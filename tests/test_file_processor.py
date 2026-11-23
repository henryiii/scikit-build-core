from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Literal

import pytest

from scikit_build_core.build._file_processor import (
    _git_config_value,
    each_unignored_file,
)

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture(params=["default", "classic", "manual"])
def mode(request: pytest.FixtureRequest) -> Literal["default", "classic", "manual"]:
    """
    Fixture to provide different modes for testing.
    """
    return request.param  # type: ignore[no-any-return]


def _mk_files(tmp_path: Path, files: str) -> Generator[Path, None, None]:
    """
    Create a set of files in the given temporary path based on the provided string.
    The string should contain file names and optional contents separated by a colon.
    """
    for line in files.splitlines():
        file_contents = line.strip()
        if file_contents:
            file_name, _, contents = file_contents.partition(":")
            file_path = tmp_path / file_name.strip()
            # Create parent directories if needed
            if not file_path.parent.is_dir():
                file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(contents.strip() or "content")
            yield file_path.relative_to(tmp_path)


def _setup_test_filesystem(tmp_path: Path) -> set[Path]:
    """
    Set up a test filesystem with various files and directories for testing.
    """

    return set(
        _mk_files(
            tmp_path,
            """
        README.md
        setup.py
        pyproject.toml
        src/__init__.py
        src/main.py
        src/utils.py
        tests/test_main.py
        tests/test_utils.py
        tests/tmp.py
        docs/index.md
        docs/api.rst
        temp.tmp: temporary file
        debug.log: log file
        cache.db: cache file
        local_ignored_file.txt
        __pycache__/test.pyc
        .git/config
        .gitignore: *tmp*
        .git/info/exclude: local_ignored_file.txt
        nested_dir/not_ignored.txt: not ignored file
    """,
        )
    )


@pytest.mark.skipif(
    sys.implementation.name == "pypy" and sys.platform.startswith("win"),
    reason="PyPy on Windows does not support symlinks",
)
def test_on_each_with_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test that each_unignored_file() does not follow symlinks.
    """
    monkeypatch.chdir(tmp_path)
    # Set up a gitignore
    gitignore = Path(".gitignore")
    gitignore.write_text("/hidden_dir")
    # Create a directory with a symlink to a file in the same directory
    pkg_dir = Path("pkg")
    pkg_dir.mkdir()
    file1 = pkg_dir / "file"
    file1.write_text("content")
    file2 = pkg_dir / "link"
    file2.symlink_to("file")
    hidden_dir = Path("hidden_dir")
    hidden_dir.mkdir()
    hidden_file = hidden_dir / "file2"
    hidden_file.write_text("content2")
    exposed_symlink = pkg_dir / "exposed_symlink"
    exposed_symlink.symlink_to("../hidden_dir")

    local_ignored_file = Path("local_ignored_file.txt")
    Path(".git/info").mkdir(parents=True)
    Path(".git/info/exclude").write_text(f"{local_ignored_file}\n")

    nested_dir = Path("nested_dir")
    nested_dir.mkdir()
    nested_dir.joinpath("not_ignored.txt").write_text("content")
    nested_dir.joinpath("ignored.txt").write_text("content")
    nested_dir.joinpath(".gitignore").write_text("ignored.txt")
    nested_dir.joinpath("more").mkdir()
    nested_dir.joinpath("more/ignored.txt").write_text("content")

    if (
        sys.platform.startswith("win")
        and not exposed_symlink.joinpath("file2").is_file()
    ):
        pytest.skip("Windows symlink support not available")

    # Test that each_unignored_file() follows the symlink
    files = {
        gitignore,
        file1,
        file2,
        exposed_symlink / "file2",
        nested_dir / "not_ignored.txt",
        nested_dir / ".gitignore",
    }
    if mode == "manual":
        files |= {
            hidden_file,
            nested_dir.joinpath("ignored.txt"),
            nested_dir.joinpath("more/ignored.txt"),
        }
    assert set(each_unignored_file(Path(), mode=mode)) == files


@pytest.mark.skipif(
    sys.implementation.name == "pypy" and sys.platform.startswith("win"),
    reason="PyPy on Windows does not support symlinks",
)
def test_circular_symlink_terminates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    A circular directory symlink (pkg/sub/pkg -> ../../pkg) must not make the
    walk loop forever or emit duplicated, ever-deeper copies of the same files
    (#1101).
    """
    monkeypatch.chdir(tmp_path)

    pkg = Path("pkg")
    sub = pkg / "sub"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text("content")

    loop = sub / "pkg"
    try:
        loop.symlink_to(Path("..") / ".." / "pkg")
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks not supported on this platform")
    if not loop.is_dir():
        pytest.skip("Symlink support not available")

    # Guard against an infinite loop (the pre-fix behavior on Linux) so the
    # test fails fast instead of hanging the suite.
    result: list[Path] = []
    error: list[BaseException] = []

    def _collect() -> None:
        try:
            result.extend(each_unignored_file(Path(), mode=mode))
        except BaseException as exc:  # noqa: BLE001
            error.append(exc)

    thread = threading.Thread(target=_collect, daemon=True)
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive(), "each_unignored_file did not terminate (symlink loop)"
    if error:
        raise error[0]

    # The real __init__.py must appear exactly once and there must be no
    # ever-deeper duplicates re-entering through the symlink.
    assert result.count(pkg / "__init__.py") == 1
    assert not any("sub/pkg/sub/pkg" in p.as_posix() for p in result)

    # By default the loop symlink itself is not yielded: the wheel package
    # copy can't represent a directory symlink. The sdist walk opts in.
    assert loop not in result
    with_loops = set(each_unignored_file(Path(), mode=mode, yield_loop_symlinks=True))
    assert loop in with_loops


