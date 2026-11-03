from __future__ import annotations

__lazy_modules__ = {
    "itertools",
    "packaging.tags",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._logging",
    f"{__spec__.parent}.macos",
    f"{__spec__.parent}.sysconfig",
}

import dataclasses
import itertools
import os
import sys

import packaging.tags

from .._logging import logger
from .macos import get_macosx_deployment_target
from .sysconfig import is_free_threaded

TYPE_CHECKING = False
if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterable, Mapping, Sequence

    from .._compat.typing import Self

__all__ = ["WheelTag"]


def __dir__() -> list[str]:
    return __all__


class _PyTag:
    """Helper for interrogating a single Python ABI tag like 'cp310' or 'cp315t'."""

    def __init__(self, tag: str) -> None:
        self._tag = tag

    @property
    def is_classic_abi3(self) -> bool:
        return self._tag.startswith("cp3") and self._tag[3:].isdecimal()

    @property
    def is_ft_abi3(self) -> bool:
        return (
            self._tag.startswith("cp3")
            and self._tag.endswith("t")
            and len(self._tag) > 4
            and self._tag[3:-1].isdecimal()
        )

    @property
    def minor(self) -> int:
        if self.is_ft_abi3:
            return int(self._tag[3:-1])
        return int(self._tag[3:])

    def __str__(self) -> str:
        return self._tag


