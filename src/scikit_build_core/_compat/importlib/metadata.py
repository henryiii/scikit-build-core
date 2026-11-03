from __future__ import annotations

__lazy_modules__ = {"importlib.metadata"}

import functools
import importlib.metadata

TYPE_CHECKING = False

if TYPE_CHECKING:
    import sys

    if sys.version_info < (3, 12):
        from importlib.metadata import EntryPoints, SelectableGroups
    else:
        from importlib.metadata import EntryPoints

        SelectableGroups = EntryPoints

__all__ = ["all_entry_points", "entry_points"]


@functools.cache
def all_entry_points() -> SelectableGroups:
    """Scan the installed distributions once; every group shares the result.

    Call ``all_entry_points.cache_clear()`` if the entry points change.
    """
    return importlib.metadata.entry_points()


def entry_points(*, group: str) -> EntryPoints:
    """Entry points for one group, from the cached scan.

    Callers read this from the module global, so a monkeypatch of it is seen.
    """
    return all_entry_points().select(group=group)


def __dir__() -> list[str]:
    return __all__
