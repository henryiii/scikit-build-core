from __future__ import annotations

__lazy_modules__ = {
    "copy",
    "dataclasses",
    "difflib",
    "packaging.specifiers",
    "packaging.version",
    "pathlib",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._compat",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._logging",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._variants",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.ast.ast",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.errors",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.utils.typing",
    f"{__spec__.parent}._load_entrypoint_config",
    f"{__spec__.parent}.auto_cmake_version",
    f"{__spec__.parent}.auto_requires",
    f"{__spec__.parent}.config_settings",
    f"{__spec__.parent}.skbuild_model",
    f"{__spec__.parent}.skbuild_overrides",
    f"{__spec__.parent}.sources",
}

import copy
import dataclasses
import difflib
import os
import sys
from pathlib import Path
from typing import Any, Literal, TypeVar

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .. import __version__
from .._compat import tomllib
from .._logging import logger, rich_error, rich_print, rich_warning
from .._variants import validate_variant_settings
from ..ast.ast import ParseError
from ..errors import CMakeConfigError
from ..utils.typing import get_target_raw_type
from ._load_entrypoint_config import load_config_providers
from .auto_cmake_version import find_min_cmake_version
from .auto_requires import get_min_requires
from .config_settings import (
    load_declarations,
    resolve_config_settings,
    resolve_define_references,
)
from .skbuild_model import (
    BuildSettings,
    CMakeSettings,
    NinjaSettings,
    ScikitBuildSettings,
    normalize_build_types,
)
from .skbuild_overrides import process_overrides, strtobool
from .sources import ConfSource, EnvSource, Source, SourceChain, TOMLSource

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Generator, Mapping

    from .skbuild_overrides import OverrideRecord


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

    # Backwards compatibility for minimum_version. It is only honored when an
    # old minimum-version (< 0.8) explicitly opts back into it; unset (latest)
    # or >= 0.8 is an error.
    if dc.minimum_version is not None:
        msg = f"Use {name}.version instead of {name}.minimum-version with scikit-build-core >= 0.8"
        if minimum_version is None or minimum_version >= Version("0.8"):
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
    *,
    static: bool,
) -> T:
    """
    Backward_compat for moving names around. The default must be false-like.
    """
    if (
        static
        and after
        and minimum_version is not None
        and minimum_version < introduced_in
    ):
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
        if not static:
            return after
        rich_error(f"Cannot set {before_name} and {after_name} at the same time")

    if before is None:
        return after

    # The renamed field is only honored when an old minimum-version (<
    # introduced_in) explicitly opts back into it; unset (latest) is an error.
    if minimum_version is None:
        rich_error(
            f"Use {after_name} instead of {before_name} for scikit-build-core >= {introduced_in}"
        )

    return before


def _validate_overrides(
    settings: ScikitBuildSettings,
    overrides: dict[str, OverrideRecord],
    *,
    dynamic_sources: tuple[Source, ...],
    toml_sources: tuple[Source, ...],
) -> None:
    """
    Validate all fields with any override information.

    ``dynamic_sources`` are the sources that may legitimately set
    ``override_only`` fields at build time (env vars, PEP 517 config-settings,
    and machine-level entry-point config); ``toml_sources`` are the static
    ``pyproject.toml`` (and ``extra_settings``) tables where ``override_only``
    fields are forbidden outside of an ``[[overrides]]`` section.
    """

    def validate_field(
        field: dataclasses.Field[Any],
        value: Any,
        prefix: str = "",
        path: tuple[str, ...] = (),
        record: OverrideRecord | None = None,
    ) -> None:
        """Do the actual validation."""
        # Check if we had a hard-coded value in the record
        conf_key = field.name.replace("_", "-")
        if field.metadata.get("override_only", False):
            # has_item needs dict-presence semantics for dict-valued fields,
            # since some sources represent dict entries as nested keys.
            is_dict = get_target_raw_type(field.type) is dict
            # override-only fields may be set dynamically via env vars or
            # config-settings; only static pyproject.toml values are forbidden.
            if any(
                source.has_item(*path, field.name, is_dict=is_dict)
                for source in dynamic_sources
            ):
                return

            # Decide whether the value was actually hard-coded in pyproject.toml.
            # We can't rely on `value is not None`, since some override-only
            # fields have non-None falsy defaults (e.g. [] or False), so we ask
            # the TOML sources whether the key is really present.
            if record is not None:
                original_value = record.original_value
            elif any(
                source.has_item(*path, field.name, is_dict=is_dict)
                for source in toml_sources
            ):
                original_value = value
            else:
                original_value = None

            if original_value is not None:
                msg = f"{prefix}{conf_key} is not allowed to be hard-coded in the pyproject.toml file"
                if settings.strict_config:
                    sys.stdout.flush()
                    rich_print(f"{{bold.red}}ERROR:{{normal}} {msg}")
                    raise SystemExit(7)
                logger.warning(msg)

    def validate_field_recursive(
        obj: Any,
        prefix: str = "",
        path: tuple[str, ...] = (),
    ) -> None:
        """Navigate through all the keys and validate each field."""
        for field in dataclasses.fields(obj):
            conf_key = field.name.replace("_", "-")
            value = getattr(obj, field.name)
            # Do the validation of the current field
            validate_field(
                field=field,
                value=value,
                prefix=prefix,
                path=path,
                record=overrides.get(f"{prefix}{conf_key}"),
            )
            if dataclasses.is_dataclass(value):
                validate_field_recursive(
                    obj=value,
                    prefix=f"{prefix}{conf_key}.",
                    path=(*path, field.name),
                )

    # Navigate all fields starting from the top-level
    validate_field_recursive(obj=settings)


