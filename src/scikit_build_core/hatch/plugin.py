from __future__ import annotations

__lazy_modules__ = {
    "copy",
    "importlib.metadata",
    "packaging.utils",
    "packaging.version",
    "pathlib",
    "shutil",
    "tempfile",
    "typing",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._check_extra",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._logging",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.build._editable",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.build._init",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.build._pathutil",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.build.common_wheel_helpers",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.builder.get_requires",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.cmake",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.settings.skbuild_model",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.settings.skbuild_read_settings",
}

import copy
import importlib.metadata
import os
import shutil
import tempfile
import typing
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.utils import canonicalize_name
from packaging.version import Version

from .._check_extra import warn_missing_extra
from .._logging import rich_print
from ..build._editable import (
    editable_inplace_files,
    editable_redirect_files,
    get_packages,
    package_search_dirs,
)
from ..build._init import setup_logging
from ..build._pathutil import packages_to_file_mapping, scantree
from ..build.common_wheel_helpers import (
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
from ..builder.get_requires import GetRequires
from ..cmake import CMake
from ..settings.skbuild_model import ScikitBuildSettings
from ..settings.skbuild_read_settings import SettingsReader

__all__ = ["ScikitBuildHook"]


def __dir__() -> list[str]:
    return __all__


class ScikitBuildHook(BuildHookInterface):  # type: ignore[type-arg]
    PLUGIN_NAME = "scikit-build"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.__tmp_dir: Path | None = None

    def _read_config(
        self,
        *,
        state: typing.Literal["sdist", "wheel", "editable"] | None = None,
    ) -> SettingsReader:
        config_dict = copy.deepcopy(self.config)
        config_dict.pop("dependencies", None)
        config_dict.pop("require-runtime-dependencies", None)
        config_dict.pop("require-runtime-features", None)
        config_dict.pop("enable-by-default", None)

        if state is None:
            state = typing.cast(
                "typing.Literal['sdist', 'wheel', 'editable']", self.target_name
            )
        return SettingsReader.from_file(
            "pyproject.toml", state=state, extra_settings=config_dict
        )

    def _validate(self, settings_reader: SettingsReader) -> None:
        settings = settings_reader.settings

        settings_reader.validate_may_exit()

        if not settings.wheel.cmake:
            msg = "CMake is required for scikit-build"
            raise ValueError(msg)

        if settings.sdist.include or settings.sdist.exclude:
            msg = "include and exclude are not supported for hatch builds"
            raise ValueError(msg)

        if settings.sdist.cmake:
            msg = "Not currently supported for SDist builds"
            raise ValueError(msg)

        if settings.wheel.packages:
            msg = f"Packages ({settings.wheel.packages!r}) are not supported for hatch builds"
            raise ValueError(msg)

        if (
            settings.wheel.license_files
            and settings.wheel.license_files
            != ScikitBuildSettings().wheel.license_files
        ):
            msg = f"License files ({settings.wheel.license_files!r}) are not supported for hatch builds"
            raise ValueError(msg)

        if settings.wheel.platlib is not None and not settings.wheel.platlib:
            msg = "Purelib builds not supported for hatch builds"
            raise ValueError(msg)

        if settings.generate:
            msg = "Generate is not supported for hatch builds"
            raise ValueError(msg)

        if settings.metadata:
            msg = "Metadata is not supported for hatch builds"
            raise ValueError(msg)

        if settings.sdist.force_include or settings.wheel.force_include:
            msg = "scikit-build.*.force-include is not supported, use hatch's force-include instead"
            raise ValueError(msg)

        if settings.wheel.exclude:
            msg = "wheel.exclude is not supported for hatch builds, use hatch's exclude instead"
            raise ValueError(msg)

    def dependencies(self) -> list[str]:
        reader = self._read_config()
        requires = GetRequires(reader.settings, reader.dynamic_metadata, reader.variant)

        if self.target_name == "sdist":
            required = requires.settings.sdist.cmake
        elif self.target_name == "wheel":
            required = requires.settings.wheel.cmake
        else:
            msg = f"Unknown target: {self.target_name!r}, only 'sdist' and 'wheel' are supported"
            raise ValueError(msg)

        # These are only injected if cmake is required
        cmake_requires = [*requires.cmake(), *requires.ninja()] if required else []
        return [*cmake_requires, *requires.dynamic_metadata()]

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        try:
            self._initialize(version=version, build_data=build_data)
        except Exception:
            self._cleanup()
            raise

    def _initialize(self, *, version: str, build_data: dict[str, Any]) -> None:
        requested_state = (
            "editable"
            if version == "editable"
            else typing.cast("typing.Literal['sdist', 'wheel']", self.target_name)
        )
        settings_reader = self._read_config(state=requested_state)
        settings = settings_reader.settings
        state = typing.cast(
            "typing.Literal['editable', 'sdist', 'wheel']", settings_reader.state
        )
        editable = state == "editable"

        self._validate(settings_reader)

        warn_missing_extra("hatchling")

        if state == "sdist":
            build_data["artifacts"].append("CMakeLists.txt")  # Needs full list, etc.
            return

        setup_logging(settings.logging.level)

        cmake = CMake.default_search(version=settings.cmake.version, env=os.environ)

        rich_print(
            "{green}***",
            "{bold.green}scikit-build-core {__version__}",
            f"using {{blue}}CMake {cmake.version}",
            f"{{red}}({state})",
        )

        self.__tmp_dir = Path(tempfile.mkdtemp()).resolve()
        wheel_dir = self.__tmp_dir / "wheel"

        # _validate guarantees wheel.cmake is true and rejects a falsy
        # wheel.platlib (purelib), so this is always a platlib build.
        targetlib = get_targetlib(settings)
        assert targetlib == "platlib"
        tags = get_wheel_tag(settings, targetlib=targetlib)
        # Normalized like the wheel/sdist filename, for the {name} build-dir placeholder
        placeholder_name = canonicalize_name(
            self.build_config.builder.metadata.name
        ).replace("-", "_")
        build_dir = get_build_dir(
            settings,
            tags=tags,
            state=state,
            editable=editable,
            has_cmake=True,
            fallback=self.__tmp_dir / "build",
            name=placeholder_name,
        )
        wheel_dirs = prepare_wheel_dirs(wheel_dir, targetlib=targetlib)
        install_dir = get_install_dir(
            settings, wheel_dirs=wheel_dirs, targetlib=targetlib
        )

        build_data["tag"] = str(tags)
        build_data["pure_python"] = False

        extra_cache_entries = {
            "SKBUILD_HATCHLING": importlib.metadata.version("hatchling")
        }
        builder = configure_wheel(
            cmake=cmake,
            settings=settings,
            wheel_dirs=wheel_dirs,
            install_dir=install_dir,
            build_dir=build_dir,
            state=state,
            name=self.build_config.builder.metadata.name,
            version=Version(self.build_config.builder.metadata.version),
            extra_cache_entries=extra_cache_entries,
        )
        build_wheel(builder)
        install_wheel(builder, install_dir=install_dir, editable=editable)
        build_options, install_options = editable_rebuild_options(builder)
        build_install_extra_build_types(
            builder,
            settings=settings,
            wheel_dirs=wheel_dirs,
            install_dir=install_dir,
            state=state,
            name=self.build_config.builder.metadata.name,
            version=Version(self.build_config.builder.metadata.version),
            editable=editable,
            extra_cache_entries=extra_cache_entries,
        )

        files = list(wheel_dirs["headers"].iterdir())
        if files:
            msg = (
                f"Unsupported files found in 'headers' directory: {files}\n"
                "Please report use case to https://github.com/pypa/hatch/issues/1291 if you need it."
            )
            raise ValueError(msg)

        if editable:
            editable_force_include = build_data["force_include_editable"]
            normalized_name = self.build_config.builder.metadata.name.replace(
                "-", "_"
            ).replace(".", "_")
            packages = get_packages(
                packages=settings.wheel.packages,
                name=self.build_config.builder.metadata.name,
            )
            package_paths = package_search_dirs(packages)
            if package_paths:
                self.build_config.target_config["dev-mode-dirs"] = package_paths

            if settings.editable.mode == "redirect":
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
                reload_dir = build_dir.resolve() if settings.build_dir else None
                editable_files = editable_redirect_files(
                    build_options=build_options,
                    install_options=install_options,
                    libdir=wheel_dirs[targetlib],
                    mapping=mapping,
                    name=normalized_name,
                    packages=package_paths,
                    reload_dir=reload_dir,
                    settings=settings,
                )
                for editable_file in scantree(wheel_dirs[targetlib]):
                    editable_force_include[str(editable_file.resolve())] = str(
                        editable_file.relative_to(wheel_dirs[targetlib])
                    )
            else:
                if not packages:
                    msg = "Editable inplace mode requires at least one package"
                    raise AssertionError(msg)
                editable_files = editable_inplace_files(
                    name=normalized_name,
                    packages=packages,
                    package_paths=package_paths,
                    source_dir=build_dir.resolve(),
                    build_options=build_options,
                    settings=settings,
                )

            editable_dir = self.__tmp_dir / "editable"
            editable_dir.mkdir(parents=True, exist_ok=True)
            for filename, contents in editable_files.items():
                path = editable_dir / filename
                path.write_bytes(contents)
                editable_force_include[str(path)] = filename
        else:
            # CMake already installed into
            # wheel_dirs[targetlib] / settings.wheel.install_dir, so the files
            # under wheel_dirs[targetlib] already carry the install_dir prefix;
            # mapping them relative to wheel_dirs[targetlib] keeps that single
            # prefix (matching the editable branch above).
            for raw_path in wheel_dirs[targetlib].iterdir():
                path = raw_path.resolve()  # Windows mingw64 and UCRT now requires this
                build_data["force_include"][f"{path}"] = str(
                    path.relative_to(wheel_dirs[targetlib])
                )

        for raw_path in wheel_dirs["data"].iterdir():
            path = raw_path.resolve()  # Windows mingw64 and UCRT now requires this
            build_data["shared_data"][f"{path}"] = str(
                path.relative_to(wheel_dirs["data"])
            )

        for raw_path in wheel_dirs["scripts"].iterdir():
            path = raw_path.resolve()  # Windows mingw64 and UCRT now requires this
            build_data["shared_scripts"][f"{path}"] = str(
                path.relative_to(wheel_dirs["scripts"])
            )

        for raw_path_root in wheel_dirs["metadata"].iterdir():
            path_root = (
                raw_path_root.resolve()
            )  # Windows mingw64 and UCRT now requires this
            if path_root.name != "extra_metadata":
                msg = f"Hatchling metadata must be in an extra_metadata folder, got {path_root}"
                raise ValueError(msg)
            for raw_path in path_root.iterdir():
                path = raw_path.resolve()  # Windows mingw64 and UCRT now requires this
                build_data["extra_metadata"][f"{path}"] = str(
                    path.relative_to(path_root)
                )

    def finalize(
        self, version: str, build_data: dict[str, Any], artifact_path: str
    ) -> None:
        self._cleanup()
        return super().finalize(version, build_data, artifact_path)

    def _cleanup(self) -> None:
        if self.__tmp_dir:
            shutil.rmtree(self.__tmp_dir, ignore_errors=True)
            self.__tmp_dir = None
