from __future__ import annotations

__lazy_modules__ = {
    "pathlib",
    "pathspec",
    "typing",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._logging",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.format",
}

import os
from pathlib import Path
from typing import Literal

import pathspec

from .._logging import logger
from ..format import pyproject_format

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Generator, Sequence

__all__ = ["each_unignored_file", "symlink_escapes"]

EXCLUDE_LINES = [
    ".git",
    ".tox/",
    ".nox/",
    ".egg-info/",
    "__pycache__/",
    "__pypackages__/",
    "*.pyc",
    "*.dist-info/",
]


def __dir__() -> list[str]:
    return __all__


def symlink_escapes(path: Path) -> bool:
    """
    True if the symlink at ``path`` (relative to the project root, which must
    be the current directory) has an immediate target pointing outside the
    subtree the SDist mirrors at that location: an absolute target, a Windows
    drive, or a relative target that lexically escapes the containment root.
    Such a link would dangle (or hit the wrong file) once the SDist is
    extracted somewhere else. The containment root is the project root,
    unless ``path`` was reached by following an external directory symlink --
    then it is the nearest symlink ancestor, since only that subtree mirrors
    the real directory the link resolves against. Only the immediate target
    is checked, so a chain of internal links to an eventually-external target
    stays consistent link by link (the last link is the one that gets
    resolved).
    """
    target = os.readlink(path)  # noqa: PTH115
    if os.path.isabs(target) or os.path.splitdrive(target)[0]:  # noqa: PTH117
        return True
    joined = os.path.normpath(os.path.join(os.path.dirname(path), target))  # noqa: PTH118, PTH120
    for parent in path.parents:
        if parent != Path() and parent.is_symlink():
            root = str(parent)
            return joined != root and not joined.startswith(root + os.sep)
    return joined == os.pardir or joined.startswith(os.pardir + os.sep)


def _dir_key(dirstr: str) -> tuple[int, int] | None:
    """
    Identify a directory by its (device, inode) pair so that symlink loops can
    be detected. Returns None if the directory can't be stat'd (it is then
    treated as not-yet-seen and handled normally).
    """
    try:
        st = Path(dirstr).stat()
    except OSError:
        return None
    return (st.st_dev, st.st_ino)


def _nested_ignore_dirs(starting_path: Path) -> Generator[Path, None, None]:
    """
    Directories whose ignore files can affect a walk of ``starting_path``.

    Only a nested ignore in the walked directory itself or one of its
    ancestors applies, so only ``starting_path``'s own subtree, plus the chain
    of directories above it, can ever match. Walking the whole project to
    collect the rest is pure cost: for a package that is a subdirectory it
    means traversing every sibling tree -- build outputs, vendored
    dependencies, scratch directories -- once per package.
    """
    yield from starting_path.parents
    for dirstr, _, _ in os.walk(str(starting_path)):
        yield Path(dirstr)


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (FileNotFoundError, NotADirectoryError):
        return []


def _submodule_paths(dirpath: Path) -> Generator[Path, None, None]:
    """
    Submodule roots listed in ``dirpath/.gitmodules``. An SDist has no
    ``.git`` entries, so this keeps repository boundaries when an SDist is
    made from an unpacked SDist.
    """
    for line in _read_lines(dirpath / ".gitmodules"):
        key, sep, value = line.partition("=")
        if sep and key.strip().lower() == "path" and (path := _git_config_value(value)):
            yield Path(os.path.normpath(dirpath / path))


def _git_config_value(value: str) -> str:
    """
    Decode a single-line git-config value: quotes, backslash escapes, ``#``
    and ``;`` comments, and trimming of unquoted outer whitespace.
    """
    escapes = {"n": "\n", "t": "\t", "b": "\b", '"': '"', "\\": "\\"}
    out: list[str] = []
    # Length of out up to the last quoted or non-space character.
    keep = 0
    quoted = False
    chars = iter(value.lstrip())
    for ch in chars:
        if ch == "\\":
            out.append(escapes.get(next(chars, ""), ""))
            keep = len(out)
        elif ch == '"':
            quoted = not quoted
        elif not quoted and ch in "#;":
            break
        else:
            out.append(ch)
            if quoted or not ch.isspace():
                keep = len(out)
    return "".join(out[:keep])


