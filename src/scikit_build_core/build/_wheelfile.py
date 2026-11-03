from __future__ import annotations

__lazy_modules__ = {
    "base64",
    "csv",
    "datetime",
    "email.message",
    "hashlib",
    "io",
    "pathlib",
    "pathspec",
    "zipfile",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._reproducible",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._variants",
}

import base64
import csv
import dataclasses
import datetime as dt
import hashlib
import io
import os
import stat
import time
import zipfile
from email.message import Message
from email.policy import EmailPolicy
from pathlib import Path
from zipfile import ZipInfo

import pathspec

from .. import __version__
from .._reproducible import (
    MAX_TIMESTAMP,
    MIN_TIMESTAMP,
    get_reproducible_epoch,
    normalize_file_permissions,
    parse_source_date_epoch,
)
from .._variants import VARIANT_DIST_INFO_FILENAME

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from collections.abc import Set as AbstractSet

    from packaging.tags import Tag

    from .._compat.typing import Self
    from .._vendor.pyproject_metadata import StandardMetadata

EMAIL_POLICY = EmailPolicy(max_line_length=0, mangle_from_=False, utf8=True)


def _b64encode(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


__all__ = ["WheelMetadata", "WheelWriter"]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass
class WheelMetadata:
    root_is_purelib: bool = False
    metadata_version: str = "1.0"
    generator: str = f"scikit-build-core {__version__}"
    tags: AbstractSet[Tag] = dataclasses.field(default_factory=frozenset)
    build_tag: str = ""

    def as_bytes(self) -> bytes:
        msg = Message(policy=EMAIL_POLICY)

        msg["Wheel-Version"] = self.metadata_version
        msg["Generator"] = self.generator
        msg["Root-Is-Purelib"] = str(self.root_is_purelib).lower()

        for tag in sorted(self.tags, key=lambda t: (t.interpreter, t.abi, t.platform)):
            msg["Tag"] = f"{tag.interpreter}-{tag.abi}-{tag.platform}"
        if self.build_tag:
            msg["Build"] = self.build_tag

        return msg.as_bytes()


@dataclasses.dataclass
class WheelWriter:
    """A general tool for writing wheels. Designed to look a little like ZipFile."""

    metadata: StandardMetadata
    folder: Path
    tags: AbstractSet[Tag]
    wheel_metadata: WheelMetadata
    metadata_dir: Path | None
    variant_label: str = ""
    variant_dist_info_contents: bytes | None = None
    reproducible: bool = False
    _zipfile: zipfile.ZipFile | None = None

    @property
    def name_ver(self) -> str:
        name = self.metadata.canonical_name.replace("-", "_")
        # replace - with _ as a local version separator
        version = str(self.metadata.version).replace("-", "_")
        return f"{name}-{version}"

    @property
    def basename(self) -> str:
        pyver = ".".join(sorted({t.interpreter for t in self.tags}))
        abi = ".".join(sorted({t.abi for t in self.tags}))
        arch = ".".join(sorted({t.platform for t in self.tags}))
        optbuildver = (
            [self.wheel_metadata.build_tag] if self.wheel_metadata.build_tag else []
        )
        variant = [self.variant_label] if self.variant_label else []
        return "-".join([self.name_ver, *optbuildver, pyver, abi, arch, *variant])

    @property
    def wheelpath(self) -> Path:
        return self.folder / f"{self.basename}.whl"

    @property
    def dist_info(self) -> str:
        return f"{self.name_ver}.dist-info"

    def timestamp(
        self, mtime: float | None = None
    ) -> tuple[int, int, int, int, int, int]:
        if self.reproducible:
            # Honor SOURCE_DATE_EPOCH, else a fixed epoch (ignore per-file mtime).
            timestamp = get_reproducible_epoch()
        else:
            raw = os.environ.get("SOURCE_DATE_EPOCH")
            timestamp = (
                parse_source_date_epoch(raw)
                if raw is not None
                else int(mtime or time.time())
            )
        # The ZIP file format only supports timestamps from 1980-01-01 to
        # 2107-12-31 23:59:59 (inclusive); clamp rather than let zipfile crash.
        timestamp = min(max(timestamp, MIN_TIMESTAMP), MAX_TIMESTAMP)
        # Not time.gmtime: it overflows past 2038 where time_t is 32 bits.
        when = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc) + dt.timedelta(
            seconds=timestamp
        )
        return (when.year, when.month, when.day, when.hour, when.minute, when.second)

    def dist_info_contents(self) -> dict[str, bytes]:
        entry_points = io.StringIO()
        ep = self.metadata.entrypoints.copy()
        ep["console_scripts"] = self.metadata.scripts
        ep["gui_scripts"] = self.metadata.gui_scripts
        for group, entries in ep.items():
            if entries:
                entry_points.write(f"[{group}]\n")
                for name, target in entries.items():
                    entry_points.write(f"{name} = {target}\n")
                entry_points.write("\n")

        self.wheel_metadata.tags = self.tags

        rfc822 = self.metadata.as_rfc822()

        metadata_files = self.metadata_dir.rglob("*") if self.metadata_dir else []
        extra_metadata = {
            str(f.relative_to(self.metadata_dir or Path())): f.read_bytes()
            for f in metadata_files
            if f.is_file()
        }
        reserved = {"METADATA", "WHEEL", "RECORD", "entry_points.txt"}
        if self.variant_dist_info_contents is not None:
            reserved.add(VARIANT_DIST_INFO_FILENAME)
        if reserved & extra_metadata.keys():
            msg = f"Cannot have {', '.join(sorted(reserved))} in metadata_dir"
            raise ValueError(msg)

        entry_points_txt = entry_points.getvalue().encode("utf-8")
        entry_points_dict = (
            {"entry_points.txt": entry_points_txt} if entry_points_txt else {}
        )

        return {
            "METADATA": bytes(rfc822),
            "WHEEL": self.wheel_metadata.as_bytes(),
            **entry_points_dict,
            **(
                {VARIANT_DIST_INFO_FILENAME: self.variant_dist_info_contents}
                if self.variant_dist_info_contents is not None
                else {}
            ),
            **extra_metadata,
        }

    def build(
        self,
        wheel_dirs: Mapping[str, Path],
        exclude: Sequence[str] = (),
        exclude_exempt: AbstractSet[Path] = frozenset(),
        *,
        source_mapping: Mapping[str, str] | None = None,
    ) -> None:
        """Write staged files and optional source-to-staging package mappings.

        Package sources are read directly, without an intermediate copy. Files
        already in staging take precedence, including force-included files.
        """
        (targetlib,) = {"platlib", "purelib"} & set(wheel_dirs)
        assert {
            targetlib,
            "data",
            "headers",
            "scripts",
            "null",
            "metadata",
        } >= wheel_dirs.keys()

        # The "main" directory (platlib usually for us) will be handled specially below
        plans = {"": wheel_dirs[targetlib]}
        data_dir = f"{self.name_ver}.data"

        for key in sorted({"data", "headers", "scripts"} & wheel_dirs.keys()):
            plans[key] = wheel_dirs[key]

        exclude_spec = pathspec.GitIgnoreSpec.from_lines(exclude)
        # Staged symlinks may point at package sources that are not in staging.
        resolved_sources = {
            Path(os.path.realpath(dst)): Path(src)
            for src, dst in (source_mapping or {}).items()
        }

        for key, path in plans.items():
            sources = (
                {Path(dst): Path(src) for src, dst in (source_mapping or {}).items()}
                if not key
                else {}
            )
            for f in path.glob("**/*"):
                if f.is_file():
                    sources[f] = f
                elif f.is_symlink():
                    target = resolved_sources.get(Path(os.path.realpath(f)))
                    if target is not None:
                        sources[f] = target
            for filename in sorted(sources):
                if any(x.endswith(".dist-info") for x in filename.parts):
                    continue
                if filename.suffix in {".pyc", ".pyo"}:
                    continue
                relpath = filename.relative_to(path)
                # Force-included files are exempt from wheel.exclude.
                if (
                    exclude_spec.match_file(relpath)
                    and filename.resolve() not in exclude_exempt
                ):
                    continue
                target = Path(data_dir) / key / relpath if key else relpath
                self.write(str(sources[filename]), str(target))

        dist_info_contents = self.dist_info_contents()
        for key, data in dist_info_contents.items():
            self.writestr(f"{self.dist_info}/{key}", data)

    def write(self, filename: str, arcname: str | None = None) -> None:
        """Write a file to the archive. Paths are normalized to Posix paths."""

        with Path(filename).open("rb") as f:
            st = os.fstat(f.fileno())
            data = f.read()

        # Zipfiles require Posix paths for the arcname
        zinfo = ZipInfo(
            (arcname or filename).replace("\\", "/"),
            date_time=self.timestamp(st.st_mtime),
        )
        zinfo.compress_type = zipfile.ZIP_DEFLATED
        mode = (
            normalize_file_permissions(st.st_mode) if self.reproducible else st.st_mode
        )
        zinfo.external_attr = (stat.S_IMODE(mode) | stat.S_IFMT(st.st_mode)) << 16
        self.writestr(zinfo, data)

    def writestr(self, zinfo_or_arcname: str | ZipInfo, data: bytes) -> None:
        """Write bytes (not strings) to the archive."""
        assert isinstance(data, bytes)
        assert self._zipfile is not None
        if isinstance(zinfo_or_arcname, zipfile.ZipInfo):
            zinfo = zinfo_or_arcname
        else:
            zinfo = zipfile.ZipInfo(
                zinfo_or_arcname.replace("\\", "/"),
                date_time=self.timestamp(),
            )
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o644 if self.reproducible else 0o664
            zinfo.external_attr = (mode | stat.S_IFREG) << 16
        assert "\\" not in zinfo.filename, (
            f"\\ not supported in zip; got {zinfo.filename!r}"
        )
        self._zipfile.writestr(zinfo, data)

    def __enter__(self) -> Self:
        if not self.wheelpath.parent.exists():
            self.wheelpath.parent.mkdir(parents=True)

        self._zipfile = zipfile.ZipFile(
            self.wheelpath, "w", compression=zipfile.ZIP_DEFLATED
        )
        return self

    def __exit__(self, *args: object) -> None:
        assert self._zipfile is not None
        record = f"{self.dist_info}/RECORD"
        data = io.StringIO()
        writer = csv.writer(data, delimiter=",", quotechar='"', lineterminator="\n")
        for member in self._zipfile.infolist():
            assert "\\" not in member.filename, (
                f"Invalid zip contents: {member.filename}"
            )
            with self._zipfile.open(member) as f:
                member_data = f.read()
            sha = _b64encode(hashlib.sha256(member_data).digest()).decode("ascii")
            writer.writerow((member.filename, f"sha256={sha}", member.file_size))
        writer.writerow((record, "", ""))
        self.writestr(record, data.getvalue().encode("utf-8"))
        self._zipfile.close()
        self._zipfile = None
