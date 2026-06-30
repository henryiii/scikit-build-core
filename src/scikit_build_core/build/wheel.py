from __future__ import annotations

import dataclasses
import functools
import os
import platform
import shutil
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from packaging.requirements import Requirement
from packaging.tags import Tag
from packaging.utils import canonicalize_name

from .._compat import tomllib
from .._compat.typing import assert_never
from .._logging import LEVEL_VALUE, logger, rich_error, rich_print
from .._variants import get_wheel_variant
from ..cmake import CMake
from ..errors import FailedLiveProcessError
from ..settings.skbuild_read_settings import SettingsReader
from ._editable import editable_inplace_files, editable_redirect_files, get_packages
from ._init import setup_logging
from ._pathutil import (
    iter_force_include,
    packages_to_file_mapping,
    resolve_from_sdist_force_include,
    resolve_wheel_tree,
)
from ._scripts import process_script_dir
from ._wheelfile import WheelMetadata, WheelWriter
from .common_wheel_helpers import (
    build_install_extra_build_types,
    build_wheel,
    configure_wheel,
    editable_rebuild_options,
    get_build_dir,
    get_install_dir,
    get_targetlib,
    get_wheel_tag,
    install_wheel,
    prepare_wheel_dirs,
)
from .generate import generate_file_contents
from .metadata import get_standard_metadata

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from ..settings.skbuild_model import ScikitBuildSettings

__all__ = ["_build_wheel_impl"]


def __dir__() -> list[str]:
    return __all__


def _make_editable(
    *,
    build_options: Sequence[str] = (),
    install_options: Sequence[str] = (),
    libdir: Path,
    mapping: dict[str, str],
    name: str,
    reload_dir: Path | None,
    settings: ScikitBuildSettings,
    wheel: WheelWriter,
    packages: Iterable[str],
) -> None:
    for filename, contents in editable_redirect_files(
        build_options=build_options,
        install_options=install_options,
        libdir=libdir,
        mapping=mapping,
        name=name,
        packages=packages,
        reload_dir=reload_dir,
        settings=settings,
    ).items():
        wheel.writestr(filename, contents)


def _force_include_into_wheel(
    settings: ScikitBuildSettings,
    *,
    wheel_dirs: dict[str, Path],
    targetlib: str,
    only_metadata: bool = False,
) -> set[Path]:
    """
    Copy ``wheel.force-include`` entries into the staged wheel trees.

    Run after the package copy and CMake install so force-included files override
    files at the same destination. ``only_metadata`` restricts the copy to the
    metadata tree; the prepare-metadata path uses it so the prepared
    ``.dist-info`` matches the final wheel.

    Returns the resolved target paths of force-included *files*, so the caller
    can exempt them from ``wheel.exclude`` (naming an exact file forces it past
    an exclude pattern). Files copied from a force-included *directory* are not
    returned, so a bulk directory copy stays subject to ``wheel.exclude``.
    """
    written: set[Path] = set()
    for source, dest in settings.wheel.force_include.items():
        base, rest = resolve_wheel_tree(
            dest,
            wheel_dirs=wheel_dirs,
            targetlib=targetlib,
            experimental=settings.experimental,
        )
        if only_metadata and base != wheel_dirs["metadata"]:
            continue
        # A source that names an sdist output exists only in an unpacked-sdist
        # build; from a source tree or editable build, fall back through the
        # sdist.force-include map to the original source.
        resolved = resolve_from_sdist_force_include(
            source, settings.sdist.force_include
        )
        source_is_file = Path(resolved).expanduser().is_file()
        for src_file, target in iter_force_include(resolved, rest, base):
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, target)
            if source_is_file:
                written.add(target.resolve())
    return written