def each_unignored_file(
    starting_path: Path,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    build_dir: str = "",
    *,
    mode: Literal["classic", "default", "manual", "explicit"],
    resolve_symlinks: Literal["all", "external", "none", "classic", "error"] = "all",
    yield_loop_symlinks: bool = False,
) -> Generator[Path, None, None]:
    """
    Runs through all non-ignored files. Must be run from the root directory.

    ``resolve_symlinks`` controls directory symlinks: "all" and "classic"
    follow them (their contents are walked); "none" and "error" yield the link
    itself as a member instead of descending; "external" does the same only for links
    staying inside the project, still following links that point outside it.
    File symlinks are always yielded as-is here; whether they are stored
    dereferenced is up to the caller.

    A directory symlink loop is never followed; with ``yield_loop_symlinks``
    the link itself is yielded (the SDist stores it as a symlink member),
    otherwise it is skipped (wheel copying can't represent it).
    """
    # "manual" and "explicit" do not consult git ignore files at all.
    reads_gitignore = mode in {"classic", "default"}
    explicit = mode == "explicit"

    # Each repository (the project root and every submodule) has its own
    # ignore files; like git, they do not apply across a boundary.
    nested_excludes: dict[Path, pathspec.GitIgnoreSpec] = {}
    boundaries = {Path()}
    if reads_gitignore:
        for dirpath in _nested_ignore_dirs(starting_path):
            lines: list[str] = []
            if os.path.lexists(dirpath / ".git"):
                boundaries.add(dirpath)
                # Lower priority than .gitignore; the last match wins.
                lines = _read_lines(dirpath / ".git/info/exclude")
            boundaries.update(_submodule_paths(dirpath))
            lines += _read_lines(dirpath / ".gitignore")
            if lines:
                nested_excludes[dirpath] = pathspec.GitIgnoreSpec.from_lines(lines)
    ignored_boundaries = _ignored_boundaries(nested_excludes, boundaries)

    exclude_build_dir = build_dir.format(**pyproject_format(dummy=True))

    # A build-dir made only of placeholders would become "*" or "*/*" and
    # exclude source files, so skip it.
    exclude_lines = (
        [*EXCLUDE_LINES, exclude_build_dir]
        if exclude_build_dir.strip("*/")
        else EXCLUDE_LINES
    )

    user_exclude_spec = pathspec.GitIgnoreSpec.from_lines(list(exclude))
    builtin_exclude_spec = pathspec.GitIgnoreSpec.from_lines(exclude_lines)

    include_spec = pathspec.GitIgnoreSpec.from_lines(include)

    # Map each visited directory to the set of (device, inode) keys of itself
    # and all of its ancestors along the walk path. A circular symlink
    # (e.g. pkg/sub/pkg -> ../../pkg) re-enters a directory that is one of its
    # own ancestors; pruning it stops os.walk from descending forever or
    # emitting duplicated, ever-deeper copies of the same files (#1101). A
    # symlink to an unrelated directory is not an ancestor of itself, so it is
    # still followed.
    ancestor_keys: dict[str, frozenset[tuple[int, int]]] = {}

    for dirstr, dirs, filenames in os.walk(str(starting_path), followlinks=True):
        dirpath = Path(dirstr)
        repo_ignores = _repo_ignores(dirpath, nested_excludes, boundaries)
        # Entries below an ignored boundary need only the include check.
        ignored = not ignored_boundaries.isdisjoint((dirpath, *dirpath.parents))
        key = _dir_key(dirstr)
        # os.path.dirname keeps the exact string form os.walk uses for keys
        # (e.g. "" for the root), unlike Path.parent which maps it to ".".
        parent_keys = ancestor_keys.get(os.path.dirname(dirstr), frozenset())  # noqa: PTH120
        if key is not None and key in parent_keys:
            logger.debug(
                "Not descending into {} because it is an ancestor of itself "
                "(symlink loop).",
                dirpath,
            )
            dirs.clear()
            # A loop symlink can't be followed in any mode; the SDist walk
            # asks for the link itself so it isn't silently dropped. (On
            # Windows os.walk may classify it as a file instead, yielding it
            # below.)
            if (
                yield_loop_symlinks
                and dirpath.is_symlink()
                and match_path(
                    dirpath,
                    include_spec,
                    builtin_exclude_spec,
                    user_exclude_spec,
                    _repo_ignores(dirpath.parent, nested_excludes, boundaries),
                    is_path=False,
                    explicit=explicit,
                    ignored=not ignored_boundaries.isdisjoint(dirpath.parents),
                )
            ):
                yield dirpath
            continue
        if key is not None:
            ancestor_keys[dirstr] = parent_keys | {key}
        if resolve_symlinks in {"none", "external", "error"}:
            for dname in list(dirs):
                dpath = dirpath / dname
                if not dpath.is_symlink():
                    continue
                if resolve_symlinks == "external" and symlink_escapes(dpath):
                    # Points outside the mirrored subtree; keep walking it so
                    # its contents get stored instead of a dangling link.
                    continue
                # Store the link itself as a member instead of descending.
                dirs.remove(dname)
                if match_path(
                    dpath,
                    include_spec,
                    builtin_exclude_spec,
                    user_exclude_spec,
                    repo_ignores,
                    is_path=False,
                    explicit=explicit,
                    ignored=ignored,
                ):
                    yield dpath
        if mode != "classic":
            for dname in list(dirs):
                if not match_path(
                    dirpath / dname,
                    include_spec,
                    builtin_exclude_spec,
                    user_exclude_spec,
                    repo_ignores,
                    is_path=True,
                    explicit=explicit,
                    ignored=ignored,
                ):
                    # Only prune if no include pattern could match a file below
                    # this directory. A literal include deeper than the dir, or
                    # a glob include (e.g. ``pkg/**/*.py``) whose fixed prefix is
                    # this dir or an ancestor of it, must keep the dir walkable.
                    dstr = (dirpath / dname).as_posix().strip("/")
                    if not any(_include_may_match_below(p, dstr) for p in include):
                        dirs.remove(dname)

        for fn in filenames:
            path = dirpath / fn
            if match_path(
                path,
                include_spec,
                builtin_exclude_spec,
                user_exclude_spec,
                repo_ignores,
                is_path=False,
                explicit=explicit,
                ignored=ignored,
            ):
                yield path


