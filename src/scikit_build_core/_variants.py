from __future__ import annotations

__lazy_modules__ = {"importlib", "typing", f"{__spec__.parent}._logging"}

import dataclasses
import importlib
from typing import Any, NoReturn

from ._logging import logger, rich_error

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Mapping

    from ._vendor.pyproject_metadata import StandardMetadata
    from .settings.skbuild_model import ScikitBuildSettings

VARIANTLIB_BUILD_REQUIREMENT = "variantlib>=0.2.1,<0.3.0"
VARIANT_DIST_INFO_FILENAME = "variant.json"
NULL_VARIANT_LABEL = "null"

__all__ = [
    "VARIANT_DIST_INFO_FILENAME",
    "get_wheel_variant",
    "validate_variant_settings",
    "variant_build_requires",
]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class WheelVariant:
    label: str
    dist_info_contents: bytes


def has_variant_config(settings: ScikitBuildSettings) -> bool:
    return bool(settings.variant_label)


def _no_label_entry(label: str) -> NoReturn:
    rich_error(
        "variant-label '{label}' has no [variant.variants.{label}] entry",
        label=label,
    )


def _variant_namespaces(label: str, variant_table: Mapping[str, Any]) -> set[str]:
    # PEP 825 reserves "null" for the variant with no properties
    if label == NULL_VARIANT_LABEL:
        return set()
    variant = variant_table.get("variants", {}).get(label)
    if not isinstance(variant, dict):
        _no_label_entry(label)
    return set(variant)


def variant_build_requires(
    settings: ScikitBuildSettings, variant_table: Mapping[str, Any]
) -> list[str]:
    """
    Build requirements for a variant build: variantlib plus the provider
    plugins for the namespaces in use, so the properties can be validated
    at build time (PEP 817).
    """
    if not settings.variant_label:
        return []

    providers = variant_table.get("providers", {})
    requires = [VARIANTLIB_BUILD_REQUIREMENT]
    for namespace in sorted(_variant_namespaces(settings.variant_label, variant_table)):
        provider = providers.get(namespace)
        if provider is None:
            rich_error(
                "variant namespace '{ns}' has no [variant.providers.{ns}] entry",
                ns=namespace,
            )
        if not isinstance(provider, dict):
            rich_error("[variant.providers.{ns}] must be a table", ns=namespace)
        for key in ("build-requires", "requires"):
            plugin_requires = provider.get(key, [])
            if not isinstance(plugin_requires, list):
                rich_error(
                    "[variant.providers.{ns}] {key} must be a list",
                    ns=namespace,
                    key=key,
                )
            requires.extend(plugin_requires)
    return requires


def validate_variant_settings(settings: ScikitBuildSettings) -> None:
    if not has_variant_config(settings):
        return

    if not settings.experimental:
        rich_error(
            "experimental must be enabled currently to use wheel variant settings"
        )


def _validate_with_plugins(
    validate_variant: Any, variant: Any, variant_info: Any
) -> None:
    """Query the installed provider plugins (PEP 817 step 5)."""
    result = validate_variant(variant, variant_info)
    if result.invalid_properties:
        rich_error(
            "variant properties not supported by their provider plugin: "
            + ", ".join(sorted(p.to_str() for p in result.invalid_properties))
        )
    if result.multi_value_violations:
        rich_error(
            "variant features given more than one value but not multi-value: "
            + ", ".join(
                sorted(
                    f"{f.namespace} :: {f.feature}"
                    for f in result.multi_value_violations
                )
            )
        )
    for prop in result.unknown_properties:
        logger.warning(
            "No provider plugin for namespace {!r}, {!r} was not validated",
            prop.namespace,
            prop.to_str(),
        )


def get_wheel_variant(
    settings: ScikitBuildSettings,
    pyproject: dict[str, object],
    metadata: StandardMetadata,
) -> WheelVariant | None:
    label = settings.variant_label
    if not label:
        return None

    try:
        variantlib_api = importlib.import_module("variantlib.api")
        variantlib_errors = importlib.import_module("variantlib.errors")
        variantlib_pyproject = importlib.import_module("variantlib.pyproject_toml")
    except ModuleNotFoundError:
        rich_error("variantlib is required to use variant settings")

    make_variant_dist_info = variantlib_api.make_variant_dist_info
    validate_variant = variantlib_api.validate_variant
    validation_error = variantlib_errors.ValidationError
    plugin_error = variantlib_errors.PluginError
    variant_pyproject_toml: Any = variantlib_pyproject.VariantPyProjectToml

    if "variant" not in pyproject:
        rich_error(
            "a [variant] table with default-priorities and providers is required to build variant wheels, including the null variant"
        )

    try:
        variant_info = variant_pyproject_toml(pyproject)
        variant = variant_info.get_variant_desc(label)
        if variant is None:
            _no_label_entry(label)
        missing = {p.namespace for p in variant.properties} - set(
            variant_info.namespace_priorities
        )
        if missing:
            rich_error(
                "variant namespace(s) {missing} are missing from [variant.providers] / [variant.default-priorities]",
                missing=", ".join(sorted(missing)),
            )
        if variant.properties:
            _validate_with_plugins(validate_variant, variant, variant_info)
        dist_info_contents = make_variant_dist_info(
            variant,
            variant_info=variant_info,
        ).encode("utf-8")
    except (validation_error, plugin_error) as err:
        rich_error("{err}", err=err)

    if metadata.version is None:
        msg = "project.version is required to build variant wheel metadata"
        raise AssertionError(msg)

    return WheelVariant(label=variant.label, dist_info_contents=dist_info_contents)
