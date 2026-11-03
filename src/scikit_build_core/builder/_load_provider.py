from __future__ import annotations

__lazy_modules__ = {
    "importlib.machinery",
    "inspect",
    "pathlib",
    "types",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.metadata",
}

import dataclasses
import importlib
import importlib.abc
import importlib.machinery
import inspect
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any,
    Literal,
    Protocol,
    cast,
    get_args,
    runtime_checkable,
)

from ..metadata import (
    _ALL_FIELDS,
    _DICT_STR_FIELDS,
    _EXTENDABLE_FIELDS,
    _LIST_DICT_FIELDS,
    _LIST_STR_FIELDS,
    _SCALAR_FIELDS,
)

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Generator, Sequence
    from importlib.machinery import ModuleSpec
    from types import ModuleType

    StrMapping = Mapping[str, Any]
else:
    StrMapping = Mapping

__all__ = [
    "BUILD_STATES",
    "BuildState",
    "dynamic_wheel_fields",
    "load_dynamic_metadata",
    "load_entry_provider",
    "load_provider",
    "process_dynamic_metadata",
    "process_legacy_dynamic_metadata",
]


def __dir__() -> list[str]:
    return __all__


# The five build states a backend can report to a provider's ``build_state``
# hook; the last two are the ``prepare_metadata_for_build_*`` phases.
BuildState = Literal[
    "sdist", "wheel", "editable", "metadata_wheel", "metadata_editable"
]
BUILD_STATES: frozenset[str] = frozenset(get_args(BuildState))


@runtime_checkable
class DynamicMetadataProtocol(Protocol):
    def dynamic_metadata(
        self,
        settings: Mapping[str, Any],
        project: Mapping[str, Any],
    ) -> Any: ...


@runtime_checkable
class DynamicMetadataBuildStateProtocol(DynamicMetadataProtocol, Protocol):
    def build_state(self, build_state: BuildState) -> None: ...


@runtime_checkable
class DynamicMetadataRequirementsProtocol(DynamicMetadataProtocol, Protocol):
    def get_requires_for_dynamic_metadata(
        self, settings: Mapping[str, Any]
    ) -> list[str]: ...


@runtime_checkable
class DynamicMetadataWheelProtocol(DynamicMetadataProtocol, Protocol):
    def dynamic_wheel(self, settings: Mapping[str, Any]) -> dict[str, bool]: ...


DMProtocols = (
    DynamicMetadataProtocol
    | DynamicMetadataBuildStateProtocol
    | DynamicMetadataRequirementsProtocol
    | DynamicMetadataWheelProtocol
)