def _include_may_match_below(pattern: str, dirpath: str) -> bool:
    """
    Decide whether an include ``pattern`` could match any file beneath the
    directory ``dirpath`` (both POSIX, leading/trailing slashes stripped).

    The fixed (glob-free) leading portion of the pattern is compared against the
    directory. A glob like ``pkg/**/*.py`` has fixed prefix ``pkg`` and could
    match below ``pkg/sub``; a literal include like ``pkg/sub/file.py`` is
    deeper than ``pkg`` and must keep ``pkg`` walkable. Both cases reduce to the
    directory and the fixed prefix sharing an ancestor relationship.
    """
    cleaned = pattern.lstrip("/")
    prefix_parts: list[str] = []
    for part in cleaned.split("/"):
        # Stop at the first segment containing a glob metacharacter.
        if any(ch in part for ch in "*?[") or part == "**":
            break
        if part:
            prefix_parts.append(part)
    prefix = "/".join(prefix_parts)
    if not prefix:
        # A leading glob (e.g. ``**/*.py``) can match anywhere below the dir.
        return True
    dir_with_sep = f"{dirpath}/"
    prefix_with_sep = f"{prefix}/"
    # dir is an ancestor of (or equal to) the fixed prefix, or vice versa.
    return prefix_with_sep.startswith(dir_with_sep) or dir_with_sep.startswith(
        prefix_with_sep
    )


