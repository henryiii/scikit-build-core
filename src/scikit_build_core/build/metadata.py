from __future__ import annotations

__lazy_modules__ = {
    "copy",
    "packaging.version",
    "typing",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._logging",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._vendor.pyproject_metadata.constants",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.builder._load_provider",
    f"{__spec__.parent}._import_names",
}

import copy
import dataclasses
import sys
from typing import Any

from packaging.version import Version

from .._logging import logger
from .._vendor.pyproject_metadata import (
    RFC822Message,
    StandardMetadata,
    errors,
    extras_build_system,
    extras_top_level,
)
from .._vendor.pyproject_metadata.constants import (
    PROJECT_DYNAMIC_STATIC,
    PROJECT_TO_METADATA,
)
from ..builder._load_provider import (
    dynamic_wheel_fields,
    process_dynamic_metadata,
    process_legacy_dynamic_metadata,
)
from ._import_names import add_dynamic_import_names

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..builder._load_provider import BuildState
    from ..settings.skbuild_model import ScikitBuildSettings

__all__ = ["SkbuildMetadata", "get_standard_metadata"]


def __dir__() -> list[str]:
    return __all__


# Use exceptiongroup backport
if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup

    errors.ExceptionGroup = ExceptionGroup  # type: ignore[misc, assignment]


@dataclasses.dataclass
class SkbuildMetadata(StandardMetadata):
    raw_version: str | None = None
    """
    ``project.version`` as written, before packaging normalizes it. A calendar
    version like ``2024.01.05`` keeps its leading zeros here. When set, it is
    used for the ``Version`` metadata field; ``version`` is always the
    normalized form and is what filenames use.
    """

    def as_rfc822(self) -> RFC822Message:
        message = super().as_rfc822()
        if self.raw_version is not None:
            message.replace_header("Version", self.raw_version)
        return message

    def as_json(self) -> dict[str, str | list[str]]:
        data = super().as_json()
        if self.raw_version is not None:
            data["version"] = self.raw_version
        return data


def get_standard_metadata(
    pyproject_dict: Mapping[str, Any],
    settings: ScikitBuildSettings,
    build_state: BuildState = "metadata_wheel",
) -> SkbuildMetadata:
    new_pyproject_dict = copy.deepcopy(dict(pyproject_dict))
    project = new_pyproject_dict["project"]

    # PEP 808: fields the author gives a static value in [project] *and* lists in
    # dynamic. Captured before providers resolve them, as process_*dynamic_metadata
    # drops resolved fields from dynamic. Only those also marked Dynamic in the
    # SDist (via dynamic_wheel, below) need metadata_version 2.6.
    dual_dynamic = {
        field
        for field in project.get("dynamic", [])
        if isinstance(field, str)
        and field in project
        and field in PROJECT_DYNAMIC_STATIC
    }

    # Handle the legacy tool.scikit-build.metadata table, then the standard
    # top-level [[tool.dynamic-metadata]] entries (dynamic-metadata 0.3). Both
    # forms may be present; the legacy table is resolved first.
    if settings.metadata:
        project = process_legacy_dynamic_metadata(project, settings.metadata)

    entries = new_pyproject_dict.get("tool", {}).get("dynamic-metadata", [])
    if entries:
        project = process_dynamic_metadata(project, entries, build_state)

    # PEP 794: fill import names still listed in dynamic from the packages
    project = add_dynamic_import_names(project, settings)

    new_pyproject_dict["project"] = project

    # METADATA 2.2: fields a provider reports (via the optional dynamic_wheel
    # hook) as possibly differing between the SDist and a wheel built from it
    # are marked Dynamic. Only SDist metadata may carry Dynamic fields.
    dynamic_metadata: list[str] = []
    if entries and build_state == "sdist":
        dynamic_metadata = sorted(
            metadata_field
            for project_field in dynamic_wheel_fields(entries)
            for metadata_field in PROJECT_TO_METADATA[project_field]
        )

    if settings.strict_config:
        # [variant] is the wheel variant table (PEP 817)
        extra_keys_top = extras_top_level(new_pyproject_dict) - {"variant"}
        if extra_keys_top:
            logger.warning(
                f"Unknown keys in top-level of pyproject.toml: {', '.join(extra_keys_top)}"
            )
        extra_keys_build = extras_build_system(new_pyproject_dict)
        if extra_keys_build:
            logger.warning(
                f"Unknown keys in build-system of pyproject.toml: {', '.join(extra_keys_build)}"
            )

    extra_validate = (
        settings.minimum_version is None or settings.minimum_version >= Version("0.10")
    )
    if extra_validate:
        allow_extra_keys: bool | None = not settings.strict_config
    else:
        allow_extra_keys = None if settings.strict_config else False

    metadata = SkbuildMetadata.from_pyproject(
        new_pyproject_dict,
        dynamic_metadata=dynamic_metadata,
        all_errors=True,
        allow_extra_keys=allow_extra_keys,
    )
    # Keep the version as written (scikit-build-core >= 1.1). Older minimums
    # keep the normalized form so existing builds stay bit-for-bit reproducible.
    raw_version = project.get("version")
    if isinstance(raw_version, str):
        # packaging strips surrounding whitespace, and a header cannot hold it
        raw_version = raw_version.strip()
    if (
        settings.minimum_version is None or settings.minimum_version >= Version("1.1")
    ) and (isinstance(raw_version, str) and raw_version):
        metadata.raw_version = raw_version

    # Restore the PEP 808 dual-dynamic set that from_pyproject can no longer see
    # (the fields were dropped from dynamic during resolution). Combined with the
    # Dynamic metadata headers above, this bumps auto_metadata_version to 2.6.
    metadata.dual_dynamic = dual_dynamic

    # For scikit-build-core < 0.5, we keep the normalized name for back-compat
    if settings.minimum_version is not None and settings.minimum_version < Version(
        "0.5"
    ):
        metadata.name = metadata.canonical_name

    # The description field is required to be one line. Instead of merging it
    # or cutting off subsequent lines (setuptools), we throw a nice error.
    # But we didn't validate before 0.9.
    if (
        settings.minimum_version is None or settings.minimum_version >= Version("0.9")
    ) and "\n" in (metadata.description or ""):
        msg = "Multiple lines in project.description are not supported; this is supposed to be a one line summary"
        raise ValueError(msg)

    # Validate license if possible.
    if isinstance(metadata.license, str):
        try:
            import packaging.licenses

            metadata.license = packaging.licenses.canonicalize_license_expression(
                metadata.license
            )
        except ImportError:
            logger.warning(
                "Packaging 24.2+ required for license normalization. Please update"
            )

    # For scikit-build-core >= 0.11, we set METADATA 2.2 as minimum
    if (
        settings.minimum_version is None or settings.minimum_version >= Version("0.11")
    ) and metadata.auto_metadata_version == "2.1":
        metadata.metadata_version = "2.2"

    return metadata
