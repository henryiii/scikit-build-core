"""
Compute PEP 794 ``import-names`` / ``import-namespaces`` from the files in a wheel.
"""

from __future__ import annotations

__lazy_modules__ = {
    "keyword",
    "pathlib",
    f"{__spec__.parent}._editable",
    f"{__spec__.parent}._pathutil",
}

import keyword
from pathlib import PurePosixPath

from ._editable import get_packages
from ._pathutil import iter_package_files

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import Any

    from ..settings.skbuild_model import ScikitBuildSettings

__all__ = ["add_dynamic_import_names", "find_import_names"]

IMPORT_FIELDS = ("import-names", "import-namespaces")


def __dir__() -> list[str]:
    return __all__


def _module_name(filename: str) -> str | None:
    """Return the import name of a module file, or None if not importable."""
    if filename.endswith(".py"):
        name = filename[:-3]
    elif filename.endswith((".so", ".pyd")):
        # name.so, name.abi3.so, name.cpython-313-darwin.so, name.cp313-win_amd64.pyd
        name = filename.split(".", 1)[0]
    else:
        return None
    return name if _is_identifier(name) else None


def _is_identifier(name: str) -> bool:
    return name.isidentifier() and not keyword.iskeyword(name)


def find_import_names(
    files: Iterable[PurePosixPath],
) -> tuple[list[str], list[str]]:
    """
    Compute the shortest import names and the namespaces above them from a
    set of file paths relative to the wheel root (``site-packages``).

    A directory with an ``__init__`` module is a package. A directory without
    one is a namespace if it has an importable name below it. A module shadows
    a namespace of the same name.
    """
    tree: dict[str, set[PurePosixPath]] = {}
    names: set[str] = set()
    for path in files:
        if len(path.parts) == 1:
            name = _module_name(path.name)
            if name is not None:
                names.add(name)
        elif _is_identifier(path.parts[0]):
            tree.setdefault(path.parts[0], set()).add(PurePosixPath(*path.parts[1:]))

    namespaces: set[str] = set()
    for dirname, children in tree.items():
        if any(
            len(c.parts) == 1 and _module_name(c.name) == "__init__" for c in children
        ):
            names.add(dirname)
            continue
        sub_names, sub_namespaces = find_import_names(children)
        if sub_names:
            names.update(f"{dirname}.{n}" for n in sub_names)
            namespaces.update(f"{dirname}.{n}" for n in sub_namespaces)
            namespaces.add(dirname)

    namespaces -= names
    return sorted(names), sorted(namespaces)


def add_dynamic_import_names(
    project: Mapping[str, Any], settings: ScikitBuildSettings
) -> dict[str, Any]:
    """
    Fill the import fields still listed in ``project.dynamic`` from the wheel
    packages, and drop them from ``dynamic``. Static values (PEP 808) are kept
    first; computed names they already give are skipped.
    """
    result = dict(project)
    dynamic = project.get("dynamic", [])
    fields = [f for f in IMPORT_FIELDS if f in dynamic]
    if not fields:
        return result

    assert settings.sdist.inclusion_mode is not None
    files = iter_package_files(
        packages=get_packages(
            packages=settings.wheel.packages, name=project.get("name", "")
        ),
        include=settings.sdist.include,
        src_exclude=settings.sdist.exclude,
        target_exclude=settings.wheel.exclude,
        build_dir=settings.build_dir,
        mode=settings.sdist.inclusion_mode,
    )
    names, namespaces = find_import_names(
        PurePosixPath(target.as_posix()) for _, target in files
    )
    computed = dict(zip(IMPORT_FIELDS, (names, namespaces), strict=True))

    # Compare without a "; private" suffix, so static entries win
    static = {
        n.partition(";")[0].strip() for f in IMPORT_FIELDS for n in project.get(f, [])
    }
    for field in fields:
        new = [n for n in computed[field] if n not in static]
        result[field] = [*project.get(field, []), *new]
    result["dynamic"] = [f for f in dynamic if f not in fields]
    return result