def _repo_ignores(
    dirpath: Path,
    nested_excludes: dict[Path, pathspec.GitIgnoreSpec],
    boundaries: set[Path],
) -> list[tuple[Path, pathspec.GitIgnoreSpec]]:
    """
    Ignore specs that apply to entries of ``dirpath``, nearest first. Like
    git, the search stops at the repository (submodule) boundary; the entry of
    a submodule itself still belongs to the outer repository.
    """
    ignores = []
    for np in (dirpath, *dirpath.parents):
        if (spec := nested_excludes.get(np)) is not None:
            ignores.append((np, spec))
        if np in boundaries:
            break
    return ignores


def _ignored_boundaries(
    nested_excludes: dict[Path, pathspec.GitIgnoreSpec],
    boundaries: set[Path],
) -> set[Path]:
    """
    Repository boundaries that an outer repository ignores. Like git, nothing
    below such a boundary can be re-included by an ignore rule.
    """
    ignored: set[Path] = set()
    for b in sorted(boundaries - {Path()}, key=lambda b: len(b.parts)):
        if any(p in ignored for p in b.parents) or any(
            spec.check_file(f"{b.relative_to(op).as_posix()}/").include
            for op, spec in _repo_ignores(b.parent, nested_excludes, boundaries)
        ):
            ignored.add(b)
    return ignored


def match_path(
    p: Path,
    include_spec: pathspec.GitIgnoreSpec,
    builtin_exclude_spec: pathspec.GitIgnoreSpec,
    user_exclude_spec: pathspec.GitIgnoreSpec,
    repo_ignores: list[tuple[Path, pathspec.GitIgnoreSpec]],
    *,
    is_path: bool,
    explicit: bool = False,
    ignored: bool = False,
) -> bool:
    ptype = "directory" if is_path else "file"

    # In "explicit" mode the set is purely include minus exclude: nothing is in
    # unless an include matches it, and exclude is applied after (so it wins over
    # include). git ignore files are not consulted (they are empty here anyway).
    if explicit:
        if (c := user_exclude_spec.check_file(p)).include:
            assert c.index is not None
            logger.debug(
                "Excluding {} {} because it is explicitly excluded by the user with {!r}.",
                ptype,
                p,
                user_exclude_spec.patterns[c.index].pattern,
            )
            return False
        if (c := include_spec.check_file(p)).include:
            assert c.index is not None
            logger.debug(
                "Including {} {} because it is explicitly included by rule {!r}.",
                ptype,
                p,
                include_spec.patterns[c.index].pattern,
            )
            return True
        logger.debug(
            "Excluding {} {} because no include rule opts it in (explicit mode).",
            ptype,
            p,
        )
        return False

    # Always include something included
    if (c := include_spec.check_file(p)).include:
        assert c.index is not None
        logger.debug(
            "Including {} {} because it is explicitly included by rule {!r}.",
            ptype,
            p,
            include_spec.patterns[c.index].pattern,
        )
        return True

    if ignored:
        logger.debug(
            "Excluding {} {} because it is below an ignored repository boundary.",
            ptype,
            p,
        )
        return False

    # Always exclude something excluded
    if (c := user_exclude_spec.check_file(p)).include:
        assert c.index is not None
        logger.debug(
            "Excluding {} {} because it is explicitly excluded by the user with {!r}.",
            ptype,
            p,
            user_exclude_spec.patterns[c.index].pattern,
        )
        return False

    # Ignore built-in patterns
    if (c := builtin_exclude_spec.check_file(p)).include:
        assert c.index is not None
        logger.debug(
            "Excluding {} {} because it is explicitly excluded by the built-in ignore with {!r}.",
            ptype,
            p,
            builtin_exclude_spec.patterns[c.index].pattern,
        )
        return False

    # Ignore files of this repository, nearest first
    for np, nex in repo_ignores:
        if (c := nex.check_file(p.relative_to(np))).include:
            assert c.index is not None
            logger.debug(
                "Excluding {} {} because it is explicitly excluded by the ignore file in {} with {!r}.",
                ptype,
                p,
                np,
                nex.patterns[c.index].pattern,
            )
            return False

    logger.debug(
        "Including {} {} because it exists (and isn't matched any other way).", ptype, p
    )
    return True
