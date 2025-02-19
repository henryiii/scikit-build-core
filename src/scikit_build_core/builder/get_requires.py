from __future__ import annotations

import dataclasses
import functools
import importlib.util
import os
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from packaging.tags import sys_tags

from .._compat import tomllib
from .._logging import logger
from ..program_search import (
    best_program,
    get_cmake_programs,
    get_make_programs,
    get_ninja_programs,
)
from ..resources import resources
from ..settings._load_provider import load_provider
from ..settings.skbuild_read_settings import SettingsReader

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from .._compat.typing import Self
    from ..settings.skbuild_model import ScikitBuildSettings

__all__ = ["GetRequires"]


def __dir__() -> list[str]:
    return __all__


def _uses_ninja_generator(settings: ScikitBuildSettings) -> bool | None:
    """
    Returns True if Ninja is set, False if something else is set, and None
    otherwise.
    """
    gen_args = [arg[2:] for arg in settings.cmake.args if arg.startswith("-G")]
    if gen_args:
        return any("Ninja" in gen for gen in gen_args)

    if "CMAKE_GENERATOR" in os.environ:
        return "Ninja" in os.environ["CMAKE_GENERATOR"]

    return None


@functools.lru_cache(maxsize=2)
def known_wheels(name: Literal["ninja", "cmake"]) -> frozenset[str]:
    with resources.joinpath("known_wheels.toml").open("rb") as f:
        return frozenset(tomllib.load(f)["tool"]["scikit-build"][name]["known-wheels"])


@functools.lru_cache(maxsize=2)
def is_known_platform(platforms: frozenset[str]) -> bool:
    return any(tag.platform in platforms for tag in sys_tags())


def _load_scikit_build_settings(
    config_settings: Mapping[str, list[str] | str] | None = None,
) -> ScikitBuildSettings:
    return SettingsReader.from_file("pyproject.toml", config_settings).settings


class RootPath(type(Path())):  # type: ignore[misc]
    """Handle ``{root:uri}`` like formatting similar to ``hatchling``."""

    def __format__(self: Path, fmt: str) -> str:
        command, _, rest = fmt.partition(":")
        if command == "parent":
            return self.parent.__format__(rest)
        if command == "uri" and rest == "":
            return self.absolute().as_uri()
        if command == "" and rest == "":
            return str(self)
        msg = f"Could not handle format: {fmt}"
        raise ValueError(msg)


@dataclasses.dataclass(frozen=True)
class GetRequires:
    settings: ScikitBuildSettings = dataclasses.field(
        default_factory=_load_scikit_build_settings
    )

    @classmethod
    def from_config_settings(
        cls, config_settings: Mapping[str, list[str] | str] | None
    ) -> Self:
        return cls(_load_scikit_build_settings(config_settings))

    def cmake(self) -> Generator[str, None, None]:
        if self.settings.fail or os.environ.get("CMAKE_EXECUTABLE", ""):
            return

        cmake_verset = self.settings.cmake.version

        # If the module is already installed (via caching the build
        # environment, for example), we will use that
        if importlib.util.find_spec("cmake") is not None:
            yield f"cmake{cmake_verset}"
            return

        cmake = best_program(get_cmake_programs(module=False), version=cmake_verset)
        if cmake is None:
            yield f"cmake{cmake_verset}"
            return
        logger.debug("Found system CMake: {} - not requiring PyPI package", cmake)

    def ninja(self) -> Generator[str, None, None]:
        # Check to see if Ninja is clearly not used
        use_ninja = _uses_ninja_generator(self.settings)
        if use_ninja is False:
            return

        # On Windows MSVC, Ninja is not default
        if self.settings.fail or (
            sysconfig.get_platform().startswith("win") and use_ninja is None
        ):
            return

        # If CMAKE_MAKE_PROGRAM is set, don't add anything, someone already knows what they want
        if os.environ.get("CMAKE_MAKE_PROGRAM", ""):
            return

        ninja_verset = self.settings.ninja.version

        # If the module is already installed (via caching the build
        # environment, for example), we will use that
        if importlib.util.find_spec("ninja") is not None:
            yield f"ninja{ninja_verset}"
            return

        ninja = best_program(get_ninja_programs(module=False), version=ninja_verset)
        if ninja is not None:
            logger.debug("Found system Ninja: {} - not requiring PyPI package", ninja)
            return

        if (
            self.settings.ninja.make_fallback
            and not is_known_platform(known_wheels("ninja"))
            and list(get_make_programs())
        ):
            logger.debug(
                "Found system Make & not on known platform - not requiring PyPI package for Ninja"
            )
            return
        yield f"ninja{ninja_verset}"

    def dynamic_metadata(self) -> Generator[str, None, None]:
        if self.settings.fail:
            return

        for build_require in self.settings.build.build_requires:
            yield build_require.format(root=RootPath())

        for dynamic_metadata in self.settings.metadata.values():
            if "provider" in dynamic_metadata:
                config = dynamic_metadata.copy()
                provider = config.pop("provider")
                provider_path = config.pop("provider-path", None)
                module = load_provider(provider, provider_path)
                yield from getattr(
                    module, "get_requires_for_dynamic_metadata", lambda _: []
                )(config)
