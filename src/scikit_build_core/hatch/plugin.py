from __future__ import annotations

import copy
import os
import sys
import sysconfig
import typing
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from packaging.version import Version

from scikit_build_core.settings.skbuild_model import ScikitBuildSettings

from .. import __version__
from .._compat.typing import Literal
from .._logging import logger, rich_print
from ..build._init import setup_logging
from ..builder.builder import Builder, archs_to_tags, get_archs
from ..builder.get_requires import GetRequires
from ..builder.wheel_tag import WheelTag
from ..cmake import CMake, CMaker
from ..settings.skbuild_read_settings import SettingsReader

__all__ = ["ScikitBuildHook"]


def __dir__() -> list[str]:
    return __all__


class ScikitBuildHook(BuildHookInterface):  # type: ignore[type-arg]
    PLUGIN_NAME = "scikit-build"

    def _read_config(self) -> SettingsReader:
        config_dict = copy.deepcopy(self.config)
        config_dict.pop("dependencies", None)
        config_dict.pop("require-runtime-dependencies", None)
        config_dict.pop("require-runtime-features", None)
        config_dict.pop("require-runtime-features", None)

        state = typing.cast(Literal["sdist", "wheel", "editable"], self.target_name)
        return SettingsReader.from_file(
            "pyproject.toml", state=state, extra_settings=config_dict
        )

    def _validate(self, settings_reader: SettingsReader) -> None:
        settings = settings_reader.settings

        settings_reader.validate_may_exit()

        if not settings.experimental:
            msg = "Hatch support is experimental, must enable the experimental flag"
            raise ValueError(msg)

        if not settings.wheel.cmake or settings.sdist.cmake:
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

    def dependencies(self) -> list[str]:
        settings = self._read_config().settings
        requires = GetRequires(settings)

        if self.target_name == "sdist":
            required = requires.settings.sdist.cmake
        elif self.target_name in {"wheel", "editable"}:
            required = requires.settings.wheel.cmake
        else:
            msg = f"Unknown target: {self.target_name!r}, only 'sdist', 'wheel', 'editable' are supported"
            raise ValueError(msg)

        # These are only injected if cmake is required
        cmake_requires = [*requires.cmake(), *requires.ninja()] if required else []
        return [*cmake_requires, *requires.dynamic_metadata()]

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:  # noqa: ARG002
        settings_reader = self._read_config()
        settings = settings_reader.settings
        state = settings_reader.state

        self._validate(settings_reader)

        if state == "sdist":
            build_data["artifacts"].append("CMakeLists.txt")  # Needs full list, etc.
            return

        setup_logging(settings.logging.level)

        cmake = CMake.default_search(version=settings.cmake.version, env=os.environ)

        rich_print(
            f"[green]***[/green] [bold][green]scikit-build-core {__version__}[/green]",
            f"using [blue]CMake {cmake.version}[/blue]",
            f"[red]({state})[/red]",
        )

        build_tmp_folder = Path(self.directory)
        wheel_dir = build_tmp_folder / "wheel"

        tags = WheelTag.compute_best(
            archs_to_tags(get_archs(os.environ)),
            settings.wheel.py_api,
            expand_macos=settings.wheel.expand_macos_universal_tags,
            build_tag=settings.wheel.build_tag,
        )
        build_data["tag"] = str(tags)
        build_data["pure_python"] = not settings.wheel.platlib

        build_dir = (
            Path(
                settings.build_dir.format(
                    cache_tag=sys.implementation.cache_tag,
                    wheel_tag=str(tags),
                    build_type=settings.cmake.build_type,
                    state=state,
                )
            )
            if settings.build_dir
            else build_tmp_folder / "build"
        )
        logger.info("Build directory: {}", build_dir.resolve())

        targetlib = "platlib"

        wheel_dirs = {
            targetlib: wheel_dir / targetlib,
            "data": wheel_dir / "data",
            "headers": wheel_dir / "headers",
            "scripts": wheel_dir / "scripts",
            "null": wheel_dir / "null",
        }

        for d in wheel_dirs.values():
            d.mkdir(parents=True)

        if ".." in settings.wheel.install_dir:
            msg = "wheel.install_dir must not contain '..'"
            raise AssertionError(msg)
        if settings.wheel.install_dir.startswith("/"):
            if not settings.experimental:
                msg = "Experimental features must be enabled to use absolute paths in wheel.install_dir"
                raise AssertionError(msg)
            if settings.wheel.install_dir[1:].split("/")[0] not in wheel_dirs:
                msg = "Must target a valid wheel directory"
                raise AssertionError(msg)
            install_dir = wheel_dir / settings.wheel.install_dir[1:]
        else:
            install_dir = wheel_dirs[targetlib] / settings.wheel.install_dir

        config = CMaker(
            cmake,
            source_dir=settings.cmake.source_dir,
            build_dir=build_dir,
            build_type=settings.cmake.build_type,
        )

        builder = Builder(
            settings=settings,
            config=config,
        )

        rich_print("[green]***[/green] [bold]Configuring CMake...")
        defines: dict[str, str] = {}
        cache_entries: dict[str, str | Path] = {
            f"SKBUILD_{k.upper()}_DIR": v for k, v in wheel_dirs.items()
        }
        cache_entries["SKBUILD_STATE"] = state
        builder.configure(
            defines=defines,
            cache_entries=cache_entries,
            name=self.build_config.builder.metadata.name,
            version=Version(self.build_config.builder.metadata.version),
        )

        default_gen = (
            "MSVC"
            if sysconfig.get_platform().startswith("win")
            else "Default Generator"
        )
        generator = builder.get_generator() or default_gen
        rich_print(
            f"[green]***[/green] [bold]Building project with [blue]{generator}[/blue]..."
        )
        build_args: list[str] = []
        builder.build(build_args=build_args)

        rich_print("[green]***[/green] [bold]Installing project into wheel...")
        builder.install(install_dir)

        for unsupported in ("headers", "scripts"):
            files = list(wheel_dirs[unsupported].iterdir())
            if files:
                msg = f"Unsupported files found in {unsupported} directory: {files}"
                raise ValueError(msg)

        for path in wheel_dirs[targetlib].iterdir():
            build_data["artifacts"].append(path)
            build_data["force_include"][f"{path}"] = str(
                settings.wheel.install_dir / path.relative_to(wheel_dirs[targetlib])
            )
        for path in wheel_dirs["data"].iterdir():
            build_data["artifacts"].append(path)
            build_data["shared-data"][f"{path}"] = str(
                path.relative_to(wheel_dirs[targetlib])
            )