class _ProviderPathFinder(importlib.abc.MetaPathFinder):
    """Load the top-level provider module from ``provider-path``.

    Mirrors how pyproject_hooks handles PEP 517 ``backend-path``: a finder at
    the front of ``sys.meta_path`` guarantees the in-tree provider wins over a
    same-named module elsewhere on ``sys.path`` (or behind another finder), and
    a provider absent from ``provider-path`` raises instead of silently
    importing the wrong module. Only the top-level name is intercepted; nested
    modules resolve through the parent package's path. A provider already cached
    in ``sys.modules`` short-circuits import and bypasses this finder.
    """

    def __init__(self, provider_path: list[str], provider: str) -> None:
        self.provider_path = provider_path
        self.provider = provider
        self.provider_parent = provider.partition(".")[0]

    def find_spec(
        self,
        fullname: str,
        _path: Sequence[str] | None,
        _target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if "." in fullname:
            return None

        spec = importlib.machinery.PathFinder.find_spec(
            fullname, path=self.provider_path
        )
        if spec is None and fullname == self.provider_parent:
            msg = f"Cannot find module {self.provider!r} in {self.provider_path!r}"
            raise ModuleNotFoundError(msg)
        return spec


def load_provider(
    provider: str,
    provider_path: str | None = None,
) -> DMProtocols:
    """Load a provider, returning the object whose hooks are called.

    ``provider`` is either a module path (``"pkg.mod"``) or a module path and a
    class within it (``"pkg.mod:Class"``). A bare module is returned as-is, so
    its hooks are plain module-level functions; a class is instantiated with no
    arguments and the instance is returned, so its hooks are bound methods and
    may share state through ``self`` (e.g. the optional ``build_state`` hook
    stashing the build state for ``dynamic_metadata`` to read).
    """
    module_name, _, class_name = provider.partition(":")

    if provider_path is None:
        module = importlib.import_module(module_name)
    else:
        if not Path(provider_path).is_dir():
            msg = f"provider-path {provider_path!r} must be an existing directory"
            raise FileNotFoundError(msg)
        # Absolute, since sys.path_importer_cache is keyed on the path string
        finder = _ProviderPathFinder([str(Path(provider_path).absolute())], module_name)
        sys.meta_path.insert(0, finder)
        try:
            module = importlib.import_module(module_name)
        finally:
            sys.meta_path.remove(finder)

    return getattr(module, class_name)() if class_name else module


def load_entry_provider(provider: str | Mapping[str, Any]) -> DMProtocols:
    """Resolve a ``[[tool.dynamic-metadata]]`` provider (dynamic-metadata 0.3).

    A string is a name registered in the ``dynamic_metadata.provider``
    entry-point group; a class-valued entry point is instantiated, a
    module-valued one used as-is. An inline table ``{path, module}`` names a
    local in-project plugin: ``module`` (``"pkg.mod"`` or ``"pkg.mod:Class"``) is
    imported from the ``path`` directory via the same finder as ``load_provider``.

    Unlike the deprecated ``tool.scikit-build.metadata`` table, a bare import
    string is not accepted here -- an installed plugin is reached through its
    entry point, a local one through the inline table.
    """
    if not isinstance(provider, str):
        module = provider.get("module")
        path = provider.get("path")
        if not isinstance(module, str) or not isinstance(path, str):
            msg = "A table provider must set string 'path' and 'module' keys"
            raise TypeError(msg)
        return load_provider(module, path)

    from .._compat.importlib.metadata import entry_points

    eps = entry_points(group="dynamic_metadata.provider")
    matches = [ep for ep in eps if ep.name == provider]
    if not matches:
        import difflib

        names = sorted(ep.name for ep in eps)
        close = difflib.get_close_matches(provider, names, n=1)
        hint = f"; did you mean {close[0]!r}?" if close else ""
        msg = f"Unknown dynamic-metadata provider {provider!r}{hint}"
        raise ModuleNotFoundError(msg)
    if len(matches) > 1:
        from .._logging import rich_warning

        dists = ", ".join(
            getattr(getattr(ep, "dist", None), "name", None) or "unknown distribution"
            for ep in matches
        )
        rich_warning(
            f"Multiple 'dynamic_metadata.provider' entry points named "
            f"{provider!r} found (from {dists}); using the first"
        )
    obj: Any = matches[0].load()
    return cast("DMProtocols", obj() if isinstance(obj, type) else obj)


def load_dynamic_metadata(
    entries: Sequence[Mapping[str, Any]],
) -> Generator[tuple[DMProtocols, dict[str, Any]], None, None]:
    """Load each ``[[tool.dynamic-metadata]]`` entry's provider in order.

    ``provider`` is consumed here; the remaining keys are returned as that
    provider's plugin settings.
    """
    for entry in entries:
        if "provider" not in entry:
            msg = "Each [[tool.dynamic-metadata]] entry must set a 'provider'"
            raise KeyError(msg)
        settings = {k: v for k, v in entry.items() if k != "provider"}
        provider = load_entry_provider(entry["provider"])
        yield provider, settings


def dynamic_wheel_fields(entries: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    """Collect fields whose value may change between the SDist and a wheel.

    Each ``[[tool.dynamic-metadata]]`` provider implementing the optional
    ``dynamic_wheel`` hook reports a field -> bool map; a field a provider does
    not mention defaults to not dynamic in this sense, and ``version`` may never
    be. The returned fields are marked ``Dynamic`` in the SDist's PKG-INFO
    (METADATA 2.2).
    """
    fields: set[str] = set()
    for provider, settings in load_dynamic_metadata(entries):
        if not isinstance(provider, DynamicMetadataWheelProtocol):
            continue
        for field, is_dynamic in provider.dynamic_wheel(settings).items():
            if field not in _ALL_FIELDS:
                msg = f"{field!r} is not a valid dynamic-metadata field"
                raise KeyError(msg)
            if field == "version" and is_dynamic:
                msg = "'version' may not change between the SDist and wheel"
                raise ValueError(msg)
            # A field's merged value can change if any contributing provider's
            # part may, so reports combine with OR: one True can't be retracted.
            if is_dynamic:
                fields.add(field)

    return frozenset(fields)


def _merge_dict(
    field: str, base: Mapping[str, Any], additions: Mapping[str, Any]
) -> dict[str, Any]:
    """Add new keys to a table; a provider may not change existing values."""
    merged = dict(base)
    for key, value in additions.items():
        if key in merged and merged[key] != value:
            msg = f"Provider for {field!r} may not modify existing key {key!r}"
            raise ValueError(msg)
        merged[key] = value
    return merged


def _merge_metadata(field: str, static: Any, dynamic: Any) -> Any:
    """Merge a current value with a provider's additions (PEP 808).

    Existing entries are preserved as-is and kept first; the provider's value is
    appended after them. Single-value fields cannot be extended; merging onto a
    static value of one is the invalid "static *and* dynamic" case and raises.
    """
    if field not in _EXTENDABLE_FIELDS:
        msg = f"Field {field!r} cannot be given both statically and dynamically"
        raise ValueError(msg)

    if field in _LIST_STR_FIELDS or field in _LIST_DICT_FIELDS:
        return [*static, *dynamic]

    if field in _DICT_STR_FIELDS:
        return _merge_dict(field, static, dynamic)

    if field == "optional-dependencies":
        merged_extras = {extra: list(deps) for extra, deps in static.items()}
        for extra, deps in dynamic.items():
            merged_extras.setdefault(extra, []).extend(deps)
        return merged_extras

    # entry-points: a table of groups, each a table of name -> object reference
    merged_groups = {group: dict(eps) for group, eps in static.items()}
    for group, eps in dynamic.items():
        merged_groups[group] = _merge_dict(
            f"entry-points group {group!r}", merged_groups.get(group, {}), eps
        )
    return merged_groups


def process_dynamic_metadata(
    project: Mapping[str, Any],
    entries: Sequence[Mapping[str, Any]],
    build_state: BuildState = "metadata_wheel",
) -> dict[str, Any]:
    """Resolve ``[[tool.dynamic-metadata]]`` entries (the 0.3 spec).

    Entries run in list order; each provider is called with a read-only snapshot
    of the project as resolved so far, so a later entry can read a field an
    earlier one produced via ``project[...]``. A provider returns a ``dict``
    fragment of ``[project]`` which is merged in (PEP 808 add-only for list and
    table fields; a later entry replaces a scalar). ``build_state`` is reported
    to any provider implementing the optional ``build_state`` hook before its
    ``dynamic_metadata`` is called.
    """
    if build_state not in BUILD_STATES:
        msg = f"build_state must be one of {sorted(BUILD_STATES)}, got {build_state!r}"
        raise ValueError(msg)

    result = dict(project)
    result["dynamic"] = list(result.get("dynamic", []))
    declared_dynamic = set(result["dynamic"])
    snapshot = MappingProxyType(result)

    # Fields already written by an earlier entry: a further entry merges onto
    # that result (and may *replace* a scalar), as opposed to a static value
    # still sitting in [project], which is the PEP 808 add-only case.
    produced: set[str] = set()

    for provider, settings in load_dynamic_metadata(entries):
        if isinstance(provider, DynamicMetadataBuildStateProtocol):
            provider.build_state(build_state)
        fragment: dict[str, Any] = provider.dynamic_metadata(settings, snapshot)

        for field in fragment:
            if field not in _ALL_FIELDS:
                msg = f"{field!r} is not a settable dynamic-metadata field"
                raise KeyError(msg)
            if field not in declared_dynamic:
                msg = f"{field!r} must be listed in project.dynamic to be set"
                raise KeyError(msg)

        for field, value in fragment.items():
            if field in produced:
                result[field] = (
                    value
                    if field in _SCALAR_FIELDS
                    else _merge_metadata(field, result[field], value)
                )
            elif field in result:
                result[field] = _merge_metadata(field, result[field], value)
            else:
                result[field] = value
            produced.add(field)
            if field in result["dynamic"]:
                result["dynamic"].remove(field)

    return result


def _load_dynamic_metadata(
    metadata: Mapping[str, Mapping[str, str]],
) -> Generator[tuple[str, DMProtocols, dict[str, Any]], None, None]:
    for field, orig_config in metadata.items():
        if "provider" not in orig_config:
            msg = "Missing provider in dynamic metadata"
            raise KeyError(msg)

        if field not in _ALL_FIELDS:
            msg = f"{field} is not a valid field"
            raise KeyError(msg)
        config = dict(orig_config)
        provider = config.pop("provider")
        provider_path = config.pop("provider-path", None)
        loaded_provider = load_provider(provider, provider_path)
        yield field, loaded_provider, config


@dataclasses.dataclass
class DynamicPyProject(StrMapping):
    settings: dict[str, dict[str, Any]]
    project: dict[str, Any]
    providers: dict[str, DMProtocols]

    def __getitem__(self, key: str) -> Any:
        # Try to get the settings from either the static file or dynamic metadata provider
        if key in self.project:
            return self.project[key]

        # Check if we are in a loop, i.e. something else is already requesting
        # this key while trying to get another key
        if key not in self.providers:
            dep_type = "missing" if key in self.settings else "circular"
            msg = f"Encountered a {dep_type} dependency at {key}"
            raise ValueError(msg)

        provider = self.providers.pop(key)
        # Legacy hooks have a different shape, so they are called untyped.
        hook: Any = provider.dynamic_metadata
        sig = inspect.signature(hook)
        if len(sig.parameters) < 3:
            # Backcompat for dynamic_metadata without metadata dict
            self.project[key] = hook(key, self.settings[key])
        else:
            self.project[key] = hook(key, self.settings[key], self)
        self.project["dynamic"].remove(key)

        return self.project[key]

    def __iter__(self) -> Iterator[str]:
        # Iterate over the keys of the static settings
        yield from self.project

        # Iterate over the keys of the dynamic metadata providers
        # GraalPy needs it to be a copy
        yield from list(self.providers)

    def __len__(self) -> int:
        return len(self.project) + len(self.providers)

    def __contains__(self, key: object) -> bool:
        return key in self.project or key in self.providers


def process_legacy_dynamic_metadata(
    project: Mapping[str, Any],
    metadata: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve the deprecated ``tool.scikit-build.metadata`` table.

    Each field names a provider; fields resolve lazily, so a provider may read
    another field (even one defined later in the table) via ``project[...]``,
    with circular references detected and reported.
    """
    initial = {f: (p, c) for (f, p, c) in _load_dynamic_metadata(metadata)}

    # Copy the mutable project, including the "dynamic" list that providers
    # remove resolved fields from, so the caller's dict is left untouched.
    project_copy = dict(project)
    project_copy["dynamic"] = list(project_copy.get("dynamic", []))

    settings = DynamicPyProject(
        settings={f: c for f, (_, c) in initial.items()},
        project=project_copy,
        providers={k: v for k, (v, _) in initial.items()},
    )

    return dict(settings)
