from __future__ import annotations

__lazy_modules__ = {"importlib", "typing"}

import dataclasses
import importlib
from typing import Any

TYPE_CHECKING = False
if TYPE_CHECKING:
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


def _variant_namespaces(settings: ScikitBuildSettings) -> set[str]:
    # "namespace :: feature :: value"; empty for the null variant
    return {
        p.split("::", 1)[0].strip() for p in [*settings.variant_name, *settings.variant]
    }


def variant_build_requires(settings: ScikitBuildSettings) -> list[str]:
    if has_variant_config(settings):
        from pathlib import Path

        from ._compat import tomllib

        with Path("pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)

        providers = pyproject.get("variant", {}).get("providers", {})
        requires = [VARIANTLIB_BUILD_REQUIREMENT]
        # install only build-time providers for the namespaces
        for namespace in sorted(_variant_namespaces(settings)):
            if namespace not in providers:
                from ._logging import rich_error

                rich_error(
                    f"variant namespace '{namespace}' has no [variant.providers.{namespace}] entry"
                )
            requires.extend(providers[namespace].get("build-requires", []))
        return requires
    return []


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

    if settings.variant_label and not (
        settings.variant or settings.variant_name or settings.null_variant
    ):
        from ._logging import rich_error

        rich_error('variant-label requires "variant", "variant-name", or null-variant')


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

    try:
        properties = [
            variant_property.from_str(value)
            for value in [*settings.variant_name, *settings.variant]
        ]
        variant = (
            variant_description(properties, label=settings.variant_label)
            if settings.variant_label
            else variant_description(properties)
        )
        variant_label = variant.label
        variant_info = variant_pyproject_toml(pyproject)
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
