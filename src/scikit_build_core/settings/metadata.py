from __future__ import annotations

from typing import Any

from packaging.version import Version
from pyproject_metadata import StandardMetadata

from ..settings.skbuild_model import ScikitBuildSettings
from ._load_provider import load_provider

__all__ = ["get_standard_metadata"]


def __dir__() -> list[str]:
    return __all__


# If pyproject-metadata eventually supports updates, this can be simplified
def get_standard_metadata(
    pyproject_dict: dict[str, Any],
    settings: ScikitBuildSettings,
) -> StandardMetadata:
    # Handle any dynamic metadata
    calls: dict[frozenset[tuple[str, Any]], set[str]] = {}
    for field, raw_settings in settings.metadata.items():
        if field not in pyproject_dict.get("project", {}).get("dynamic", []):
            msg = f"{field} is not in project.dynamic"
            raise KeyError(msg)
        if "provider" not in raw_settings:
            msg = f"{field} is missing provider"
            raise KeyError(msg)
        calls.setdefault(frozenset(raw_settings.items()), set()).add(field)

    for call, fields in calls.items():
        args = dict(call)
        provider = args.pop("provider")
        provider_path = args.pop("provider-path", None)
        computed = load_provider(provider, provider_path).dynamic_metadata(
            frozenset(fields), args
        )
        if set(computed) != fields:
            msg = f"{provider} did not return requested fields"
            raise KeyError(msg)
        pyproject_dict["project"].update(computed)
        for field in fields:
            pyproject_dict["project"]["dynamic"].remove(field)

    metadata = StandardMetadata.from_pyproject(pyproject_dict)
    # pyproject-metadata normalizes the name - see https://github.com/FFY00/python-pyproject-metadata/pull/65
    # For scikit-build-core 0.5+, we keep the un-normalized name, and normalize it when using it for filenames
    if settings.minimum_version is None or settings.minimum_version >= Version("0.5"):
        metadata.name = pyproject_dict["project"]["name"]
    return metadata
