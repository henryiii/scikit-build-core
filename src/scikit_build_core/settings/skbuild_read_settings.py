from __future__ import annotations

import copy
import dataclasses
import difflib
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, TypeVar

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .. import __version__
from .._compat import tomllib
from .._logging import logger, rich_error, rich_print, rich_warning
from ..errors import CMakeConfigError
from .auto_cmake_version import find_min_cmake_version
from .auto_requires import get_min_requires
from .skbuild_model import CMakeSettings, NinjaSettings, ScikitBuildSettings
from .skbuild_overrides import process_overides
from .sources import ConfSource, EnvSource, SourceChain, TOMLSource

if TYPE_CHECKING:
    import os
    from collections.abc import Generator, Mapping


__all__ = ["SettingsReader"]


def __dir__() -> list[str]:
    return __all__


T = TypeVar("T")


def _handle_minimum_version(
    dc: CMakeSettings | NinjaSettings,
    minimum_version: Version | None,
    default: str = "",
) -> None:
    """
    Handle the minimum version option. Supports scikit-build-core < 0.8 style
    minimum_version. Prints an error message and exits.
    """
    name = "cmake" if isinstance(dc, CMakeSettings) else "ninja"

    version_default = next(
        iter(f for f in dataclasses.fields(dc) if f.name == "version")
    ).default
    if version_default is None:
        if not default:
            msg = "Default version must be provided for this function if None is the default"
            raise AssertionError(msg)
        version_default = SpecifierSet(f">={default}")

    # Check for minimum_version < 0.8 and the modern version setting
    if (
        dc.version is not None
        and dc.version != version_default
        and minimum_version is not None
        and minimum_version < Version("0.8")
    ):
        rich_error(
            f"Cannot set {name}.version if minimum-version is set to less than 0.8 (which is where it was introduced)"
        )

    # Backwards compatibility for minimum_version
    if dc.minimum_version is not None:
        msg = f"Use {name}.version instead of {name}.minimum-version with scikit-build-core >= 0.8"
        if minimum_version is None:
            rich_warning(msg)
        elif minimum_version >= Version("0.8"):
            rich_error(msg)

        if dc.version is not None and dc.version != version_default:
            rich_error(
                f"Cannot set both {name}.minimum_version and {name}.version; use version only for scikit-build-core >= 0.8."
            )

        dc.version = SpecifierSet(f">={dc.minimum_version}")

    if dc.version is None:
        dc.version = SpecifierSet(f">={default}")


def _handle_move(
    before_name: str,
    before: T | None,
    after_name: str,
    after: T,
    minimum_version: Version | None,
    introduced_in: Version,
) -> T:
    """
    Backward_compat for moving names around. The default must be false-like.
    """

    if after and minimum_version is not None and minimum_version < introduced_in:
        rich_error(
            f"Cannot set {after_name} if minimum-version is set to less than {introduced_in} (which is where it was introduced)"
        )

    if (
        before is not None
        and minimum_version is not None
        and minimum_version >= introduced_in
    ):
        rich_error(
            f"Cannot set {before_name} if minimum-version is set to {introduced_in} or higher"
        )

    if before is not None and after:
        rich_error(f"Cannot set {before_name} and {after_name} at the same time")

    if before is None:
        return after

    if minimum_version is None:
        rich_warning(
            f"Use {after_name} instead of {before_name} for scikit-build-core >= {introduced_in}"
        )

    return before