def _detect_auto_repackage(
    settings_reader: SettingsReader,
    *,
    exit_after_config: bool,
    cmake_install_dir: Path | None,
) -> bool:
    """
    Decide whether this is a from-sdist build of a vendored ``sdist.install-dir``
    tree, which can be repackaged into the wheel without re-running CMake.

    When true, ``wheel.cmake`` is forced off so the rest of the build skips
    configure/build/install and :func:`_restage_vendored_tree` supplies the
    contents instead. Detection (and the disable) is suppressed when:

    * this *is* the sdist install pass (``cmake_install_dir``) or a configure-only
      sdist run (``exit_after_config``);
    * ``sdist.install-dir`` is unset or its directory is absent (a source-tree
      build has no vendored tree);
    * ``PKG-INFO`` is absent (the same signal as ``if.from-sdist``);
    * the user set ``wheel.cmake`` explicitly (the opt-out: an explicit value -
      even ``false`` with a hand-written ``force-include`` recipe - is honored).
    """
    if cmake_install_dir is not None or exit_after_config:
        return False
    settings = settings_reader.settings
    install_dir = settings.sdist.install_dir
    if not install_dir or not Path(install_dir).is_dir():
        return False
    if not Path("PKG-INFO").is_file():
        return False
    if settings_reader.sources.has_item("wheel", "cmake", is_dict=False):
        return False
    settings.wheel.cmake = False
    return True


def _restage_vendored_tree(
    vendored: Path,
    *,
    wheel_dirs: dict[str, Path],
    targetlib: str,
) -> None:
    """
    Copy each subtree the ``sdist.install-dir`` pass vendored back into its wheel
    tree, reproducing the original wheel without CMake.

    The lib subtree was named for the sdist-time targetlib (``platlib`` /
    ``purelib``); remap it onto the current targetlib. A ``platlib`` subtree built
    against a ``purelib`` wheel means compiled output whose platform tag cannot be
    recovered without re-running CMake - refuse, and point at the explicit recipe.
    """
    for sub in sorted(vendored.iterdir()):
        if not sub.is_dir():
            continue
        name = sub.name
        if name in {"platlib", "purelib"}:
            if name == "platlib" and targetlib != "platlib":
                msg = (
                    "sdist.install-dir vendored a 'platlib' tree but this wheel "
                    "is purelib. Set wheel.platlib = false if the tree is pure, "
                    "or (if it is compiled) keep wheel.cmake and wheel.tags set "
                    "and use an explicit wheel.force-include recipe."
                )
                raise AssertionError(msg)
            dest = wheel_dirs[targetlib]
        elif name in wheel_dirs:
            dest = wheel_dirs[name]
        else:
            logger.warning("Ignoring unknown vendored tree {!r}", name)
            continue
        shutil.copytree(sub, dest, dirs_exist_ok=True, symlinks=True)


@dataclasses.dataclass
class WheelImplReturn:
    wheel_filename: str
    settings: ScikitBuildSettings
    mapping: dict[str, str] = dataclasses.field(default_factory=dict)


def _build_wheel_impl(
    wheel_directory: str | None,
    config_settings: dict[str, list[str] | str] | None,
    metadata_directory: str | None,
    *,
    exit_after_config: bool = False,
    editable: bool,
    cmake_install_dir: Path | None = None,
) -> WheelImplReturn:
    """
    Build a wheel or just prepare metadata (if wheel dir is None). Can be editable.
    Handles one retry attempt if "failed" override present.

    ``cmake_install_dir`` (the ``sdist.install-dir`` path) runs a full
    configure + build + install and copies the staged wheel trees there,
    returning before any wheel is assembled.
    """
    state: Literal["sdist", "wheel", "editable", "metadata_wheel", "metadata_editable"]
    if cmake_install_dir is not None:
        # The sdist.install-dir pass produces the tree later repackaged as the
        # wheel, so it configures as a wheel build: if.state = "wheel" overrides
        # and SKBUILD_STATE == "wheel" checks must apply, not the sdist ones.
        state = "wheel"
    elif exit_after_config:
        state = "sdist"
    elif wheel_directory is None:
        state = "metadata_editable" if editable else "metadata_wheel"
    else:
        state = "editable" if editable else "wheel"

    pyproject_path = Path("pyproject.toml")
    with pyproject_path.open("rb") as ft:
        pyproject = tomllib.load(ft)

    settings_reader = SettingsReader(
        pyproject, config_settings or {}, state=state, retry=False
    )
    setup_logging(settings_reader.settings.logging.level)

    settings_reader.validate_may_exit()

    if settings_reader.settings.fail:
        if settings_reader.settings.messages.after_failure:
            rich_print(settings_reader.settings.messages.after_failure)
            raise SystemExit(7)
        rich_error("scikit-build-core's fail setting was enabled. Exiting immediately.")

    # Warn if cmake or ninja is in build-system.requires
    requirements = [
        canonicalize_name(Requirement(p).name)
        for p in pyproject.get("build-system", {}).get("requires", [])
    ]
    if "cmake" in requirements:
        logger.warning(
            "cmake should not be in build-system.requires - scikit-build-core will inject it as needed"
        )
    if "ninja" in requirements:
        logger.warning(
            "ninja should not be in build-system.requires - scikit-build-core will inject it as needed"
        )

    auto_repackage = _detect_auto_repackage(
        settings_reader,
        exit_after_config=exit_after_config,
        cmake_install_dir=cmake_install_dir,
    )

    try:
        return _build_wheel_impl_impl(
            wheel_directory,
            metadata_directory,
            exit_after_config=exit_after_config,
            editable=editable,
            cmake_install_dir=cmake_install_dir,
            auto_repackage=auto_repackage,
            state=state,
            settings=settings_reader.settings,
            pyproject=pyproject,
        )
    except FailedLiveProcessError as err:
        settings_reader = SettingsReader(
            pyproject, config_settings or {}, state=state, retry=True
        )
        if "failed" not in settings_reader.overrides:
            err.msg = settings_reader.settings.messages.after_failure
            raise

        rich_print(
            "\n***",
            *err.args,
            "- retrying due to override...",
            color="yellow",
        )

        logger.setLevel(LEVEL_VALUE[settings_reader.settings.logging.level])

        settings_reader.validate_may_exit()

        auto_repackage = _detect_auto_repackage(
            settings_reader,
            exit_after_config=exit_after_config,
            cmake_install_dir=cmake_install_dir,
        )

        try:
            return _build_wheel_impl_impl(
                wheel_directory,
                metadata_directory,
                exit_after_config=exit_after_config,
                editable=editable,
                cmake_install_dir=cmake_install_dir,
                auto_repackage=auto_repackage,
                state=state,
                settings=settings_reader.settings,
                pyproject=pyproject,
            )
        except FailedLiveProcessError as err2:
            err2.msg = settings_reader.settings.messages.after_failure
            raise