class SettingsReader:
    def __init__(
        self,
        pyproject: dict[str, Any],
        config_settings: Mapping[str, str | list[str] | bool],
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
        environ = os.environ if env is None else env

        pyproject = copy.deepcopy(pyproject)
        tool_skb = pyproject.get("tool", {}).get("scikit-build", {})

        # Project-declared config-settings: pop the declaration table (like
        # ``overrides``, it is not a settings field) and resolve values before
        # overrides so ``if.config-setting`` can match them.
        self.config_setting_decls = load_declarations(
            tool_skb.pop("config-setting", {})
        )
        self.custom_config_settings = resolve_config_settings(
            self.config_setting_decls, config_settings, environ
        )

        def process_table(
            skb: dict[str, Any], declaration_error: str
        ) -> tuple[set[str], dict[str, OverrideRecord]]:
            """
            Apply overrides to one settings table, reject stray config-setting
            declarations (the static table was popped from pyproject.toml above,
            so any survivor is misplaced), and resolve define references.
            """
            matched, overridden = process_overrides(
                skb,
                state=state,
                env=env,
                retry=retry,
                config_settings=self.custom_config_settings,
            )
            if "config-setting" in skb:
                rich_error(declaration_error)
            resolve_define_references(skb, self.custom_config_settings)
            return matched, overridden

        # Handle overrides
        self.overrides, self.overridden_items = process_table(
            tool_skb, "config-setting declarations may not be set by overrides"
        )

        # Support for minimum-version='build-system.requires'
        tmp_min_v = tool_skb.get("minimum-version")
        if tmp_min_v == "build-system.requires":
            reqlist = pyproject["build-system"]["requires"]
            min_v = get_min_requires("scikit-build-core", reqlist)
            if min_v is None:
                rich_error(
                    "scikit-build-core needs a min version in "
                    "build-system.requires to use minimum-version='build-system.requires'"
                )
            tool_skb["minimum-version"] = str(min_v)
        toml_srcs = [TOMLSource("tool", "scikit-build", settings=pyproject)]
        # Human-readable names parallel to ``toml_srcs`` (used by suggestions).
        toml_src_names = ["pyproject.toml"]

        # Standard top-level [[tool.dynamic-metadata]] entries (0.3). Kept so
        # callers do not have to parse pyproject.toml a second time.
        self.dynamic_metadata: list[dict[str, Any]] = pyproject.get("tool", {}).get(
            "dynamic-metadata", []
        )
        self.variant: dict[str, Any] = pyproject.get("variant", {})

        # Support for cmake.version='CMakeLists.txt'
        # We will save the value for now since we need the CMakeLists location
        # A malformed non-table cmake value is left for conversion to report.
        cmake_table = tool_skb.get("cmake", {})
        force_auto_cmake = (
            isinstance(cmake_table, dict)
            and cmake_table.get("version", None) == "CMakeLists.txt"
        )
        if force_auto_cmake:
            del cmake_table["version"]

        if extra_settings is not None:
            extra_skb = copy.deepcopy(dict(extra_settings))
            extra_matched, extra_overridden = process_table(
                extra_skb,
                "config-setting declarations are only allowed in pyproject.toml",
            )
            self.overrides |= extra_matched
            self.overridden_items.update(extra_overridden)
            toml_srcs.insert(0, TOMLSource(settings=extra_skb))
            toml_src_names.insert(0, "extra settings")

        # Configuration contributed by installed packages via the
        # "scikit-build-core.config.default" / ".override" entry-point groups
        # (e.g. a Linux distro shipping build defaults for all its package
        # builds). The group selects the precedence level: "override" sources sit
        # above pyproject.toml (and extra_settings), "default" sources sit below
        # it, just above the hard-coded defaults. Either way the user's per-build
        # env vars and config-settings still win. Opt out entirely with
        # SKBUILD_NO_ENTRYPOINT_CONFIG.
        # Entry-point config comes from the *machine environment* (installed
        # distro packages), not the project, so for validation gates it is
        # treated like env vars / config-settings (dynamic), not like static
        # pyproject content: override-only fields are allowed and the project's
        # minimum-version pin does not gate it. It still participates in normal
        # precedence/merging via ``toml_srcs`` (see ``ep_srcs`` below).
        ep_srcs: list[Source] = []
        if not strtobool(environ.get("SKBUILD_NO_ENTRYPOINT_CONFIG", "")):
            override_index = 0
            for level, ep_name, ep_table in load_config_providers(
                state=state, env=environ
            ):
                ep_skb = copy.deepcopy(ep_table)
                # Any [[overrides]] in the provider table (including inherit
                # append/prepend) resolve against the provider's own table
                # here; cross-source merging happens later in SourceChain,
                # which merges dicts but takes lists wholesale from the
                # highest-precedence source. A future refactor could process
                # overrides on the merged view instead.
                ep_matched, ep_overridden = process_table(
                    ep_skb,
                    "config-setting declarations are only allowed in pyproject.toml",
                )
                self.overrides |= ep_matched
                ep_source = TOMLSource(settings=ep_skb)
                ep_srcs.append(ep_source)
                ep_display = f"entry-point config ({ep_name})"
                if level == "override":
                    self.overridden_items.update(ep_overridden)
                    toml_srcs.insert(override_index, ep_source)
                    toml_src_names.insert(override_index, ep_display)
                    override_index += 1
                else:
                    # Lowest priority: never clobber higher-priority records.
                    for key, record in ep_overridden.items():
                        self.overridden_items.setdefault(key, record)
                    toml_srcs.append(ep_source)
                    toml_src_names.append(ep_display)

        prefixed = {
            k: v for k, v in config_settings.items() if k.startswith("skbuild.")
        }
        remaining = {
            k: v for k, v in config_settings.items() if not k.startswith("skbuild.")
        }
        # Sources that may legitimately set override-only fields at build time.
        dynamic_srcs: list[Source] = [
            EnvSource("SKBUILD", env=env),
            ConfSource("skbuild", settings=prefixed, verify=verify_conf),
            ConfSource(
                settings=remaining,
                verify=verify_conf,
                extra_keys=frozenset(self.config_setting_decls),
            ),
        ]
        # env vars + config-settings; these lead ``self.sources`` (see below),
        # so ``print_suggestions`` relies on their count.
        self._dynamic_srcs = tuple(dynamic_srcs)
        # Entry-point config is machine-level (not project-static), so for
        # validation it is grouped with the dynamic sources: override-only
        # fields are allowed and the project's minimum-version pin does not
        # gate it. It still participates in normal precedence via ``toml_srcs``.
        self._ep_srcs = tuple(ep_srcs)
        # Static pyproject.toml (and extra_settings) tables; override-only fields
        # are forbidden here outside of an [[overrides]] section, and their
        # values are gated by the project's minimum-version pin.
        self._static_srcs = tuple(s for s in toml_srcs if s not in ep_srcs)
        # Full TOML precedence chain (including entry-point config), used for
        # value resolution and unrecognized-option reporting.
        self._toml_srcs = tuple(toml_srcs)
        self._toml_src_names = tuple(toml_src_names)
        self.sources = SourceChain(
            *dynamic_srcs,
            *toml_srcs,
            prefixes=["tool", "scikit-build"],
        )
        self.settings = self.sources.convert_target(ScikitBuildSettings)

        # CMake 3.22+ reads CMAKE_BUILD_TYPE from the environment, but only as a
        # default for the first configure; the -DCMAKE_BUILD_TYPE we always pass
        # (default "Release") would override it. Honor the environment value when
        # build-type wasn't configured, which also works on older CMake.
        if "CMAKE_BUILD_TYPE" in environ and not self.sources.has_item(
            "cmake", "build_type", is_dict=False
        ):
            self.settings.cmake.build_type = environ["CMAKE_BUILD_TYPE"]

        validate_variant_settings(self.settings)

        # The cmake/build values that come *only* from static project sources
        # (pyproject.toml and extra_settings), used by the minimum-version move
        # gates below. Entry-point config is excluded so it behaves like
        # env/config-settings.
        static_chain = SourceChain(
            *self._static_srcs, prefixes=["tool", "scikit-build"]
        )
        static_cmake = static_chain.convert_target(CMakeSettings, "cmake")
        static_build = static_chain.convert_target(BuildSettings, "build")

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

        if self.settings.editable.persistent_install:
            if self.settings.editable.mode == "inplace":
                # Inplace builds in the source tree, which serves as the
                # persistent build dir, so no separate build-dir is required.
                # rebuild-dir relocates the install tree, which inplace lacks.
                if self.settings.editable.rebuild_dir:
                    rich_error("editable rebuild-dir is incompatible with inplace mode")
            elif not self.settings.build_dir:
                rich_error("editable mode with rebuild requires build-dir")

        install_policy = (
            self.settings.minimum_version is None
            or self.settings.minimum_version >= Version("0.5")
        )
        if self.settings.install.strip is None:
            self.settings.install.strip = install_policy and all(
                bt in {"Release", "MinSizeRel"}
                for bt in normalize_build_types(self.settings.cmake.build_type)
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
            except ParseError:
                new_min_cmake = None
                rich_warning(
                    "CMakeLists.txt could not be parsed when looking for minimum "
                    "CMake version. Report this or (and) set manually to avoid this warning."
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

        _handle_minimum_version(
            self.settings.cmake, self.settings.minimum_version, "3.15"
        )
        _handle_minimum_version(self.settings.ninja, self.settings.minimum_version)

        self.settings.build.verbose = _handle_move(
            "cmake.verbose",
            self.settings.cmake.verbose,
            "build.verbose",
            self.settings.build.verbose,
            self.settings.minimum_version,
            Version("0.10"),
            static=static_cmake.verbose == self.settings.cmake.verbose
            and static_build.verbose == self.settings.build.verbose,
        )
        self.settings.build.targets = _handle_move(
            "cmake.targets",
            self.settings.cmake.targets,
            "build.targets",
            self.settings.build.targets,
            self.settings.minimum_version,
            Version("0.10"),
            static=static_cmake.targets == self.settings.cmake.targets
            and static_build.targets == self.settings.build.targets,
        )

        if (
            self.config_setting_decls
            and self.settings.minimum_version is not None
            and self.settings.minimum_version < Version("1.1")
        ):
            rich_error(
                "minimum-version must be at least 1.1 to use tool.scikit-build.config-setting"
            )

        if self.settings.sdist.inclusion_mode is not None:
            if (
                self.settings.minimum_version is not None
                and self.settings.minimum_version < Version("0.12")
            ):
                rich_error(
                    "minimum-version can't be less than 0.12 to use sdist.inclusion-mode"
                )
            if (
                self.settings.sdist.inclusion_mode == "explicit"
                and self.settings.minimum_version is not None
                and self.settings.minimum_version < Version("1.0")
            ):
                rich_error(
                    'minimum-version must be at least 1.0 to use sdist.inclusion-mode = "explicit"'
                )
        elif (
            self.settings.minimum_version is not None
            and self.settings.minimum_version < Version("0.12")
        ):
            self.settings.sdist.inclusion_mode = "classic"
        else:
            self.settings.sdist.inclusion_mode = "default"

        if self.settings.sdist.resolve_symlinks is not None:
            if (
                self.settings.minimum_version is not None
                and self.settings.minimum_version < Version("1.0")
            ):
                rich_error(
                    "minimum-version can't be less than 1.0 to use sdist.resolve-symlinks"
                )
            if (
                self.settings.sdist.resolve_symlinks == "error"
                and self.settings.minimum_version is not None
                and self.settings.minimum_version < Version("1.1")
            ):
                rich_error(
                    'minimum-version must be at least 1.1 to use sdist.resolve-symlinks = "error"'
                )
        elif (
            self.settings.minimum_version is not None
            and self.settings.minimum_version < Version("1.0")
        ):
            self.settings.sdist.resolve_symlinks = "classic"
        else:
            self.settings.sdist.resolve_symlinks = "all"

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
        # Index 0 is the env source (skipped); the config-settings sources
        # follow, then the TOML sources, named in order by ``_toml_src_names``
        # (pyproject.toml plus any extra-settings/entry-point config sources).
        n_dynamic = len(self._dynamic_srcs)
        names = dict.fromkeys(range(1, n_dynamic), "config-settings")
        for offset, src_name in enumerate(self._toml_src_names):
            names[n_dynamic + offset] = src_name
        for index, name in names.items():
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
        _validate_overrides(
            self.settings,
            self.overridden_items,
            dynamic_sources=(*self._dynamic_srcs, *self._ep_srcs),
            toml_sources=self._static_srcs,
        )

        if self.settings.metadata and self.dynamic_metadata:
            sys.stdout.flush()
            rich_error(
                "tool.scikit-build.metadata cannot be combined with the standard "
                "top-level [[tool.dynamic-metadata]]; use only one"
            )

        if self.settings.metadata and (
            self.settings.minimum_version is None
            or self.settings.minimum_version >= Version("1.0")
        ):
            rich_warning(
                "tool.scikit-build.metadata is deprecated; use the standard "
                "top-level [[tool.dynamic-metadata]] instead"
            )

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
        config_settings: Mapping[str, str | list[str] | bool] | None = None,
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
