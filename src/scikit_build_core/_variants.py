from __future__ import annotations

__lazy_modules__ = {"importlib", "typing"}

import dataclasses
import importlib
from typing import Any

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


def _variant_namespaces(
    settings: ScikitBuildSettings, variant_table: Mapping[str, Any]
) -> set[str]:
    # "namespace :: feature :: value"; empty for the null variant
    from ._logging import rich_error

    properties = [*settings.variant_name, *settings.variant]
    if not properties and settings.variant_label:
        # label-only selection: look the properties up in [variant.variants]
        variant = variant_table.get("variants", {}).get(settings.variant_label)
        if not isinstance(variant, dict):
            rich_error(
                f"variant-label '{settings.variant_label}' has no [variant.variants.{settings.variant_label}] entry and no variant properties were given"
            )
        return set(variant)

    namespaces = set()
    for prop in properties:
        parts = [part.strip() for part in prop.split("::")]
        if len(parts) != 3 or not all(parts):
            rich_error(
                f"variant property {prop!r} is invalid, expected format: 'namespace :: feature :: value'"
            )
        namespaces.add(parts[0])
    return namespaces


def variant_build_requires(
    settings: ScikitBuildSettings, variant_table: Mapping[str, Any]
) -> list[str]:
    """
    Build requirements for a variant build. Only ``build-requires`` providers
    (ahead-of-time plugins) are needed at build time; ``requires`` providers
    are install-time only.
    """
    if not has_variant_config(settings):
        return []

    from ._logging import rich_error

    providers = variant_table.get("providers", {})
    requires = [VARIANTLIB_BUILD_REQUIREMENT]
    for namespace in sorted(_variant_namespaces(settings, variant_table)):
        provider = providers.get(namespace)
        if provider is None:
            rich_error(
                f"variant namespace '{namespace}' has no [variant.providers.{namespace}] entry"
            )
        if not isinstance(provider, dict):
            rich_error(f"[variant.providers.{namespace}] must be a table")
        build_requires = provider.get("build-requires", [])
        if not isinstance(build_requires, list):
            rich_error(f"[variant.providers.{namespace}] build-requires must be a list")
        requires.extend(build_requires)
    return requires


def validate_variant_settings(settings: ScikitBuildSettings) -> None:
    if not has_variant_config(settings):
        return

    if not settings.experimental:
        from ._logging import rich_error

        rich_error(
            "experimental must be enabled currently to use wheel variant settings"
        )

    if settings.null_variant and (settings.variant or settings.variant_name):
        from ._logging import rich_error

        rich_error(
            'null-variant is mutually exclusive with "variant" and "variant-name"'
        )

    if settings.null_variant and settings.variant_label:
        from ._logging import rich_error

        rich_error('null-variant is mutually exclusive with "variant-label"')


def get_wheel_variant(
    settings: ScikitBuildSettings,
    pyproject: dict[str, object],
    metadata: StandardMetadata,
) -> WheelVariant | None:
    if not has_variant_config(settings):
        return None

    from ._logging import rich_error

    try:
        variantlib_api = importlib.import_module("variantlib.api")
        variantlib_errors = importlib.import_module("variantlib.errors")
        variantlib_models = importlib.import_module("variantlib.models.variant")
        variantlib_pyproject = importlib.import_module("variantlib.pyproject_toml")
    except ModuleNotFoundError:
        rich_error("variantlib is required to use variant settings")

    make_variant_dist_info = variantlib_api.make_variant_dist_info
    validation_error = variantlib_errors.ValidationError
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
        if not properties and settings.variant_label:
            # label-only selection from [variant.variants.<label>]
            variant = variant_info.variants.get(settings.variant_label)
            if variant is None:
                rich_error(
                    f"variant-label '{settings.variant_label}' has no [variant.variants.{settings.variant_label}] entry and no variant properties were given"
                )
        elif settings.variant_label:
            variant = variant_description(properties, label=settings.variant_label)
            # PEP 825: a label maps to exactly one property set per version
            declared = variant_info.variants.get(settings.variant_label)
            if declared is not None and {p.to_str() for p in declared.properties} != {
                p.to_str() for p in variant.properties
            }:
                rich_error(
                    f"variant-label '{settings.variant_label}' properties do not match [variant.variants.{settings.variant_label}], which declares: {', '.join(sorted(p.to_str() for p in declared.properties))}"
                )
        else:
            variant = variant_description(properties)
        variant_label = variant.label
        missing = {p.namespace for p in variant.properties} - set(
            variant_info.namespace_priorities
        )
        if missing:
            rich_error(
                f"variant namespace(s) {', '.join(sorted(missing))} are missing from [variant.providers] / [variant.default-priorities]"
            )
        dist_info_contents = make_variant_dist_info(
            variant,
            variant_info=variant_info,
        ).encode("utf-8")
    except validation_error as err:
        rich_error(str(err))

    if metadata.version is None:
        msg = "project.version is required to build variant wheel metadata"
        raise AssertionError(msg)

    return WheelVariant(label=variant_label, dist_info_contents=dist_info_contents)