def test_dot_git_is_a_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test that each_unignored_file() does not crash when .git is a file (e.g.,
    if the build is being run in a submodule)
    """
    monkeypatch.chdir(tmp_path)
    # Create a file named .git
    git = Path(".git")
    git.write_text("gitdir: ../../.git/modules/foo")
    # If this throws an exception, the test will fail
    assert list(each_unignored_file(Path(), mode=mode)) == []


def test_include_patterns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test that include patterns work correctly and override excludes.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Test including only Python files
    result = set(each_unignored_file(Path(), include=["*.py"], mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "debug.log",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "tests/test_utils.py",
            "tests/tmp.py",
        ]
    }
    if mode == "manual":
        expected |= {Path("temp.tmp"), Path("local_ignored_file.txt")}
    assert result == expected

    # Test including specific files
    result = set(each_unignored_file(Path(), include=["tests/tmp.py"], mode=mode))
    assert result == expected | {Path("tests/tmp.py")}

    # Test including with wildcards
    result = set(each_unignored_file(Path(), include=["tests/*"], mode=mode))
    expected = expected | {Path("tests/tmp.py")}
    assert result == expected


def test_include_pattern_with_nested_path_and_broad_exclude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that nested include patterns are not pruned by directory traversal,
    even when exclude patterns match all paths.
    """
    monkeypatch.chdir(tmp_path)
    nested_file = Path("a") / "b" / "c.txt"
    nested_file.parent.mkdir(parents=True)
    nested_file.write_text("content")

    result = set(
        each_unignored_file(
            Path(),
            include=["a/b/c.txt"],
            exclude=["*"],
            mode="manual",
        )
    )
    assert result == {nested_file}