def _build_wheel_impl_impl(
    wheel_directory: str | None,
    metadata_directory: str | None,
    *,
    exit_after_config: bool = False,
    editable: bool,
    cmake_install_dir: Path | None = None,
    auto_repackage: bool = False,
    state: Literal["sdist", "wheel", "editable", "metadata_wheel", "metadata_editable"],
    settings: ScikitBuildSettings,
    pyproject: dict[str, Any],
) -> WheelImplReturn:
    """
    Build a wheel or just prepare metadata (if wheel dir is None). Can be editable.
    """

    metadata = get_standard_metadata(pyproject, settings)

    if metadata.version is None:
        msg = "project.version is not specified, must be statically present or tool.scikit-build metadata.version.provider configured when dynamic"
        raise AssertionError(msg)

    # Verify PEP 639 replaces license-files
    if metadata.license_files is not None and settings.wheel.license_files:
        msg = "Both project.license-files and tool.scikit-build.wheel.license-files are set, use only one"
        raise AssertionError(msg)

    # Get the closest (normally) importable name
    normalized_name = metadata.name.replace("-", "_").replace(".", "_")

    if settings.wheel.cmake:
        cmake = CMake.default_search(version=settings.cmake.version, env=os.environ)
        cmake_msg = [f"using {{blue}}CMake {cmake.version}{{default}}"]
    else:
        cmake = None
        cmake_msg = []

    rich_print(
        "{green}*** {bold}scikit-build-core {__version__}",
        *cmake_msg,
        f"{{red}}({state})",
    )
    logger.info(
        "Implementation: {} {} on {}",
        sys.implementation.name,
        sys.platform,
        platform.machine(),
    )

    override_wheel_tags = None
    if settings.wheel.tags:
        override_wheel_tags = {Tag(*tag.split("-")) for tag in settings.wheel.tags}

    with tempfile.TemporaryDirectory() as tmpdir:
        build_tmp_folder = Path(tmpdir)
        wheel_dir = build_tmp_folder / "wheel"
        wheel_variant = get_wheel_variant(settings, pyproject, metadata)

        targetlib = get_targetlib(settings)
        tags = get_wheel_tag(settings, targetlib=targetlib)
        build_dir = get_build_dir(
            settings,
            tags=tags,
            state=state,
            editable=editable,
            has_cmake=cmake is not None,
            fallback=build_tmp_folder / "build",
        )
        wheel_dirs = prepare_wheel_dirs(wheel_dir, targetlib=targetlib)
        install_dir = get_install_dir(
            settings, wheel_dirs=wheel_dirs, targetlib=targetlib
        )

        # Automatic from-sdist repackaging: restage the trees vendored by
        # sdist.install-dir instead of running CMake. wheel.cmake was already
        # forced off in _detect_auto_repackage, so the configure/build/install
        # block below is skipped and these contents stand in for it.
        if auto_repackage:
            _restage_vendored_tree(
                Path(settings.sdist.install_dir),
                wheel_dirs=wheel_dirs,
                targetlib=targetlib,
            )

        # The metadata-only and full-wheel paths build identical WheelWriters
        # except for the output folder; share a single constructor.
        make_wheel = functools.partial(
            WheelWriter,
            metadata,
            tags=override_wheel_tags or tags.as_tags_set(),
            wheel_metadata=WheelMetadata(
                root_is_purelib=targetlib == "purelib",
                build_tag=settings.wheel.build_tag,
            ),
            metadata_dir=wheel_dirs["metadata"],
            variant_label=wheel_variant.label if wheel_variant else "",
            variant_dist_info_contents=(
                wheel_variant.dist_info_contents if wheel_variant else None
            ),
        )

        # Include the metadata license.file entry if provided
        if metadata.license_files is not None:
            license_paths = metadata.license_files
        else:
            if settings.wheel.license_files is None:
                license_file_globs = [
                    "LICEN[CS]E*",
                    "COPYING*",
                    "NOTICE*",
                    "AUTHORS*",
                ]
            else:
                license_file_globs = list(settings.wheel.license_files)
            if (
                metadata.license
                and not isinstance(metadata.license, str)
                and metadata.license.file
            ):
                license_file_globs.append(str(metadata.license.file))

            license_paths = [
                x for y in license_file_globs for x in Path().glob(y) if x.is_file()
            ]

        for x in license_paths:
            path = wheel_dirs["metadata"] / "licenses" / x
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(x, path)

        if (
            settings.wheel.license_files
            and not (wheel_dirs["metadata"] / "licenses").is_dir()
        ):
            logger.warning(
                "No license files found, set wheel.license-files to [] to suppress this warning"
            )

        for gen in settings.generate:
            if gen.location == "source":
                contents = generate_file_contents(gen, metadata)
                gen.path.write_text(contents, encoding="utf-8")
                settings.sdist.include.append(gen.path.as_posix())

        if (
            wheel_directory is None
            and not exit_after_config
            and cmake_install_dir is None
        ):
            if metadata_directory is None:
                msg = "metadata_directory must be specified if wheel_directory is None"
                raise AssertionError(msg)
            # Metadata-tree force-includes must land here too, so the prepared
            # .dist-info matches the final wheel (it is compared on build).
            _force_include_into_wheel(
                settings,
                wheel_dirs=wheel_dirs,
                targetlib=targetlib,
                only_metadata=True,
            )
            wheel = make_wheel(folder=Path(metadata_directory))
            dist_info_contents = wheel.dist_info_contents()
            dist_info = Path(metadata_directory) / f"{wheel.name_ver}.dist-info"
            dist_info.mkdir(parents=True)
            for key, data in dist_info_contents.items():
                path = dist_info / key
                if not path.parent.is_dir():
                    path.parent.mkdir(exist_ok=True, parents=True)
                path.write_bytes(data)
            return WheelImplReturn(wheel_filename=dist_info.name, settings=settings)

        for gen in settings.generate:
            contents = generate_file_contents(gen, metadata)
            if gen.location == "source":
                continue
            if gen.location == "build":
                path = build_dir / gen.path
            elif gen.location == "install":
                path = wheel_dirs[targetlib] / gen.path
            else:
                assert_never(gen.location)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents, encoding="utf-8")

        build_options: list[str] = []
        install_options: list[str] = []

        if cmake is not None:
            builder = configure_wheel(
                cmake=cmake,
                settings=settings,
                wheel_dirs=wheel_dirs,
                install_dir=install_dir,
                build_dir=build_dir,
                state=state,
                name=metadata.name,
                version=metadata.version,
            )
            if exit_after_config:
                return WheelImplReturn("", settings=settings)
            build_wheel(builder)
            install_wheel(builder, install_dir=install_dir, editable=editable)
            build_options, install_options = editable_rebuild_options(builder)
            build_install_extra_build_types(
                builder,
                settings=settings,
                wheel_dirs=wheel_dirs,
                install_dir=install_dir,
                state=state,
                name=metadata.name,
                version=metadata.version,
                editable=editable,
            )

        # sdist.install-dir: vendor every staged wheel tree, then stop before any
        # wheel is assembled. All trees are captured (not just the install
        # prefix) so files placed via SKBUILD_HEADERS_DIR / SKBUILD_SCRIPTS_DIR /
        # SKBUILD_DATA_DIR / SKBUILD_METADATA_DIR survive into the sdist. Each
        # non-empty tree lands under its own subdirectory (platlib/purelib, data,
        # headers, scripts, metadata) for the from-sdist force-include to remap;
        # the discard tree ("null") and empty trees are skipped.
        if cmake_install_dir is not None:
            if cmake is None:
                msg = "sdist.install-dir requires CMake; wheel.cmake must not be false during the SDist build"
                raise AssertionError(msg)
            for tree_name, tree in wheel_dirs.items():
                if tree_name == "null" or not any(tree.iterdir()):
                    continue
                shutil.copytree(
                    tree,
                    cmake_install_dir / tree_name,
                    dirs_exist_ok=True,
                    symlinks=True,
                )
            return WheelImplReturn(wheel_filename="", settings=settings)

        assert wheel_directory is not None

        rich_print("{green}***", f"{{bold}}Making {state}...")
        packages = get_packages(
            packages=settings.wheel.packages,
            name=metadata.name,
        )
        assert settings.sdist.inclusion_mode is not None
        mapping = packages_to_file_mapping(
            packages=packages,
            platlib_dir=wheel_dirs[targetlib],
            include=settings.sdist.include,
            src_exclude=settings.sdist.exclude,
            target_exclude=settings.wheel.exclude,
            build_dir=settings.build_dir,
            mode=settings.sdist.inclusion_mode,
        )

        if not editable:
            for filepath, package_dir in mapping.items():
                Path(package_dir).parent.mkdir(exist_ok=True, parents=True)
                shutil.copy2(filepath, package_dir)

        # Force-include into the wheel, always (even for editable installs, as
        # these files are not redirectable) and after the package copy, so they
        # override package files and CMake output at the same destination.
        force_included = _force_include_into_wheel(
            settings,
            wheel_dirs=wheel_dirs,
            targetlib=targetlib,
        )

        # Normalize script shebangs after force-includes, so force-included
        # scripts (e.g. wheel = "/scripts/...") are processed too. Editable
        # installs still ship scripts (CMake-installed or force-included), so
        # normalize them as well.
        process_script_dir(wheel_dirs["scripts"])

        with make_wheel(folder=Path(wheel_directory)) as wheel:
            wheel.build(
                wheel_dirs,
                exclude=settings.wheel.exclude,
                exclude_exempt=force_included,
            )

            str_pkgs = (
                str(Path.cwd().joinpath(p).parent.resolve()) for p in packages.values()
            )
            if editable and settings.editable.mode == "redirect":
                reload_dir = build_dir.resolve() if settings.build_dir else None

                _make_editable(
                    build_options=build_options,
                    install_options=install_options,
                    libdir=wheel_dirs[targetlib],
                    mapping=mapping,
                    reload_dir=reload_dir,
                    settings=settings,
                    wheel=wheel,
                    name=normalized_name,
                    packages=str_pkgs,
                )
            elif editable and settings.editable.mode == "inplace":
                if not packages:
                    msg = "Editable inplace mode requires at least one package"
                    raise AssertionError(msg)

                for filename, editable_contents in editable_inplace_files(
                    name=normalized_name,
                    packages=str_pkgs,
                ).items():
                    wheel.writestr(filename, editable_contents)

    if metadata_directory is not None:
        dist_info_contents = wheel.dist_info_contents()
        dist_info = Path(metadata_directory)
        for key, data in dist_info_contents.items():
            path = dist_info / key
            previous_data = path.read_bytes()
            if previous_data != data:
                msg = f"Metadata mismatch in {key}"
                logger.error("{}: {!r} != {!r}", msg, previous_data, data)
                raise AssertionError(msg)

    wheel_filename: str = wheel.wheelpath.name
    rich_print("{green}***", f"{{bold}}Created{{normal}} {wheel_filename}")
    if settings.messages.after_success:
        rich_print(settings.messages.after_success)
    return WheelImplReturn(
        wheel_filename=wheel_filename, mapping=mapping, settings=settings
    )
