from __future__ import annotations

import re
import subprocess
import sys
import sysconfig
from typing import TYPE_CHECKING

from .._logging import logger
from ..errors import NinjaNotFoundError
from ..program_search import best_program, get_make_programs, get_ninja_programs
from .sysconfig import get_cmake_platform

if TYPE_CHECKING:
    from collections.abc import Mapping, MutableMapping

    from ..cmake import CMake
    from ..settings.skbuild_model import NinjaSettings

__all__ = ["set_environment_for_gen"]


def __dir__() -> list[str]:
    return __all__


def parse_help_default(txt: str) -> str | None:
    """
    Parses the default generator from the output of cmake --help.
    """

    lines: list[str] = re.findall(
        r"^\*\s*(.*?)(?:\s*\[arch\])?\s*= Generate", txt, re.MULTILINE
    )
    if len(lines) != 1:
        return None

    return lines[0]


def get_default_from_cmake(cmake: CMake) -> str | None:
    """
    Returns the default generator for the current platform from CMake's output.
    None if it cannot be determined.
    """

    result = subprocess.run(
        [str(cmake.cmake_path), "--help"],
        check=False,
        capture_output=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None

    return parse_help_default(result.stdout)


def get_default(cmake: CMake) -> str | None:
    """
    Returns the computed default for the current platform.
    """
    generator = get_default_from_cmake(cmake)

    # Non-MSVC Windows platforms require Ninja
    is_msvc_platform = sysconfig.get_platform().startswith("win")
    if sys.platform.startswith("win") and not is_msvc_platform:
        return "Ninja"

    # Try Ninja if it is available, even if make is CMake default
    if generator == "Unix Makefiles":
        return "Ninja"

    return generator


def set_environment_for_gen(
    generator: str | None,
    cmake: CMake,
    env: MutableMapping[str, str],
    ninja_settings: NinjaSettings,
) -> Mapping[str, str]:
    """
    This function modifies the environment as needed to safely set a generator.
    You should have used CMAKE_GENERATOR already to get the input generator
    string.

    A reasonable default generator is set if the environment does not already
    have one set; if ninja is present, ninja will be used over make on Unix.

    If gen is not None, then that will be the target generator.
    """
    # TODO: How does make_fallback interact when `preset` is set?
    allow_make_fallback = ninja_settings.make_fallback

    if generator:
        logger.debug("Set generator: {}", generator)
        allow_make_fallback = False
    else:
        generator = get_default(cmake) or ""
        if generator:
            logger.debug("Default generator: {}", generator)

    if sysconfig.get_platform().startswith("win") and "Visual Studio" in generator:
        # This must also be set when *_PLATFORM is set.
        env.setdefault("CMAKE_GENERATOR", generator)
        env.setdefault("CMAKE_GENERATOR_PLATFORM", get_cmake_platform(env))
        return {}

    # Set Python's recommended CC and CXX if not already set by the user
    if "CC" not in env:
        cc = sysconfig.get_config_var("CC")
        if cc:
            env["CC"] = cc

    if "CXX" not in env:
        cxx = sysconfig.get_config_var("CXX")
        if cxx:
            env["CXX"] = cxx

    if (generator or "Ninja") == "Ninja":
        ninja = best_program(get_ninja_programs(), version=ninja_settings.version)

        if ninja is not None:
            env.setdefault("CMAKE_GENERATOR", "Ninja")
            logger.debug("CMAKE_GENERATOR: Using ninja: {}", ninja.path)
            return {"CMAKE_MAKE_PROGRAM": str(ninja.path)}

        msg = "Ninja is required to build"
        if not allow_make_fallback:
            raise NinjaNotFoundError(msg)

        msg = "Ninja or make is required to build"
        make_programs = list(get_make_programs())
        if not make_programs:
            raise NinjaNotFoundError(msg)

        env.setdefault("CMAKE_GENERATOR", "Unix Makefiles")
        logger.debug("CMAKE_GENERATOR: Using make: {}", make_programs[0])
        return {"CMAKE_MAKE_PROGRAM": str(make_programs[0])}

    return {}