@dataclasses.dataclass(frozen=True)
class WheelTag:
    pyvers: list[str]
    abis: list[str]
    archs: list[str]
    build_tag: str = ""

    # TODO: plats only used on macOS & Windows
    @classmethod
    def compute_best(
        cls,
        archs: Sequence[str],
        py_api: str = "",
        *,
        expand_macos: bool = False,
        root_is_purelib: bool = False,
        build_tag: str = "",
        cmake_defines: Mapping[str, str] | None = None,
        cmake_args: Sequence[str] = (),
        env: Mapping[str, str] | None = None,
    ) -> Self:
        # The build environment, which the ``env`` settings table can change;
        # the tag must describe what CMake built, not the ambient environment.
        if env is None:
            env = os.environ
        if build_tag:
            if not build_tag[0].isdigit():
                msg = f"Unexpected build-tag, must start with a digit, {build_tag!r} invalid"
                raise AssertionError(msg)
            if "-" in build_tag:
                msg = f"Unexpected build-tag, {build_tag!r} cannot contain dashes"
                raise AssertionError(msg)

        # manylinux sometimes comes before linux, but can't assume manylinux, use auditwheel instead
        best_tag = next(
            iter(
                p
                for p in packaging.tags.sys_tags()
                if "manylinux" not in p.platform and "musllinux" not in p.platform
            )
        )
        interp, abi, *plats = (best_tag.interpreter, best_tag.abi, best_tag.platform)
        pyvers = [interp]

        # Check for _PYTHON_HOST_PLATFORM environment variable to override platform
        host_platform = env.get("_PYTHON_HOST_PLATFORM")
        if host_platform:
            # Convert sysconfig platform format to wheel platform tag format
            plats = [host_platform.replace("-", "_").replace(".", "_")]
        elif sys.platform.startswith("win") and archs:
            plats = [x.replace("-", "_") for x in archs]
        elif sys.platform.startswith("darwin"):
            pairs: Iterable[tuple[str | None, bool]]
            if expand_macos and archs == ["universal2"]:
                pairs = zip(
                    ["universal2", "universal2", "x86_64", "arm64"],
                    [False, True, False, True],
                    strict=True,
                )
            elif not archs:
                # It's okay to set arm to False, since this would be a native build,
                # and that will already be 11+ for ARM anyway.
                pairs = zip([None], [False], strict=True)
            else:
                pairs = zip(archs, [a == "arm64" for a in archs], strict=True)
            plats = [
                next(
                    packaging.tags.mac_platforms(
                        get_macosx_deployment_target(
                            arm=arm,
                            cmake_defines=cmake_defines,
                            cmake_args=cmake_args,
                            env=env,
                        ),
                        arch,
                    )
                )
                for arch, arm in pairs
            ]
            # Remove duplicates (e.g. universal2 if macOS > 11.0 and expanded)
            plats = list(dict.fromkeys(plats))

        if root_is_purelib:
            plats = ["any"]
            abi = "none"
            pyvers = ["py3"]

        abis = [abi]
        if py_api:
            pyvers_new = py_api.split(".")
            pytags = [_PyTag(x) for x in pyvers_new]
            gil_disabled = is_free_threaded()
            if all(t.is_classic_abi3 or t.is_ft_abi3 for t in pytags):
                if root_is_purelib:
                    msg = f"Unexpected py-api, since platlib is set to false, must be Pythonless (e.g. py2.py3), not {py_api}"
                    raise AssertionError(msg)
                stable = cls._stable_abi_tag(pytags, gil_disabled=gil_disabled)
                if stable is not None:
                    pyvers, abis = stable
            elif all(x.startswith("py") and x[2:].isdecimal() for x in pyvers_new):
                pyvers = pyvers_new
                abis = ["none"]
            else:
                msg = f"Unexpected py-api, must be abi3 (e.g. cp310), abi3t (e.g. cp315t), or Pythonless (e.g. py2.py3), not {py_api}"
                raise AssertionError(msg)

        return cls(pyvers=pyvers, abis=abis, archs=plats, build_tag=build_tag)

    @staticmethod
    def _stable_abi_tag(
        pytags: list[_PyTag], *, gil_disabled: bool
    ) -> tuple[list[str], list[str]] | None:
        """Resolve a Stable ABI py-api request to (pyvers, abis), or None to ignore."""
        classic_tags = [t for t in pytags if t.is_classic_abi3]
        ft_tags = [t for t in pytags if t.is_ft_abi3]
        is_cpython = sys.implementation.name == "cpython"

        if is_cpython and gil_disabled:
            # Free-threaded: only accept cp3XXt tags
            if not ft_tags:
                logger.debug(
                    "Ignoring py-api, free-threaded Python doesn't support the classic Stable ABI"
                )
                return None
            target = ft_tags[0]
            if target.minor > sys.version_info.minor:
                logger.debug(
                    "Ignoring py-api, version (3.{}) is too high", target.minor
                )
                return None
            # Free-threadedness lives in the abi3t ABI tag only. abi3t is a
            # subset of abi3 (PEP 803), so the single free-threaded build also
            # loads under a GIL-enabled CPython; if the classic ABI was also
            # requested (e.g. "cp315.cp315t"), advertise both.
            if classic_tags:
                # The combined tag shares one minor (the abi3t one), so the
                # classic abi3 request must not be newer; otherwise the emitted
                # abi3 tag would advertise GIL support below the requested
                # version (e.g. "cp316.cp315t" -> cp315-abi3).
                if classic_tags[0].minor > target.minor:
                    msg = (
                        f"Unexpected py-api: the classic Stable ABI ({classic_tags[0]}) "
                        f"must not be newer than the free-threaded one ({target}); a "
                        "combined abi3.abi3t wheel shares one minor version"
                    )
                    raise AssertionError(msg)
                abis = ["abi3", "abi3t"]
            else:
                abis = ["abi3t"]
            return [f"cp3{target.minor}"], abis

        # Classic CPython
        if classic_tags:
            target = classic_tags[0]
            if is_cpython and target.minor <= sys.version_info.minor:
                return [str(target)], ["abi3"]
            logger.debug(
                "Ignoring py-api, not a CPython interpreter ({}) or version (3.{}) is too high",
                sys.implementation.name,
                target.minor,
            )
            return None

        logger.debug("Ignoring py-api, free-threaded CPython is required for abi3t")
        return None

    @property
    def pyver(self) -> str:
        return ".".join(self.pyvers)

    @property
    def abi(self) -> str:
        return ".".join(self.abis)

    @property
    def arch(self) -> str:
        return ".".join(self.archs)

    def __str__(self) -> str:
        if self.build_tag:
            return f"{self.build_tag}-{self.pyver}-{self.abi}-{self.arch}"

        return f"{self.pyver}-{self.abi}-{self.arch}"

    def tags_dict(self) -> dict[str, list[str]]:
        return {
            "pyver": self.pyvers,
            "abi": self.abis,
            "arch": self.archs,
        }

    def as_tags_set(self) -> frozenset[packaging.tags.Tag]:
        vals = itertools.product(self.pyvers, self.abis, self.archs)
        return frozenset(itertools.starmap(packaging.tags.Tag, vals))


def main_wheel_tag(args: argparse.Namespace, /) -> None:
    comp_tag = WheelTag.compute_best(args.archs, args.abi, root_is_purelib=args.purelib)
    print(comp_tag)  # noqa: T201


def populate_parser(parser: argparse.ArgumentParser, /) -> None:
    """Add the ``wheel-tag`` arguments to an existing parser."""
    parser.add_argument(
        "--archs",
        nargs="*",
        default=[],
        help="Specify one or more archs (macOS only currently)",
    )
    parser.add_argument(
        "--abi",
        default="",
        help="Specify py-api, like 'cp310', 'cp315t', or 'py3'",
    )
    parser.add_argument(
        "--purelib",
        action="store_true",
        help="Specify a non-platlib (pure) tag",
    )
    parser.set_defaults(func=main_wheel_tag)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m scikit_build_core.builder.wheel_tag",
        description="Get the computed wheel tag for the current environment.",
        allow_abbrev=False,
    )
    populate_parser(parser)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
