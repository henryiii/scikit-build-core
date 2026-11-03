from __future__ import annotations

__lazy_modules__ = {
    "argparse",
    "packaging.utils",
    "pathlib",
    "scikit_build_core._logging",
    "scikit_build_core.resources",
    "string",
}

import argparse
import dataclasses
import string
import sys
from pathlib import Path

from packaging.utils import InvalidName, canonicalize_name

from scikit_build_core._logging import rich_error, rich_print
from scikit_build_core.resources import resources

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["generate_project", "main", "populate_parser"]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class _Backend:
    """Backend-specific pieces spliced into the shared ``pyproject.toml``."""

    requires: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    tool: str = ""


# Insertion order is the order shown in the interactive menu.
_BACKENDS = {
    "pybind11": _Backend(requires=("pybind11",)),
    "nanobind": _Backend(requires=("nanobind",)),
    "c": _Backend(),
    "cython": _Backend(requires=("cython", "cython-cmake")),
    "swig": _Backend(requires=("swig",)),
    "fortran": _Backend(requires=("numpy", "f2py-cmake"), dependencies=("numpy",)),
    "abi3": _Backend(tool='\n[tool.scikit-build]\nwheel.py-api = "cp310"\n'),
    "abi3t": _Backend(
        tool=(
            "\n[tool.scikit-build]\n"
            "# A free-threaded build emits the combined cp315-abi3.abi3t tag (one\n"
            "# binary for every CPython 3.15+); a GIL build falls back to abi3.\n"
            'wheel.py-api = "cp315.cp315t"\n'
        )
    ),
    "ctypes": _Backend(tool='\n[tool.scikit-build]\nwheel.py-api = "py3"\n'),
}
BACKENDS = tuple(_BACKENDS)


def _select_backend() -> str:
    """Prompt the user to pick a backend, or error if not interactive."""
    if not sys.stdin.isatty():
        rich_error(
            "No backend selected. Pass {bold}--backend{normal} (one of: {choices}).",
            choices=", ".join(BACKENDS),
        )
    rich_print("{bold}Select a binding backend:{normal}")
    for index, name in enumerate(BACKENDS, start=1):
        rich_print("  {blue}{index}{normal}) {name}", index=index, name=name)
    while True:
        choice = input(f"Enter a number [1-{len(BACKENDS)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(BACKENDS):
            return BACKENDS[int(choice) - 1]
        rich_print("{yellow}Invalid selection, try again.{normal}")


def _toml_list(items: tuple[str, ...]) -> str:
    return ", ".join(f'"{item}"' for item in items)


def _generate(
    directory: Path, backend: str, project_name: str, module: str
) -> list[Path]:
    """Render the ``common`` and ``backend`` template trees into ``directory``."""
    data = _BACKENDS[backend]
    dependencies = (
        f"\ndependencies = [{_toml_list(data.dependencies)}]"
        if data.dependencies
        else ""
    )
    substitutions = {
        "project_name": project_name,
        "module": module,
        "requires": _toml_list(("scikit-build-core", *data.requires)),
        "dependencies": dependencies,
        "tool": data.tool,
    }

    # A backend file replaces a ``common`` file with the same path.
    written: set[Path] = set()
    for root in (resources / "templates" / "common", resources / "templates" / backend):
        # Walk the tree; path components are templated too (e.g. ``${module}``).
        stack = [(root, Path())]
        while stack:
            node, rel = stack.pop()
            for entry in node.iterdir():
                name = string.Template(entry.name).safe_substitute(substitutions)
                if entry.is_dir():
                    stack.append((entry, rel / name))
                    continue
                # A ".in" suffix marks a template rendered to its bare name.
                name = name.removesuffix(".in")
                text = string.Template(
                    entry.read_text(encoding="utf-8")
                ).safe_substitute(substitutions)
                dest = directory / rel / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text.rstrip() + "\n", encoding="utf-8")
                written.add(dest)
    return sorted(written)


def _derive_module(project_name: str) -> str:
    """Derive the Python module name from a normalized project name."""
    return project_name.replace("-", "_").replace(".", "_")


def generate_project(
    directory: Path, backend: str, name: str = "example"
) -> list[Path]:
    """Render the ``backend`` template into ``directory`` as project ``name``.

    Shared entry point for the CLI, the docs example generation, and tests so
    the ``resources/templates`` tree stays the single source of truth.

    Raises :class:`packaging.utils.InvalidName` if ``name`` is not a valid
    distribution name; the derived module is substituted into template paths, so
    an unsanitized name (e.g. one containing a slash) could otherwise write
    files outside ``directory``.
    """
    project_name = canonicalize_name(name, validate=True)
    return _generate(directory, backend, project_name, _derive_module(project_name))


def _display(path: Path) -> str:
    """Show ``path`` relative to the working directory when possible."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _report(directory: Path, backend: str, module: str, written: list[Path]) -> None:
    rich_print("{bold.green}Created a {backend} project!{normal}", backend=backend)
    for path in written:
        rich_print("  {green}+{normal} {path}", path=_display(path))
    rich_print()
    rich_print("{bold}Next steps:{normal}")
    if directory != Path.cwd():
        rich_print("  {cyan}cd {directory}{normal}", directory=_display(directory))
    rich_print("  {cyan}pip install .{normal}")
    rich_print(
        '  {cyan}python -c "import {module}; print({module}.square(3))"{normal}',
        module=module,
    )


def main_init(args: argparse.Namespace, /) -> None:
    directory: Path = args.directory.resolve()
    raw_name: str = args.name or directory.name
    try:
        project_name = canonicalize_name(raw_name, validate=True)
    except InvalidName:
        rich_error(
            "Could not derive a valid project name from {raw_name!r}; pass {bold}--name{normal}.",
            raw_name=raw_name,
        )
    module = _derive_module(project_name)
    if not module.isidentifier():
        rich_error(
            "{module!r} (derived from {raw_name!r}) is not a valid Python identifier; pass a {bold}--name{normal} that starts with a letter or underscore.",
            module=module,
            raw_name=raw_name,
        )

    if directory.exists() and not directory.is_dir():
        rich_error(
            "{directory} already exists and is not a directory.",
            directory=directory,
        )

    if directory.is_dir() and any(directory.iterdir()) and not args.force:
        rich_error(
            "Directory {directory} is not empty; pass {bold}--force{normal} to generate anyway.",
            directory=directory,
        )

    backend: str = args.backend or _select_backend()
    written = _generate(directory, backend, project_name, module)
    _report(directory, backend, module, written)


def populate_parser(parser: argparse.ArgumentParser, /) -> None:
    """Add the ``init`` arguments to an existing parser."""
    parser.add_argument(
        "directory",
        type=Path,
        nargs="?",
        default=Path(),
        help="Directory to create the project in (default: current directory)",
    )
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        help="Binding backend to use (prompts interactively if omitted)",
    )
    parser.add_argument(
        "--name",
        help="Project name (default: derived from the directory name)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generate into a non-empty directory",
    )
    parser.set_defaults(func=main_init)


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scikit_build_core.init",
        allow_abbrev=False,
        description="Generate a minimal CMake + scikit-build-core starter project.",
    )
    populate_parser(parser)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