def test_glob_include_with_broad_exclude_keeps_subpackages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Regression for #1248: ``exclude=["**/*"]`` plus glob includes like
    ``pkg/**/*.py`` must still descend into nested subdirectories. Previously
    the default mode only kept a directory if an include's literal text started
    with it, so glob-only subpackages were pruned and dropped.
    """
    monkeypatch.chdir(tmp_path)
    files = set(
        _mk_files(
            tmp_path,
            """
        pkg/__init__.py
        pkg/main.py
        pkg/ase/__init__.py
        pkg/ase/calc.py
        pkg/common/__init__.py
        pkg/common/grammar_types/__init__.py
        pkg/common/grammar_types/base.py
        pkg/data/values.csv
        pkg/data/info.py
        README.md
    """,
        )
    )

    py_files = {f for f in files if f.suffix == ".py"}

    result = set(
        each_unignored_file(
            Path(),
            include=["pkg/**/*.py"],
            exclude=["**/*"],
            mode="default",
        )
    )
    assert result == py_files

    # The same result must hold in classic mode (the pre-0.12 behavior).
    classic = set(
        each_unignored_file(
            Path(),
            include=["pkg/**/*.py"],
            exclude=["**/*"],
            mode="classic",
        )
    )
    assert classic == py_files


def test_exclude_patterns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test that exclude patterns work correctly.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Test excluding specific file types
    result = set(each_unignored_file(Path(), exclude=["*.tmp", "*.log"], mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "tests/test_utils.py",
        ]
    }
    if mode == "manual":
        expected |= {Path("tests/tmp.py"), Path("local_ignored_file.txt")}
    assert result == expected

    # Test excluding directories
    result = set(each_unignored_file(Path(), exclude=["tests/"], mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "debug.log",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
        ]
    }
    if mode == "manual":
        expected |= {Path("temp.tmp"), Path("local_ignored_file.txt")}
    assert result == expected

    # Test excluding with wildcards
    result = set(each_unignored_file(Path(), exclude=["*.py"], mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "debug.log",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
        ]
    }
    if mode == "manual":
        expected |= {Path("temp.tmp"), Path("local_ignored_file.txt")}
    assert result == expected


def test_include_overrides_exclude(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test that include patterns override exclude patterns.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Exclude all files but include specific ones
    result = set(
        each_unignored_file(
            Path(),
            include=["src/main.py", "tests/test_main.py"],
            exclude=["*"],
            mode=mode,
        )
    )
    expected = {Path(s) for s in ["src/main.py", "tests/test_main.py"]}
    assert result == expected

    # Exclude everything but include a file from inside a directory
    result = set(
        each_unignored_file(
            Path(), include=["tests/test_main.py"], exclude=["*"], mode=mode
        )
    )
    expected = {Path(s) for s in ["tests/test_main.py"]}
    assert result == expected


def test_gitignore_interaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test interaction between include/exclude and gitignore files.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Create .gitignore that excludes some files
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.tmp\n*.log\n/cache.db\n")

    # Test that gitignore is respected by default
    result = set(each_unignored_file(Path(), mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "pyproject.toml",
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "tests/test_utils.py",
            "tests/tmp.py",
            "docs/index.md",
            "docs/api.rst",
            "nested_dir/not_ignored.txt",
        ]
    }
    if mode == "manual":
        expected |= {
            Path("cache.db"),
            Path("debug.log"),
            Path("local_ignored_file.txt"),
            Path("temp.tmp"),
        }
    assert result == expected

    # Test that include can override gitignore
    result = set(each_unignored_file(Path(), include=["*.tmp"], mode=mode))
    assert result == expected | {Path("temp.tmp")}


def test_nested_gitignore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test handling of nested .gitignore files.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Create nested .gitignore in src directory
    src_gitignore = tmp_path / "src" / ".gitignore"
    src_gitignore.write_text("utils.py\n")

    # Test that nested gitignore is respected
    result = set(each_unignored_file(Path(), mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "debug.log",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
            "setup.py",
            "src/.gitignore",
            "src/__init__.py",
            "src/main.py",
            "tests/test_main.py",
            "tests/test_utils.py",
        ]
    }
    if mode == "manual":
        expected |= {
            Path("local_ignored_file.txt"),
            Path("src/utils.py"),
            Path("temp.tmp"),
            Path("tests/tmp.py"),
        }
    assert result == expected

    # Test that include can override nested gitignore
    result = set(each_unignored_file(Path(), include=["src/utils.py"], mode=mode))
    assert result == expected | {Path("src/utils.py")}


def test_build_dir_exclusion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test that build_dir parameter correctly excludes build directories.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Create build directory
    build_dir = tmp_path / "build"
    build_dir.mkdir()
    build_file = build_dir / "output.so"
    build_file.write_text("compiled output")

    # Test that build directory is excluded when specified
    result = set(each_unignored_file(Path(), build_dir="build", mode=mode))
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "debug.log",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "tests/test_utils.py",
        ]
    }
    if mode == "manual":
        expected |= {
            Path("local_ignored_file.txt"),
            Path("temp.tmp"),
            Path("tests/tmp.py"),
        }
    assert result == expected
    assert build_file.relative_to(tmp_path) not in result

    # Test that include can override build_dir exclusion
    result = set(
        each_unignored_file(Path(), include=["build/*"], build_dir="build", mode=mode)
    )
    assert result == expected | {Path("build/output.so")}


@pytest.mark.parametrize(
    "build_dir",
    [
        "{wheel_tag}",
        "{wheel_tag}{build_type}",
        "{wheel_tag}/{build_type}",
        "/{cache_tag}",
    ],
)
def test_build_dir_only_placeholders_excludes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, build_dir: str
) -> None:
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    expected = set(each_unignored_file(Path(), mode="default"))
    assert Path("src/main.py") in expected

    result = set(each_unignored_file(Path(), build_dir=build_dir, mode="default"))
    assert result == expected


def test_complex_combinations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test complex combinations of include, exclude, gitignore, and build_dir.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Set up complex scenario
    gitignore = tmp_path / ".gitignore"
    gitignore.write_text("*.tmp\ndebug.log\n")

    build_dir = tmp_path / "_build"
    build_dir.mkdir()
    build_file = build_dir / "lib.so"
    build_file.write_text("build output")

    # Complex pattern: exclude tests, include specific test, respect gitignore, exclude build
    result = set(
        each_unignored_file(
            Path(),
            include=[
                "tests/test_main.py",
                "*.tmp",
            ],  # Include specific test and override gitignore for .tmp
            exclude=["*"],  # Exclude tests dir and rst files
            build_dir="_build",
            mode=mode,
        )
    )

    expected = {
        Path(s) for s in ["tests/test_main.py", "temp.tmp"]
    }  # Only these should match
    assert result == expected


def test_empty_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test behavior with empty directory.
    """
    monkeypatch.chdir(tmp_path)

    result = list(each_unignored_file(Path(), mode=mode))
    assert result == []

    result = list(each_unignored_file(Path(), include=["*.py"], mode=mode))
    assert result == []

    result = list(each_unignored_file(Path(), exclude=["*.py"], mode=mode))
    assert result == []


