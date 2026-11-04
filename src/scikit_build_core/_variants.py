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
    return bool(
        settings.variant
        or settings.variant_name
        or settings.null_variant
        or settings.variant_label
    )


def _no_label_entry(label: str) -> NoReturn:
    rich_error(
        "variant-label '{label}' has no [variant.variants.{label}] entry and no variant properties were given",
        label=label,
    )


def _variant_namespaces(
    settings: ScikitBuildSettings, variant_table: Mapping[str, Any]
) -> set[str]:
    # "namespace :: feature :: value"; empty for the null variant
    properties = [*settings.variant_name, *settings.variant]
    if not properties and settings.variant_label:
        # label-only selection: look the properties up in [variant.variants]
        variant = variant_table.get("variants", {}).get(settings.variant_label)
        if not isinstance(variant, dict):
            _no_label_entry(settings.variant_label)
        return set(variant)

    namespaces = set()
    for prop in properties:
        parts = [part.strip() for part in prop.split("::")]
        if len(parts) != 3 or not all(parts):
            rich_error(
                "variant property {prop!r} is invalid, expected format: 'namespace :: feature :: value'",
                prop=prop,
            )
        namespaces.add(parts[0])
    return namespaces


def variant_build_requires(
    settings: ScikitBuildSettings, variant_table: Mapping[str, Any]
) -> list[str]:
    """
    Build requirements for a variant build: variantlib plus the provider
    plugins for the namespaces in use, so the properties can be validated
    at build time (PEP 817).
    """
    if not has_variant_config(settings):
        return []

    providers = variant_table.get("providers", {})
    requires = [VARIANTLIB_BUILD_REQUIREMENT]
    for namespace in sorted(_variant_namespaces(settings, variant_table)):
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

    if settings.null_variant and (settings.variant or settings.variant_name):
        rich_error(
            'null-variant is mutually exclusive with "variant" and "variant-name"'
        )

    if settings.null_variant and settings.variant_label:
        rich_error('null-variant is mutually exclusive with "variant-label"')

    if settings.variant_label == "null":
        rich_error('variant-label "null" is reserved, use null-variant = true instead')


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
    if not has_variant_config(settings):
        return None

    try:
        variantlib_api = importlib.import_module("variantlib.api")
        variantlib_errors = importlib.import_module("variantlib.errors")
        variantlib_models = importlib.import_module("variantlib.models.variant")
        variantlib_pyproject = importlib.import_module("variantlib.pyproject_toml")
    except ModuleNotFoundError:
        rich_error("variantlib is required to use variant settings")

    make_variant_dist_info = variantlib_api.make_variant_dist_info
    validate_variant = variantlib_api.validate_variant
    validation_error = variantlib_errors.ValidationError
    plugin_error = variantlib_errors.PluginError
    variant_description: Any = variantlib_models.VariantDescription
    variant_property: Any = variantlib_models.VariantProperty
    variant_pyproject_toml: Any = variantlib_pyproject.VariantPyProjectToml

    if "variant" not in pyproject:
        rich_error(
            "a [variant] table with default-priorities and providers is required to build variant wheels, including the null variant"
        )

    try:
        variant_info = variant_pyproject_toml(pyproject)
        properties = [
            variant_property.from_str(value)
            for value in [*settings.variant_name, *settings.variant]
        ]
        label = settings.variant_label
        declared = variant_info.variants.get(label) if label else None
        if not properties and label:
            # label-only selection from [variant.variants.<label>]
            if declared is None:
                _no_label_entry(label)
            variant = declared
        elif label:
            variant = variant_description(properties, label=label)
            # PEP 825: a label maps to exactly one property set per version
            if declared is not None and declared.properties != variant.properties:
                rich_error(
                    "variant-label '{label}' properties do not match [variant.variants.{label}], which declares: {declared}",
                    label=label,
                    declared=", ".join(p.to_str() for p in declared.properties),
                )
        else:
            variant = variant_description(properties)
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