class SettingsReader:
    def __init__(
        self,
        pyproject: dict[str, Any],
        config_settings: Mapping[str, str | list[str]],
        *,
        state: Literal[
            "sdist", "wheel", "editable", "metadata_wheel", "metadata_editable"
        ],
        extra_settings: Mapping[str, Any] | None = None,
        verify_conf: bool = True,
        env: Mapping[str, str] | None = None,
        retry: bool = False,
    ) -> None:
        self.state = state

        # Handle overrides
        pyproject = copy.deepcopy(pyproject)
        self.overrides = process_overides(
            pyproject.get("tool", {}).get("scikit-build", {}),
            state=state,
            env=env,
            retry=retry,
        )

        # Support for minimum-version='build-system.requires'
        tmp_min_v = (
            pyproject.get("tool", {})
            .get("scikit-build", {})
            .get("minimum-version", None)
        )
        if tmp_min_v == "build-system.requires":
            reqlist = pyproject["build-system"]["requires"]
            min_v = get_min_requires("scikit-build-core", reqlist)
            if min_v is None:
                rich_error(
                    "scikit-build-core needs a min version in "
                    "build-system.requires to use minimum-version='build-system.requires'"
                )
            pyproject["tool"]["scikit-build"]["minimum-version"] = str(min_v)
        toml_srcs = [TOMLSource("tool", "scikit-build", settings=pyproject)]

        # Support for cmake.version='CMakeLists.txt'
        # We will save the value for now since we need the CMakeLists location
        force_auto_cmake = (
            pyproject.get("tool", {})
            .get("scikit-build", {})
            .get("cmake", {})
            .get("version", None)
        ) == "CMakeLists.txt"
        if force_auto_cmake:
            del pyproject["tool"]["scikit-build"]["cmake"]["version"]

        if extra_settings is not None:
            extra_skb = copy.deepcopy(dict(extra_settings))
            process_overides(extra_skb, state=state, env=env, retry=retry)
            toml_srcs.insert(0, TOMLSource(settings=extra_skb))

        prefixed = {
            k: v for k, v in config_settings.items() if k.startswith("skbuild.")
        }
        remaining = {
            k: v for k, v in config_settings.items() if not k.startswith("skbuild.")
        }
        self.sources = SourceChain(
            EnvSource("SKBUILD"),
            ConfSource("skbuild", settings=prefixed, verify=verify_conf),
            ConfSource(settings=remaining, verify=verify_conf),
            *toml_srcs,
            prefixes=["tool", "scikit-build"],
        )
        self.settings = self.sources.convert_target(ScikitBuildSettings)

        if self.settings.minimum_version:
            current_version = Version(__version__)
            minimum_version = self.settings.minimum_version
            if current_version < minimum_version:
                msg = (
                    f"scikit-build-core version {__version__} is too old. "
                    f"Minimum required version is {self.settings.minimum_version}."
                )
                raise CMakeConfigError(msg)

        if isinstance(self.settings.wheel.packages, dict):
            for key, value in self.settings.wheel.packages.items():
                if Path(key).name != Path(value).name:
                    rich_error(
                        "wheel.packages table must match in the last component of the paths"
                    )

        if self.settings.editable.rebuild:
            if self.settings.editable.mode == "inplace":
                rich_error("editable rebuild is incompatible with inplace mode")

            if not self.settings.build_dir:
                rich_error("editable mode with rebuild requires build-dir")

        install_policy = (
            self.settings.minimum_version is None
            or self.settings.minimum_version >= Version("0.5")
        )
        if self.settings.install.strip is None:
            self.settings.install.strip = (
                install_policy
                and self.settings.cmake.build_type in {"Release", "MinSizeRel"}
            )

        # If we noted earlier that auto-cmake was requested, handle it now
        if (
            self.settings.cmake.version is None
            and self.settings.cmake.minimum_version is None
            and (
                self.settings.minimum_version is None
                or self.settings.minimum_version >= Version("0.10")
            )
        ):
            cmake_path = self.settings.cmake.source_dir / "CMakeLists.txt"
            try:
                with cmake_path.open(encoding="utf-8-sig") as f:
                    new_min_cmake = find_min_cmake_version(f.read())
            except FileNotFoundError:
                new_min_cmake = "3.15"
                rich_warning(
                    "CMakeLists.txt not found when looking for minimum CMake version. "
                    "Report this or (and) set manually to avoid this warning. Using 3.15 as a fall-back."
                )

            if new_min_cmake is None:
                if force_auto_cmake:
                    rich_error(
                        "Minimum CMake version set as "
                        "'CMakeLists.txt' wasn't able to find minimum version setting. "
                        "If the CMakeLists.txt is valid, this might be a bug in our search algorithm."
                    )
                rich_warning(
                    "Minimum CMake version not found in CMakeLists.txt. "
                    "If the CMakeLists.txt is valid, this might be a bug in our search algorithm. Report "
                    "this or (and) set manually to avoid this warning."
                )
                new_min_cmake = "3.15"
            if Version(new_min_cmake) < Version("3.15"):
                rich_warning(
                    "Minimum CMake version set as 'CMakeLists.txt' is less than 3.15. "
                    "This is not supported by scikit-build-core; set manually or increase to avoid this warning."
                )
                new_min_cmake = "3.15"
            self.settings.cmake.version = SpecifierSet(f">={new_min_cmake}")

        default_cmake_minimum = "3.15"
        if self.settings.cmake.preset:
            default_cmake_minimum = "3.19"

        _handle_minimum_version(
            self.settings.cmake, self.settings.minimum_version, default_cmake_minimum
        )
        _handle_minimum_version(self.settings.ninja, self.settings.minimum_version)

        self.settings.build.verbose = _handle_move(
            "cmake.verbose",
            self.settings.cmake.verbose,
            "build.verbose",
            self.settings.build.verbose,
            self.settings.minimum_version,
            Version("0.10"),
        )
        self.settings.build.targets = _handle_move(
            "cmake.targets",
            self.settings.cmake.targets,
            "build.targets",
            self.settings.build.targets,
            self.settings.minimum_version,
            Version("0.10"),
        )

    def unrecognized_options(self) -> Generator[str, None, None]:
        return self.sources.unrecognized_options(ScikitBuildSettings)

    def suggestions(self, index: int) -> dict[str, list[str]]:
        all_options = list(self.sources[index].all_option_names(ScikitBuildSettings))
        result: dict[str, list[str]] = {
            k: [] for k in self.sources[index].unrecognized_options(ScikitBuildSettings)
        }
        for option in result:
            possibilities = {
                ".".join(k.split(".")[: option.count(".") + 1]) for k in all_options
            }
            result[option] = difflib.get_close_matches(option, possibilities, n=3)

        return result

    def print_suggestions(self) -> None:
        for index in (1, 2, 3):
            name = {1: "config-settings", 2: "config-settings", 3: "pyproject.toml"}[
                index
            ]
            suggestions_dict = self.suggestions(index)
            if suggestions_dict:
                rich_print(
                    f"{{bold.red}}ERROR:{{normal}} Unrecognized options in {name}:"
                )
                for option, suggestions in suggestions_dict.items():
                    rich_print(f"  {{red}}{option}", end="")
                    if suggestions:
                        sugstr = ", ".join(suggestions)
                        rich_print(f"{{yellow}} -> Did you mean: {sugstr}?", end="")
                    rich_print()

    def validate_may_exit(self) -> None:
        unrecognized = list(self.unrecognized_options())
        if unrecognized:
            if self.settings.strict_config:
                sys.stdout.flush()
                self.print_suggestions()
                raise SystemExit(7)
            logger.warning("Unrecognized options: {}", ", ".join(unrecognized))

        for key, value in self.settings.metadata.items():
            if "provider" not in value:
                sys.stdout.flush()
                rich_error(f"provider= must be provided in {key!r}:")
            if not self.settings.experimental and (
                "provider-path" in value
                or not value["provider"].startswith("scikit_build_core.")
            ):
                sys.stdout.flush()
                rich_error(
                    "experimental must be enabled currently to use plugins not provided by scikit-build-core"
                )

        for gen in self.settings.generate:
            if not gen.template and not gen.template_path:
                sys.stdout.flush()
                rich_error("template= or template-path= must be provided in generate")

    @classmethod
    def from_file(
        cls,
        pyproject_path: os.PathLike[str] | str,
        config_settings: Mapping[str, str | list[str]] | None = None,
        *,
        state: Literal[
            "sdist", "wheel", "editable", "metadata_wheel", "metadata_editable"
        ] = "sdist",
        verify_conf: bool = True,
        extra_settings: Mapping[str, Any] | None = None,
        env: Mapping[str, str] | None = None,
        retry: bool = False,
    ) -> SettingsReader:
        with Path(pyproject_path).open("rb") as f:
            pyproject = tomllib.load(f)

        return cls(
            pyproject,
            config_settings or {},
            verify_conf=verify_conf,
            state=state,
            extra_settings=extra_settings,
            env=env,
            retry=retry,
        )
