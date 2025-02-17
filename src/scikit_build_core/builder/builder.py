from __future__ import annotations

import dataclasses
import os
import re
import shlex
import sys
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING

from .. import __version__
from .._compat.importlib import metadata, resources
from .._logging import logger
from ..resources import find_python
from .generator import set_environment_for_gen
from .sysconfig import (
    get_numpy_include_dir,
    get_platform,
    get_python_include_dir,
    get_python_library,
    get_soabi,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping, Sequence

    from packaging.version import Version

    from ..cmake import CMaker
    from ..settings.skbuild_model import ScikitBuildSettings

__all__ = ["Builder", "archs_to_tags", "get_archs"]

DIR = Path(__file__).parent.resolve()


def __dir__() -> list[str]:
    return __all__


# TODO: cross-compile support for other platforms
def get_archs(env: Mapping[str, str], cmake_args: Sequence[str] = ()) -> list[str]:
    """
    Takes macOS platform settings and returns a list of platforms.

    Example (macOS):
        ARCHFLAGS="-arch x86_64" -> ["x86_64"]
        ARCHFLAGS="-arch x86_64 -arch arm64" -> ["x86_64", "arm64"]

    Returns an empty list otherwise or if ARCHFLAGS is not set.
    """

    if sys.platform.startswith("darwin"):
        for cmake_arg in cmake_args:
            if "CMAKE_SYSTEM_PROCESSOR" in cmake_arg:
                return [cmake_arg.split("=")[1]]
        return re.findall(r"-arch (\S+)", env.get("ARCHFLAGS", ""))
    if sys.platform.startswith("win") and get_platform(env) == "win-arm64":
        return ["win_arm64"]

    return []


def archs_to_tags(archs: list[str]) -> list[str]:
    """
    Convert a list of architectures to a list of tags (e.g. "universal2").
    """
    if sys.platform.startswith("darwin") and set(archs) == {"arm64", "x86_64"}:
        return ["universal2"]
    return archs


def _filter_env_cmake_args(env_cmake_args: list[str]) -> Generator[str, None, None]:
    """
    Filter out CMake arguments that are not supported from CMAKE_ARGS.
    """

    unsupported_args = ("-DCMAKE_BUILD_TYPE", "-DCMAKE_INSTALL_PREFIX")

    for arg in env_cmake_args:
        if arg.startswith(unsupported_args):
            logger.warning("Unsupported CMAKE_ARGS ignored: {}", arg)
        else:
            yield arg


def _sanitize_path(path: os.PathLike[str]) -> list[Path]:
    # This handles classes like:
    # MultiplexedPath from importlib.resources.readers (3.11+)
    # MultiplexedPath from importlib.readers (3.10)
    # MultiplexedPath from importlib_resources.readers
    if hasattr(path, "_paths"):
        # pylint: disable-next=protected-access
        return [Path(os.fspath(p)) for p in path._paths]

    return [Path(os.fspath(path))]


@dataclasses.dataclass
class Builder:
    settings: ScikitBuildSettings
    config: CMaker

    def get_cmake_args(self) -> list[str]:
        """
        Get CMake args from the settings and environment.
        """
        # Adding CMake arguments set as environment variable
        # (needed e.g. to build for ARM OSX on conda-forge)
        env_cmake_args: list[str] = list(
            filter(None, shlex.split(self.config.env.get("CMAKE_ARGS", "")))
        )

        if env_cmake_args:
            logger.debug("Env CMAKE_ARGS: {}", env_cmake_args)

        return [*self.settings.cmake.args, *_filter_env_cmake_args(env_cmake_args)]

    def get_generator(self, *args: str) -> str | None:
        return self.config.get_generator(*self.get_cmake_args(), *args)

    def configure(
        self,
        *,
        defines: Mapping[str, str | bool | Path],
        cache_entries: Mapping[str, str | Path] | None = None,
        name: str | None = None,
        version: Version | None = None,
        limited_api: bool | None = None,
        configure_args: Iterable[str] = (),
    ) -> None:
        cmake_defines = {
            k: ("TRUE" if v else "FALSE") if isinstance(v, bool) else str(v)
            for k, v in defines.items()
        }

        # Add any extra CMake modules
        eps = metadata.entry_points(group="cmake.module")
        self.config.module_dirs.extend(
            p for ep in eps for p in _sanitize_path(resources.files(ep.load()))
        )

        # Add any extra CMake prefixes
        eps = metadata.entry_points(group="cmake.prefix")
        self.config.prefix_dirs.extend(
            p for ep in eps for p in _sanitize_path(resources.files(ep.load()))
        )

        # Add site-packages to the prefix path for CMake
        site_packages = Path(sysconfig.get_path("purelib"))
        self.config.prefix_dirs.append(site_packages)
        logger.debug("SITE_PACKAGES: {}", site_packages)
        if site_packages != DIR.parent.parent:
            self.config.prefix_dirs.append(DIR.parent.parent)
            logger.debug("Extra SITE_PACKAGES: {}", DIR.parent.parent)
            logger.debug("PATH: {}", sys.path)

        # Add the FindPython backport if needed
        if self.config.cmake.version < self.settings.backport.find_python:
            fp_dir = Path(find_python.__file__).parent.resolve()
            self.config.module_dirs.append(fp_dir)
            logger.debug("FindPython backport activated at {}", fp_dir)

        current_gen = self.get_generator(*configure_args)
        local_def = set_environment_for_gen(
            current_gen, self.config.cmake, self.config.env, self.settings.ninja
        )
        cmake_defines.update(local_def)

        cache_config: dict[str, str | Path | bool] = {
            "SKBUILD": "2",
            "SKBUILD_CORE_VERSION": __version__,
        }

        if name is not None:
            canonical_name = name.replace("-", "_").replace(".", "_")
            cache_config["SKBUILD_PROJECT_NAME"] = canonical_name
        if version is not None:
            cache_config["SKBUILD_PROJECT_VERSION"] = ".".join(
                str(v) for v in version.release
            )
            cache_config["SKBUILD_PROJECT_VERSION_FULL"] = str(version)

        if limited_api is None:
            if self.settings.wheel.py_api.startswith("cp3"):
                target_minor_version = int(self.settings.wheel.py_api[3:])
                limited_api = target_minor_version <= sys.version_info.minor
            else:
                limited_api = False

        if limited_api and sys.implementation.name != "cpython":
            limited_api = False
            logger.info("PyPy doesn't support the Limited API, ignoring")

        if limited_api and sysconfig.get_config_var("Py_GIL_DISABLED"):
            limited_api = False
            logger.info(
                "Free-threaded Python doesn't support the Limited API currently, ignoring"
            )

        python_library = get_python_library(self.config.env, abi3=False)
        python_sabi_library = (
            get_python_library(self.config.env, abi3=True) if limited_api else None
        )
        python_include_dir = get_python_include_dir()
        numpy_include_dir = get_numpy_include_dir()

        # Classic Find Python
        cache_config["PYTHON_EXECUTABLE"] = sys.executable
        cache_config["PYTHON_INCLUDE_DIR"] = python_include_dir
        if python_library:
            cache_config["PYTHON_LIBRARY"] = python_library

        # Modern Find Python
        for prefix in ("Python", "Python3"):
            cache_config[f"{prefix}_EXECUTABLE"] = sys.executable
            cache_config[f"{prefix}_ROOT_DIR"] = sys.prefix
            cache_config[f"{prefix}_INCLUDE_DIR"] = python_include_dir
            cache_config[f"{prefix}_FIND_REGISTRY"] = "NEVER"
            # FindPython may break if this is set - only useful on Windows
            if python_library and sysconfig.get_platform().startswith("win"):
                cache_config[f"{prefix}_LIBRARY"] = python_library
            if python_sabi_library and sysconfig.get_platform().startswith("win"):
                cache_config[f"{prefix}_SABI_LIBRARY"] = python_sabi_library
            if numpy_include_dir:
                cache_config[f"{prefix}_NumPy_INCLUDE_DIR"] = numpy_include_dir

        cache_config["SKBUILD_SOABI"] = get_soabi(self.config.env, abi3=limited_api)

        # Allow CMakeLists to detect this is supposed to be a limited ABI build
        cache_config["SKBUILD_SABI_COMPONENT"] = (
            "Development.SABIModule" if limited_api else ""
        )

        # Allow users to detect the version requested in settings
        py_api = self.settings.wheel.py_api
        cache_config["SKBUILD_SABI_VERSION"] = (
            f"{py_api[2]}.{py_api[3:]}"
            if limited_api and py_api.startswith("cp")
            else ""
        )

        if cache_entries:
            cache_config.update(cache_entries)

        self.config.init_cache(cache_config)

        if sys.platform.startswith("darwin"):
            # Cross-compile support for macOS - respect ARCHFLAGS if set
            archs = get_archs(self.config.env)
            if archs:
                cmake_defines["CMAKE_OSX_ARCHITECTURES"] = ";".join(archs)

        # Add the pre-defined or passed CMake defines
        cmake_defines.update(self.settings.cmake.define)

        self.config.configure(
            preset=self.settings.cmake.preset,
            defines=cmake_defines,
            cmake_args=[*self.get_cmake_args(), *configure_args],
        )

    def build(self, build_args: Sequence[str]) -> None:
        build_tool_args = self.settings.build.tool_args
        if build_tool_args:
            build_args = [*build_args, "--", *build_tool_args]

        self.config.build(
            build_args=build_args,
            targets=self.settings.build.targets,
            verbose=self.settings.build.verbose,
        )

    def install(self, install_dir: Path | None) -> None:
        """
        Install to a path.

        Warning: if a package hard-codes CMAKE_INSTALL_PREFIX in the install
        commands, this will not rewrite those; set that variable when
        configuring for maximum compatibility.
        """
        components = self.settings.install.components
        strip = self.settings.install.strip
        assert strip is not None
        self.config.install(install_dir, strip=strip, components=components)
