from __future__ import annotations

__lazy_modules__ = {
    "importlib.util",
    "pathlib",
    "shlex",
    "sysconfig",
    "typing",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._compat",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._logging",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._variants",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.format",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.program_search",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.settings.skbuild_read_settings",
    f"{__spec__.parent}._known_wheels",
    f"{__spec__.parent}._load_provider",
    f"{__spec__.parent}.generator",
}

import dataclasses
import importlib.util
import os
import shlex
import sysconfig
from pathlib import Path
from typing import Any, Literal

from .._compat import tomllib
from .._logging import logger
from .._variants import variant_build_requires
from ..format import pyproject_format
from ..program_search import (
    best_program,
    get_cmake_programs,
    get_make_programs,
    get_ninja_programs,
)
from ..settings.skbuild_read_settings import SettingsReader
from ._known_wheels import is_known_platform, known_wheels
from ._load_provider import load_dynamic_metadata, load_provider
from .generator import resolve_generator

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

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
    args = [*settings.cmake.args, *shlex.split(os.environ.get("CMAKE_ARGS", ""))]
    generator = resolve_generator(args, settings.cmake.define, os.environ)
    if generator is None:
        return None
    return "Ninja" in generator


def _load_scikit_build_settings(
    config_settings: Mapping[str, list[str] | str] | None = None,
    state: Literal["sdist", "wheel", "editable"] = "sdist",
) -> ScikitBuildSettings:
    return SettingsReader.from_file(
        "pyproject.toml", config_settings, state=state
    ).settings


def _read_pyproject() -> dict[str, Any]:
    try:
        with Path("pyproject.toml").open("rb") as f:
            return tomllib.load(f)
    except FileNotFoundError:
        return {}


def _read_dynamic_metadata() -> list[dict[str, Any]]:
    """Read the top-level ``[[tool.dynamic-metadata]]`` entries (0.3)."""
    entries: list[dict[str, Any]] = (
        _read_pyproject().get("tool", {}).get("dynamic-metadata", [])
    )
    return entries


def _read_variant_table() -> dict[str, Any]:
    table: dict[str, Any] = _read_pyproject().get("variant", {})
    return table


@dataclasses.dataclass(frozen=True)
class GetRequires:
    settings: ScikitBuildSettings = dataclasses.field(
        default_factory=_load_scikit_build_settings
    )
    dynamic_metadata_entries: Sequence[dict[str, Any]] = dataclasses.field(
        default_factory=_read_dynamic_metadata
    )
    variant_table: Mapping[str, Any] = dataclasses.field(
        default_factory=_read_variant_table
    )

    @classmethod
    def from_config_settings(
        cls,
        config_settings: Mapping[str, list[str] | str] | None,
        state: Literal["sdist", "wheel", "editable"] = "sdist",
    ) -> Self:
        reader = SettingsReader.from_file(
            "pyproject.toml", config_settings, state=state
        )
        return cls(reader.settings, reader.dynamic_metadata, reader.variant)

    def cmake(self) -> Generator[str, None, None]:
        if self.settings.fail or os.environ.get("CMAKE_EXECUTABLE", ""):
            return

        cmake_verset = self.settings.cmake.version

        # If the module is already installed (via caching the build
        # environment, for example), we will use that. A namespace package
        # (a bare "cmake" directory on sys.path) has no origin.
        cmake_spec = importlib.util.find_spec("cmake")
        if cmake_spec is not None and cmake_spec.origin is not None:
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
        # environment, for example), we will use that. A namespace package
        # (a bare "ninja" directory on sys.path) has no origin.
        ninja_spec = importlib.util.find_spec("ninja")
        if ninja_spec is not None and ninja_spec.origin is not None:
            yield f"ninja{ninja_verset}"
            return

        ninja = best_program(get_ninja_programs(module=False), version=ninja_verset)
        if ninja is not None:
            logger.debug("Found system Ninja: {} - not requiring PyPI package", ninja)
            return

        # Only fall back to Make if the generator wasn't explicitly set to
        # Ninja - Make can't substitute for a forced Ninja generator (#953).
        if (
            use_ninja is None
            and self.settings.ninja.make_fallback
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

        for build_require in self.settings.build.requires:
            yield build_require.format(
                **pyproject_format(
                    settings=self.settings,
                )
            )

        # Deprecated tool.scikit-build.metadata table.
        for dynamic_metadata in self.settings.metadata.values():
            if "provider" in dynamic_metadata:
                config = dynamic_metadata.copy()
                provider = config.pop("provider")
                provider_path = config.pop("provider-path", None)
                module = load_provider(provider, provider_path)
                yield from getattr(
                    module, "get_requires_for_dynamic_metadata", lambda _: []
                )(config)

        # Standard top-level [[tool.dynamic-metadata]] entries (0.3).
        for provider, settings in load_dynamic_metadata(self.dynamic_metadata_entries):
            get_requires = getattr(provider, "get_requires_for_dynamic_metadata", None)
            if get_requires is not None:
                yield from get_requires(settings)

    def variants(self) -> Generator[str, None, None]:
        if self.settings.fail:
            return

        yield from variant_build_requires(self.settings, self.variant_table)