def test_consecutive_excluded_dirs_not_descended(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Two consecutive excluded sibling directories must both be pruned from the
    os.walk traversal (mutating the dirs list while iterating it used to skip
    the second one, descending into the excluded tree).
    """
    monkeypatch.chdir(tmp_path)

    Path("keep.txt").write_text("content")
    for name in ("excluded_a", "excluded_b"):
        deep = Path(name) / "deep"
        deep.mkdir(parents=True)
        (deep / "inner.txt").write_text("content")

    # Track which directories the main (followlinks) traversal descends into.
    # The unrelated nested-.gitignore discovery walk is not followlinks, so it
    # is ignored here.
    descended: list[str] = []
    real_walk = os.walk

    def tracking_walk(
        top: str, *args: object, **kwargs: object
    ) -> Generator[tuple[str, list[str], list[str]], None, None]:
        track = bool(kwargs.get("followlinks"))
        for dirstr, dirs, filenames in real_walk(top, *args, **kwargs):  # type: ignore[arg-type]
            if track:
                descended.append(dirstr)
            yield dirstr, dirs, filenames

    monkeypatch.setattr(os, "walk", tracking_walk)

    result = set(
        each_unignored_file(
            Path(),
            exclude=["excluded_a", "excluded_b"],
            mode="default",
        )
    )

    assert result == {Path("keep.txt")}

    # Neither excluded directory should have been descended into. With the
    # mutate-while-iterating bug, the second sibling (excluded_b) was skipped
    # by the removal loop and therefore still walked.
    descended_paths = {Path(d) for d in descended}
    assert Path("excluded_a") not in descended_paths
    assert Path("excluded_b") not in descended_paths


def test_explicit_is_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    In "explicit" mode nothing is packaged unless it matches an include pattern.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # No include -> nothing, even though many files exist.
    assert set(each_unignored_file(Path(), mode="explicit")) == set()

    # Only included files appear; siblings are dropped (the opposite of the other
    # modes, which include everything by default).
    result = set(each_unignored_file(Path(), include=["*.py"], mode="explicit"))
    assert result == {
        Path(s)
        for s in [
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "tests/test_utils.py",
            "tests/tmp.py",
        ]
    }


def test_explicit_exclude_wins_over_include(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    In "explicit" mode exclude is applied after the opt-in, so it trims included
    files back out (in every other mode, include would win).
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    result = set(
        each_unignored_file(
            Path(),
            include=["src/**"],
            exclude=["src/utils.py"],
            mode="explicit",
        )
    )
    assert result == {Path("src/__init__.py"), Path("src/main.py")}

    # Sanity check: in "manual" mode the same include/exclude keeps utils.py,
    # because there include overrides exclude.
    manual = set(
        each_unignored_file(
            Path(),
            include=["src/**"],
            exclude=["src/utils.py"],
            mode="manual",
        )
    )
    assert Path("src/utils.py") in manual


def test_explicit_ignores_gitignore(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    "explicit" mode does not read git ignore files (like "manual").
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # src/.gitignore would hide utils.py in default/classic mode; explicit ignores
    # it, so an include still picks utils.py (and the nested .gitignore itself).
    (tmp_path / "src" / ".gitignore").write_text("utils.py\n")

    result = set(each_unignored_file(Path(), include=["src/**"], mode="explicit"))
    assert result == {
        Path(s)
        for s in [
            "src/.gitignore",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
        ]
    }


def test_nonexistent_patterns(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
) -> None:
    """
    Test behavior with patterns that don't match any files.
    """
    monkeypatch.chdir(tmp_path)
    _setup_test_filesystem(tmp_path)

    # Include pattern that matches nothing
    include_result = list(
        each_unignored_file(Path(), exclude=["*"], include=["*.nonexistent"], mode=mode)
    )
    assert include_result == []

    # Exclude pattern that matches nothing
    exclude_result = set(
        each_unignored_file(Path(), exclude=["*.nonexistent"], mode=mode)
    )
    expected = {
        Path(s)
        for s in [
            ".gitignore",
            "README.md",
            "cache.db",
            "debug.log",
            "docs/api.rst",
            "docs/index.md",
            "nested_dir/not_ignored.txt",
            "pyproject.toml",
            "setup.py",
            "src/__init__.py",
            "src/main.py",
            "src/utils.py",
            "tests/test_main.py",
            "tests/test_utils.py",
        ]
    }
    if mode == "manual":
        expected |= {
            Path("local_ignored_file.txt"),
            Path("temp.tmp"),
            Path("tests/tmp.py"),
        }
    assert exclude_result == expected


def test_nested_gitignore_scan_scoped_to_starting_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    The nested-.gitignore discovery walk must stay inside starting_path (plus
    its ancestors). match_path only consults a nested ignore whose directory
    is the walked directory or an ancestor of it, so sibling trees can never
    contribute a match -- but they used to be traversed and parsed anyway,
    once per package, which is very expensive for a project that keeps build
    output or vendored dependencies next to its packages.
    """
    monkeypatch.chdir(tmp_path)

    pkg = Path("pkg")
    (pkg / "sub").mkdir(parents=True)
    (pkg / "keep.py").write_text("content")
    (pkg / "sub" / "keep.py").write_text("content")
    (pkg / "sub" / "dropped.py").write_text("content")
    (pkg / "sub" / ".gitignore").write_text("dropped.py\n")

    # A sibling tree that is irrelevant to a walk of pkg/, carrying its own
    # .gitignore so the old code would open and parse it.
    sibling = Path("build") / "deep" / "deeper"
    sibling.mkdir(parents=True)
    (sibling / ".gitignore").write_text("keep.py\n")
    (sibling / "artifact.o").write_text("content")

    visited: list[str] = []
    real_walk = os.walk

    def tracking_walk(
        top: str, *args: object, **kwargs: object
    ) -> Generator[tuple[str, list[str], list[str]], None, None]:
        for dirstr, dirs, filenames in real_walk(top, *args, **kwargs):  # type: ignore[arg-type]
            visited.append(dirstr)
            yield dirstr, dirs, filenames

    monkeypatch.setattr(os, "walk", tracking_walk)

    result = set(each_unignored_file(pkg, mode="default"))

    # The nested .gitignore inside the package still applies.
    assert result == {
        pkg / "keep.py",
        pkg / "sub" / "keep.py",
        pkg / "sub" / ".gitignore",
    }

    # No traversal of the sibling tree, in either walk.
    visited_paths = {Path(d) for d in visited}
    assert Path("build") not in visited_paths
    assert Path("build/deep") not in visited_paths


@pytest.mark.parametrize("marker", ["git-dir", "git-file", "gitmodules"])
def test_gitignore_stops_at_repository_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Literal["default", "classic", "manual"],
    marker: str,
) -> None:
    """
    Like git, ignore rules from a superproject do not apply inside a
    submodule, and a submodule's rules do not apply inside its own nested
    submodules (#1582). An SDist has no ``.git`` entries, so ``.gitmodules``
    marks the boundaries too.
    """
    monkeypatch.chdir(tmp_path)
    Path(".gitignore").write_text("gen/\n*.log\n")
    Path(".git").mkdir()
    Path(".git/info").mkdir()
    Path(".git/info/exclude").write_text("*.bin\n")
    Path("gen").mkdir()
    Path("gen/out.txt").write_text("content")
    Path("top.log").write_text("content")

    sub = Path("third_party/sub")
    nested = sub / "nested"
    (sub / "src/gen").mkdir(parents=True)
    (nested / "src").mkdir(parents=True)
    (sub / ".gitignore").write_text("*.cpp\n")
    (sub / "src/gen/kernel.c").write_text("content")
    (sub / "notes.log").write_text("content")
    (sub / "data.bin").write_text("content")
    (sub / "own.cpp").write_text("content")
    (nested / "src/impl.cpp").write_text("content")

    if marker == "gitmodules":
        Path(".gitmodules").write_text('[submodule "sub"]\n\tpath = third_party/sub\n')
        (sub / ".gitmodules").write_text('[submodule "nested"]\n\tpath = nested\n')
    elif marker == "git-dir":
        (sub / ".git/info").mkdir(parents=True)
        (sub / ".git/info/exclude").write_text("*.tmp\n")
        (sub / "scratch.tmp").write_text("content")
        (nested / ".git").mkdir()
    else:
        (sub / ".git").write_text("gitdir: ../../.git/modules/sub\n")
        (nested / ".git").write_text("gitdir: ../../../.git/modules/nested\n")

    result = set(each_unignored_file(Path(), mode=mode))

    expected = {
        Path(".gitignore"),
        sub / ".gitignore",
        sub / "src/gen/kernel.c",
        sub / "notes.log",
        sub / "data.bin",
        nested / "src/impl.cpp",
    }
    if marker == "gitmodules":
        expected |= {Path(".gitmodules"), sub / ".gitmodules"}
    if mode == "manual":
        expected |= {Path("gen/out.txt"), Path("top.log"), sub / "own.cpp"}
        if marker == "git-dir":
            expected.add(sub / "scratch.tmp")
    assert result == expected

    # Walking from inside the submodule gives the same answer.
    assert set(each_unignored_file(sub, mode=mode)) == {
        p for p in expected if sub in p.parents
    }


@pytest.mark.parametrize("marker", ["git-dir", "gitmodules"])
@pytest.mark.parametrize("walk_from", ["root", "vendor"])
def test_ignored_repository_boundary_excludes_subtree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    marker: str,
    walk_from: str,
) -> None:
    """
    A repository inside a directory the outer repository ignores is excluded
    as a whole, even when an include keeps the directory walkable (#1593).
    """
    monkeypatch.chdir(tmp_path)
    Path(".gitignore").write_text("vendor/\n")
    lib = Path("vendor/lib")
    (lib / "src").mkdir(parents=True)
    (lib / "code.c").write_text("content")
    (lib / "src/impl.c").write_text("content")
    (lib / "keep.txt").write_text("content")
    # A repository nested in the ignored one is ignored too.
    (lib / "sub/.git").mkdir(parents=True)
    (lib / "sub/nested.c").write_text("content")
    (lib / "sub/keep.txt").write_text("content")
    if marker == "gitmodules":
        Path(".gitmodules").write_text('[submodule "lib"]\n\tpath = vendor/lib\n')
    else:
        (lib / ".git").mkdir()

    start = Path() if walk_from == "root" else Path("vendor")
    result = set(each_unignored_file(start, include=["**/keep.txt"], mode="default"))

    vendored = {p for p in result if Path("vendor") in p.parents}
    assert vendored == {lib / "keep.txt", lib / "sub/keep.txt"}


def test_gitmodules_value_syntax(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    ``.gitmodules`` keys ignore case and values follow git-config syntax.
    """
    monkeypatch.chdir(tmp_path)
    sub = Path("vendor/dep")
    sub.mkdir(parents=True)
    (sub / "run.log").write_text("content")
    Path(".gitignore").write_text("*.log\n")
    Path(".gitmodules").write_text(
        '[submodule "dep"]\n\tPath=vendor/dep ; dependency\n'
    )

    assert sub / "run.log" in set(each_unignored_file(Path(), mode="default"))


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('"a\\"b" ; c', 'a"b'),
        ("a\\\\b", "a\\b"),
        ('" a # b "', " a # b "),
        ("a  b  # c", "a  b"),
        ("a\\tb", "a\tb"),
        (' "vendor/dep" # dependency', "vendor/dep"),
        ('vendor/"a b"  ', "vendor/a b"),
    ],
)
def test_git_config_value(value: str, expected: str) -> None:
    assert _git_config_value(value) == expected
