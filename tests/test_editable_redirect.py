from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scikit_build_core.resources import _editable_redirect
from scikit_build_core.resources._editable_redirect import (
    ScikitBuildInplaceFinder,
    ScikitBuildRedirectingFinder,
    install,
    install_inplace,
)


def process_dict_set(d: dict[str, set[str]]) -> dict[str, set[str]]:
    return {k: {str(Path(x)) for x in v} for k, v in d.items()}


def test_editable_redirect():
    # known_directories drives __path__: install-tree dirs are relative (joined
    # with `dir` at runtime), source-tree dirs are absolute. Data-only dirs
    # (pkg.resources, pkg.iresources) are present here without any module entry.
    known_directories = process_dict_set(
        {
            "pkg": {"pkg", "/source/pkg"},
            "pkg.iresources": {"pkg/iresources"},
            "pkg.namespace": {"pkg/namespace", "/source/pkg/namespace"},
            "pkg.resources": {"/source/pkg/resources"},
            "pkg.subpkg": {"pkg/subpkg", "/source/pkg/subpkg"},
        }
    )
    finder = ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={},
        known_directories={k: sorted(v) for k, v in known_directories.items()},
        known_packages=["pkg", "pkg.subpkg"],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(Path("/sitepackages")),
        install_dir="",
    )

    # Install tree first, then source tree (#1565).
    assert finder.submodule_search_locations == {
        k: [str(Path(x)) for x in v]
        for k, v in {
            "pkg": ["/sitepackages/pkg", "/source/pkg"],
            "pkg.iresources": ["/sitepackages/pkg/iresources"],
            "pkg.namespace": ["/sitepackages/pkg/namespace", "/source/pkg/namespace"],
            "pkg.resources": ["/source/pkg/resources"],
            "pkg.subpkg": ["/sitepackages/pkg/subpkg", "/source/pkg/subpkg"],
        }.items()
    }
    assert finder.pkgs == frozenset(["pkg", "pkg.subpkg"])


def test_synthesized_namespace_merges_native_portions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # A synthesized namespace spec must also carry the portions native
    # resolution would find on sys.path (e.g. a sibling distribution sharing
    # the namespace), not just the tracked directories (#1482).
    src_ns = tmp_path / "src" / "myns"
    src_ns.mkdir(parents=True)
    other_site = tmp_path / "othersite"
    sibling = other_site / "myns" / "otherpkg"
    sibling.mkdir(parents=True)
    sibling.joinpath("__init__.py").touch()
    monkeypatch.syspath_prepend(str(other_site))

    finder = ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={},
        known_directories={"myns": [str(src_ns)]},
        known_packages=[],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path / "sitepackages"),
        install_dir="",
    )

    spec = finder.find_spec("myns")
    assert spec is not None
    locations = list(spec.submodule_search_locations or [])
    assert str(src_ns) in locations
    assert str(other_site / "myns") in locations


@pytest.fixture
def _restore_meta_path():
    saved = sys.meta_path[:]
    try:
        yield
    finally:
        sys.meta_path[:] = saved


@pytest.mark.usefixtures("_restore_meta_path")
def test_install_is_idempotent():
    """PEP 829 .start entry points may be invoked more than once.

    CPython 3.15 processes a venv's site-packages twice during startup, so the
    .start entry point runs twice. ``install`` must not insert a second finder.
    """

    def count_finders() -> int:
        return sum(isinstance(f, ScikitBuildRedirectingFinder) for f in sys.meta_path)

    assert count_finders() == 0
    install({}, {}, None)
    assert count_finders() == 1
    install({}, {}, None)
    assert count_finders() == 1


@pytest.mark.usefixtures("_restore_meta_path")
def test_install_multiple_packages():
    """Several scikit-build-core editable packages can share an environment.

    Each package emits its own ``.start`` whose ``entrypoint()`` calls
    ``install`` with that package's own module maps. The idempotency guard must
    be keyed to the package, so a second (different) package still registers its
    finder, while re-running the same package's entry point does not.
    """

    def count_finders() -> int:
        return sum(isinstance(f, ScikitBuildRedirectingFinder) for f in sys.meta_path)

    pkg_a: tuple[dict[str, str], dict[str, str]] = (
        {"pkg_a": "/src/pkg_a/__init__.py"},
        {},
    )
    pkg_b: tuple[dict[str, str], dict[str, str]] = (
        {"pkg_b": "/src/pkg_b/__init__.py"},
        {},
    )

    assert count_finders() == 0
    install(*pkg_a, None)
    assert count_finders() == 1
    install(*pkg_b, None)
    assert count_finders() == 2
    # Re-running either package's entry point must not add a duplicate.
    install(*pkg_a, None)
    install(*pkg_b, None)
    assert count_finders() == 2


def test_redirect_resolves_through_path_hooks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Regression (#1492): redirected modules resolve loaders via sys.path_hooks.

    PEP 302 instrumenting import hooks (e.g. beartype.claw) register a path hook
    whose loader rewrites modules at load time. Building specs with
    spec_from_file_location hard-wires the stock SourceFileLoader, silently
    bypassing such hooks, so the finder must resolve through PathFinder instead.
    """
    import importlib.machinery
    import importlib.util

    class InstrumentingLoader(importlib.machinery.SourceFileLoader):
        # Untyped signature: Python 3.15 adds an extra positional argument.
        def source_to_code(self, data, path, *args, **kwargs):  # type: ignore[override]
            return super().source_to_code(
                b"instrumented = True\n" + data, path, *args, **kwargs
            )

    hook = importlib.machinery.FileFinder.path_hook(
        (InstrumentingLoader, importlib.machinery.SOURCE_SUFFIXES)
    )
    monkeypatch.setattr(sys, "path_hooks", [hook, *sys.path_hooks])
    monkeypatch.setattr(sys, "path_importer_cache", {})

    src_pkg = tmp_path / "src" / "pkg"
    src_pkg.mkdir(parents=True)
    init = src_pkg / "__init__.py"
    init.write_text("")
    mod = src_pkg / "mod.py"
    mod.write_text("value = 42\n")
    wheel_pkg = tmp_path / "site-packages" / "pkg"
    wheel_pkg.mkdir(parents=True)

    finder = ScikitBuildRedirectingFinder(
        known_source_files={"pkg": str(init), "pkg.mod": str(mod)},
        known_wheel_files={},
        known_directories={"pkg": [str(src_pkg), str(wheel_pkg)]},
        known_packages=["pkg"],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path / "site-packages"),
        install_dir="",
    )

    spec = finder.find_spec("pkg.mod")
    assert spec is not None
    assert spec.origin == str(mod)
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert getattr(module, "instrumented", False), "path-hook loader was bypassed"
    assert module.value == 42
    # The rebuild hook is still exposed on the wrapped loader.
    assert hasattr(spec.loader, "rebuild")

    # A package keeps its merged (source + install tree) __path__ and the
    # multi-location resource reader.
    pkg_spec = finder.find_spec("pkg")
    assert pkg_spec is not None
    assert pkg_spec.origin == str(init)
    assert set(pkg_spec.submodule_search_locations or []) == {
        str(src_pkg),
        str(wheel_pkg),
    }
    assert pkg_spec.loader is not None
    assert hasattr(pkg_spec.loader, "get_resource_reader")


def test_redirect_falls_back_when_path_hooks_miss(tmp_path: Path):
    """A mapping PathFinder cannot reproduce still resolves to the mapped file.

    If the mapped file's name does not match the module name (so the standard
    sys.path_hooks machinery cannot find it), the finder falls back to building
    the spec directly, exactly as before #1492.
    """
    import importlib.util

    actual = tmp_path / "actual_name.py"
    actual.write_text("value = 7\n")

    finder = ScikitBuildRedirectingFinder(
        known_source_files={"pkg.aliased": str(actual)},
        known_wheel_files={},
        known_directories={},
        known_packages=[],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path / "site-packages"),
        install_dir="",
    )

    spec = finder.find_spec("pkg.aliased")
    assert spec is not None
    assert spec.origin == str(actual)
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.value == 7


def _make_finder(tmp_path: Path, *, verbose: bool) -> ScikitBuildRedirectingFinder:
    return ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={},
        known_directories={},
        known_packages=[],
        path=str(tmp_path),
        rebuild=True,
        verbose=verbose,
        build_options=[],
        install_options=[],
        dir=str(tmp_path),
        install_dir="",
    )


def test_rebuild_failure_surfaces_stdout_when_not_verbose(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    """Regression: a failed non-verbose build captured stdout but never printed it.

    The error branch used ``and verbose`` (verbose already streams live), so the
    captured stdout from the failing build (e.g. MSBuild writes to stdout) was
    silently dropped. It should print when *not* verbose.
    """

    def fake_run(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert kwargs["stdout"] == subprocess.PIPE
        return subprocess.CompletedProcess(
            command, returncode=1, stdout="boom build error", stderr=""
        )

    monkeypatch.setattr("subprocess.run", fake_run)

    finder = _make_finder(tmp_path, verbose=False)
    with pytest.raises(subprocess.CalledProcessError):
        finder.rebuild()

    captured = capsys.readouterr()
    assert "boom build error" in captured.err
    # Must not print the literal "None" (the old verbose branch did this).
    assert "ERROR: None" not in captured.err


def test_rebuild_success_runs_build_and_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,  # noqa: ARG001
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    finder = _make_finder(tmp_path, verbose=False)
    finder.rebuild()

    assert calls[0][:2] == ["cmake", "--build"]
    assert calls[1][:2] == ["cmake", "--install"]


def test_find_spec_yields_inside_own_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    # When the build dir is listed in the skip marker, this process is a step
    # of the install's own CMake build; normal import resolution must win so
    # the build tree is imported, not the install tree (#1612).
    build_dir = tmp_path / "build"
    pkg = tmp_path / "site" / "pkg"
    pkg.mkdir(parents=True)
    pkg.joinpath("__init__.py").write_text("")
    finder = ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={"pkg": "pkg/__init__.py"},
        known_directories={"pkg": ["pkg"]},
        known_packages=["pkg"],
        path=str(build_dir),
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path / "site"),
        install_dir="",
    )
    monkeypatch.delenv(_editable_redirect.MARKER, raising=False)
    assert finder.find_spec("pkg") is not None

    monkeypatch.setenv(_editable_redirect.MARKER, str(tmp_path / "other"))
    assert finder.find_spec("pkg") is not None

    monkeypatch.setenv(
        _editable_redirect.MARKER,
        os.pathsep.join([str(tmp_path / "other"), str(build_dir)]),
    )
    assert finder.find_spec("pkg") is None


def test_rebuild_runs_once_per_process(tmp_path: Path):
    """Regression (#1367): rebuild fires at most once per finder, not per import.

    Importing a project like pytorch resolves many compiled modules at
    ``import torch``; each known wheel file should not re-trigger an (otherwise
    no-op) ``cmake --build``/``--install`` cycle.
    """
    finder = ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={
            "pkg._mod_a": "pkg/_mod_a.so",
            "pkg._mod_b": "pkg/_mod_b.so",
        },
        known_directories={},
        known_packages=[],
        path=str(tmp_path),
        rebuild=True,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path),
        install_dir="",
    )

    calls = 0

    def fake_rebuild() -> None:
        nonlocal calls
        calls += 1

    finder.rebuild = fake_rebuild  # type: ignore[method-assign]

    finder.find_spec("pkg._mod_a")
    finder.find_spec("pkg._mod_a")
    finder.find_spec("pkg._mod_b")

    assert calls == 1


def test_loader_exposes_rebuild(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A redirected module's loader exposes rebuild() (module.__loader__.rebuild()).

    Covers the three loader kinds the finder produces: a single-location package
    (simple wrapper), a compiled module resolved via known_wheel_files (simple
    wrapper, not a package), and a namespace package. Each must delegate to the
    finder's rebuild while still delegating other loader attributes.
    """
    import importlib.machinery

    pkg_dir = tmp_path / "src" / "pkg"
    pkg_dir.mkdir(parents=True)
    init = pkg_dir / "__init__.py"
    init.touch()

    ext = importlib.machinery.EXTENSION_SUFFIXES[0]
    so = tmp_path / "build" / "pkg" / f"_ext{ext}"
    so.parent.mkdir(parents=True)
    so.touch()

    ns_dir = tmp_path / "src" / "ns"
    ns_dir.mkdir()

    finder = ScikitBuildRedirectingFinder(
        known_source_files={"pkg": str(init)},
        known_wheel_files={"pkg._ext": str(so)},
        known_directories={"pkg": [str(pkg_dir)], "ns": [str(ns_dir)]},
        known_packages=["pkg"],
        path=str(tmp_path / "build"),
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path / "site-packages"),
        install_dir="",
    )

    calls = 0

    def fake_rebuild() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(finder, "rebuild", fake_rebuild)

    # Single-location package: simple wrapper, get_filename still delegates.
    pkg_spec = finder.find_spec("pkg")
    assert pkg_spec is not None
    assert pkg_spec.loader is not None
    pkg_spec.loader.rebuild()  # type: ignore[attr-defined]
    assert pkg_spec.loader.get_filename("pkg") == str(init)  # type: ignore[attr-defined]

    # Compiled (non-package) module resolved via known_wheel_files.
    ext_spec = finder.find_spec("pkg._ext")
    assert ext_spec is not None
    assert ext_spec.loader is not None
    ext_spec.loader.rebuild()  # type: ignore[attr-defined]

    # Namespace package.
    ns_spec = finder.find_spec("ns")
    assert ns_spec is not None
    assert ns_spec.loader is not None
    ns_spec.loader.rebuild()  # type: ignore[attr-defined]

    assert calls == 3


def test_loader_exposes_paths(tmp_path: Path):
    """Every loader the finder hands out exposes .paths (module.__loader__.paths).

    paths lists the package's search locations in __path__ order (the CMake
    install tree and the source tree), so a package can locate its install tree
    at runtime without importing scikit-build-core (#1565). A plain module has
    no search locations, so its paths is empty.
    """
    import importlib.machinery

    src_pkg = tmp_path / "src" / "pkg"
    src_pkg.mkdir(parents=True)
    init = src_pkg / "__init__.py"
    init.touch()
    (src_pkg / "mod.py").touch()
    site = tmp_path / "site-packages"
    wheel_pkg = site / "pkg"
    wheel_pkg.mkdir(parents=True)
    ext = importlib.machinery.EXTENSION_SUFFIXES[0]
    (wheel_pkg / f"_ext{ext}").touch()

    single_pkg = tmp_path / "src" / "single"
    single_pkg.mkdir()
    (single_pkg / "__init__.py").touch()

    ns_dir = tmp_path / "src" / "ns"
    ns_dir.mkdir()

    finder = ScikitBuildRedirectingFinder(
        known_source_files={
            "pkg": str(init),
            "pkg.mod": str(src_pkg / "mod.py"),
            "single": str(single_pkg / "__init__.py"),
        },
        known_wheel_files={"pkg._ext": f"pkg/_ext{ext}"},
        known_directories={
            "pkg": [str(src_pkg), "pkg"],
            "single": [str(single_pkg)],
            "ns": [str(ns_dir)],
        },
        known_packages=["pkg", "single"],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(site),
        install_dir="",
    )

    # Two search locations: paths mirrors __path__ exactly.
    pkg_spec = finder.find_spec("pkg")
    assert pkg_spec is not None
    assert pkg_spec.submodule_search_locations is not None
    paths = pkg_spec.loader.paths  # type: ignore[union-attr]
    assert paths == list(pkg_spec.submodule_search_locations)
    assert set(paths) == {str(src_pkg), str(wheel_pkg)}
    # A copy: mutating it must not change the finder's state or __path__.
    expected = list(pkg_spec.submodule_search_locations)
    paths.clear()
    assert list(pkg_spec.submodule_search_locations) == expected
    assert finder.find_spec("pkg").loader.paths == expected  # type: ignore[union-attr]
    # Delegation to the wrapped loader still works.
    assert pkg_spec.loader.get_filename("pkg") == str(init)  # type: ignore[union-attr]

    # Single search location.
    single_spec = finder.find_spec("single")
    assert single_spec is not None
    assert single_spec.loader.paths == [str(single_pkg)]  # type: ignore[union-attr]

    # Plain modules (source and compiled) have no search locations.
    for name in ("pkg.mod", "pkg._ext"):
        spec = finder.find_spec(name)
        assert spec is not None
        assert spec.loader.paths == []  # type: ignore[union-attr]

    # Namespace package.
    ns_spec = finder.find_spec("ns")
    assert ns_spec is not None
    assert ns_spec.loader.paths == [str(ns_dir)]  # type: ignore[union-attr]


def test_inplace_loader_exposes_paths(tmp_path: Path):
    """The inplace finder's loaders expose .paths too, mirroring rebuild()."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").touch()
    (pkg / "mod.py").touch()

    finder = ScikitBuildInplaceFinder(
        known_packages=["pkg"],
        search_paths=[str(tmp_path)],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
    )

    pkg_spec = finder.find_spec("pkg")
    assert pkg_spec is not None
    assert pkg_spec.loader.paths == [str(pkg)]  # type: ignore[union-attr]
    mod_spec = finder.find_spec("pkg.mod", [str(pkg)])
    assert mod_spec is not None
    assert mod_spec.loader.paths == []  # type: ignore[union-attr]


def test_multiplexed_path_paths(tmp_path: Path):
    """_SkbuildMultiplexedPath.paths lists the merged directories in order."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()

    mp = _editable_redirect._SkbuildMultiplexedPath(str(a), str(b), str(tmp_path / "x"))
    assert mp.paths == [a, b]
    mp.paths.clear()
    assert mp.paths == [a, b]


def test_loader_rebuild_without_build_dir_errors(tmp_path: Path):
    """rebuild() errors when there is no build dir to rebuild.

    A non-rebuildable editable (no persistent build-dir, path=None) still
    installs the finder and exposes the loader hook, so a rebuild request must
    raise to make the missing configuration visible. Enabling auto-rebuild
    already requires a build-dir, so the import-time path never hits this.
    """
    init = tmp_path / "pkg" / "__init__.py"
    init.parent.mkdir()
    init.touch()

    finder = ScikitBuildRedirectingFinder(
        known_source_files={"pkg": str(init)},
        known_wheel_files={},
        known_directories={"pkg": [str(init.parent)]},
        known_packages=["pkg"],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path),
        install_dir="",
    )

    with pytest.raises(RuntimeError, match="no persistent build directory"):
        finder.rebuild()

    spec = finder.find_spec("pkg")
    assert spec is not None
    assert spec.loader is not None
    with pytest.raises(RuntimeError, match="no persistent build directory"):
        spec.loader.rebuild()  # type: ignore[attr-defined]


def test_rebuild_refuses_nonrebuildable_install_dir(tmp_path: Path):
    """#1417 Bug A: an install_dir the shim can't reproduce is baked as None.

    A non-rebuild editable with a build-dir still exposes a manual
    module.__loader__.rebuild(). If wheel.install-dir points outside the platlib
    (e.g. '/data'), os.path.join(DIR, install_dir) would install to a bogus (or
    filesystem-root) path, so None is baked and rebuild() must refuse instead.
    """
    finder = ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={},
        known_directories={},
        known_packages=[],
        path=str(tmp_path),
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path),
        install_dir=None,
    )
    # The sentinel is not joined onto DIR, so no bogus path is produced.
    assert finder.install_dir is None
    with pytest.raises(RuntimeError, match="cannot be reproduced"):
        finder.rebuild()


def test_mapping_to_modules_prefers_py():
    """Test that mapping_to_modules prefers __init__.py over __init__.pxd."""
    from scikit_build_core.build._editable import mapping_to_modules

    libdir = Path("/site-packages")
    mapping = {
        "/source/pkg/__init__.py": "/site-packages/pkg/__init__.py",
        "/source/pkg/__init__.pxd": "/site-packages/pkg/__init__.pxd",
        "/source/pkg/module.py": "/site-packages/pkg/module.py",
    }
    result = mapping_to_modules(mapping, libdir)

    # Bug 3: .py should win over .pxd (currently .pxd overwrites .py)
    assert result["pkg"].endswith("__init__.py")


def test_libdir_to_installed_absolute(tmp_path: Path):
    """With absolute=True the install-tree files are recorded as absolute paths.

    Used by rebuildable editables that point at a persistent build-dir install
    tree (#1135): the redirect references the compiled artifacts there directly,
    so they need no copy in site-packages and no reconfigure on rebuild.
    """
    import importlib.machinery

    from scikit_build_core.build._editable import libdir_to_installed

    ext = importlib.machinery.EXTENSION_SUFFIXES[0]
    libdir = tmp_path / "install" / "platlib"
    mod = libdir / "pkg" / f"_module{ext}"
    mod.parent.mkdir(parents=True)
    mod.touch()

    relative = libdir_to_installed(libdir)
    assert relative == {"pkg._module": str(Path(f"pkg/_module{ext}"))}

    absolute = libdir_to_installed(libdir, absolute=True)
    assert absolute == {"pkg._module": str(mod)}
    assert Path(absolute["pkg._module"]).is_absolute()


def test_collect_search_locations_absolute(tmp_path: Path):
    """With absolute=True the install-tree __path__ entries are absolute."""
    import importlib.machinery

    from scikit_build_core.build._editable import collect_search_locations

    ext = importlib.machinery.EXTENSION_SUFFIXES[0]
    libdir = tmp_path / "install" / "platlib"
    mod = libdir / "pkg" / f"_module{ext}"
    mod.parent.mkdir(parents=True)
    mod.touch()

    directories, packages = collect_search_locations({}, libdir, absolute=True)
    assert packages == []
    assert directories == {"pkg": [str(libdir / "pkg")]}


def test_editable_redirect_external_install_tree(tmp_path: Path):
    """An external (absolute) install tree resolves and rebuilds in place (#1135).

    A rebuildable editable bakes the persistent install prefix at build time, so
    the redirect resolves compiled modules to absolute build-tree paths and the
    rebuild's ``cmake --install --prefix`` points there -- no reconfigure needed.
    """
    import importlib.machinery

    ext = importlib.machinery.EXTENSION_SUFFIXES[0]
    install_prefix = tmp_path / "build" / "install" / "platlib"
    mod = install_prefix / "pkg" / f"_module{ext}"
    mod.parent.mkdir(parents=True)
    mod.touch()

    finder = ScikitBuildRedirectingFinder(
        known_source_files={},
        known_wheel_files={"pkg._module": str(mod)},
        known_directories={"pkg": [str(install_prefix / "pkg")]},
        known_packages=[],
        path=str(tmp_path / "build"),
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(tmp_path / "site-packages"),
        install_dir=str(install_prefix),
    )

    # An absolute known_wheel_file is used verbatim, not joined under site-packages.
    spec = finder.find_spec("pkg._module")
    assert spec is not None
    assert spec.origin == str(mod)

    # The rebuild --prefix is the absolute install tree, so the cached
    # SKBUILD_<targetlib>_DIR / CMAKE_INSTALL_PREFIX stay valid without a redo.
    assert finder.install_dir == str(install_prefix)


def test_mapping_to_modules_keeps_symlink_in_package_dir(tmp_path: Path):
    """A symlinked-in module keeps its in-package directory, not the link target (#647)."""
    from scikit_build_core.build._editable import mapping_to_modules

    # A monorepo layout: shared/shared_mod.py is symlinked into src/pkg/.
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "shared_mod.py").write_text("value = 1\n")
    # An unrelated sibling file that must NOT become importable as pkg.unrelated.
    (shared / "unrelated.py").write_text("value = 2\n")

    pkg_src = tmp_path / "src" / "pkg"
    pkg_src.mkdir(parents=True)
    (pkg_src / "__init__.py").touch()
    symlink = pkg_src / "shared_mod.py"
    symlink.symlink_to(shared / "shared_mod.py")

    libdir = tmp_path / "site-packages"
    mapping = {
        str(pkg_src / "__init__.py"): str(libdir / "pkg/__init__.py"),
        str(symlink): str(libdir / "pkg/shared_mod.py"),
    }
    result = mapping_to_modules(mapping, libdir)

    # The recorded source path must stay inside the package (the symlink path),
    # not point at the resolved target dir (shared/), which would otherwise leak
    # into pkg.__path__ and make shared/unrelated.py importable as pkg.unrelated.
    assert Path(result["pkg.shared_mod"]).parent == pkg_src
    assert Path(result["pkg.shared_mod"]).parent != shared.resolve()


def test_inplace_finder_rebuild_runs_build_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """The inplace finder rebuilds with cmake --build only -- no cmake --install.

    Inplace editables compile straight into the source tree, so there is no
    install step (unlike the redirect finder, which runs both).
    """
    calls: list[list[str]] = []

    def fake_run(
        command: list[str],
        **kwargs: object,  # noqa: ARG001
    ) -> subprocess.CompletedProcess[str]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)

    finder = ScikitBuildInplaceFinder(
        known_packages=["pkg"],
        search_paths=[str(tmp_path / "src")],
        path=str(tmp_path),
        rebuild=False,
        verbose=False,
        build_options=[],
    )
    finder.rebuild()

    assert len(calls) == 1
    assert calls[0][:2] == ["cmake", "--build"]


def test_inplace_loader_exposes_rebuild(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """An inplace-built module's loader exposes rebuild() and delegates the rest.

    The finder does not change resolution (it delegates to PathFinder), it only
    wraps the loader so module.__loader__.rebuild() works. Both the top-level
    package and a submodule get wrapped.
    """
    import importlib

    src = tmp_path / "src"
    pkg_dir = src / "pkg"
    pkg_dir.mkdir(parents=True)
    init = pkg_dir / "__init__.py"
    init.touch()
    mod = pkg_dir / "mod.py"
    mod.touch()
    importlib.invalidate_caches()

    finder = ScikitBuildInplaceFinder(
        known_packages=["pkg"],
        search_paths=[str(src)],
        path=str(tmp_path),
        rebuild=False,
        verbose=False,
        build_options=[],
    )

    calls = 0

    def fake_rebuild() -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(finder, "rebuild", fake_rebuild)

    pkg_spec = finder.find_spec("pkg")
    assert pkg_spec is not None
    assert pkg_spec.loader is not None
    pkg_spec.loader.rebuild()  # type: ignore[attr-defined]
    # Non-rebuild attributes still delegate to the real loader.
    assert pkg_spec.loader.get_filename("pkg") == str(init)  # type: ignore[attr-defined]

    # A submodule is resolved against the package __path__ and also wrapped.
    mod_spec = finder.find_spec("pkg.mod", [str(pkg_dir)])
    assert mod_spec is not None
    assert mod_spec.loader is not None
    mod_spec.loader.rebuild()  # type: ignore[attr-defined]

    assert calls == 2


def test_inplace_finder_ignores_unknown(tmp_path: Path):
    """Imports outside the known packages fall through to native resolution."""
    finder = ScikitBuildInplaceFinder(
        known_packages=["pkg"],
        search_paths=[str(tmp_path)],
        path=str(tmp_path),
        rebuild=False,
        verbose=False,
        build_options=[],
    )
    assert finder.find_spec("othermod") is None


def test_inplace_import_time_rebuild_debounced(tmp_path: Path):
    """With rebuild=True, importing a known package rebuilds once per process."""
    finder = ScikitBuildInplaceFinder(
        known_packages=["pkg"],
        search_paths=[str(tmp_path)],
        path=str(tmp_path),
        rebuild=True,
        verbose=False,
        build_options=[],
    )

    calls = 0

    def fake_rebuild() -> None:
        nonlocal calls
        calls += 1

    finder.rebuild = fake_rebuild  # type: ignore[method-assign]

    finder.find_spec("pkg")
    finder.find_spec("pkg")
    finder.find_spec("pkg.sub", [str(tmp_path)])

    assert calls == 1


def test_inplace_rebuild_without_path_errors(tmp_path: Path):
    """rebuild() errors when there is no source/build dir (path=None)."""
    finder = ScikitBuildInplaceFinder(
        known_packages=["pkg"],
        search_paths=[str(tmp_path)],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
    )
    with pytest.raises(RuntimeError, match="no known source directory"):
        finder.rebuild()


@pytest.mark.usefixtures("_restore_meta_path")
def test_install_inplace_is_idempotent():
    """install_inplace dedups its own finder (PEP 829 .start may run twice)."""

    def count_finders() -> int:
        return sum(isinstance(f, ScikitBuildInplaceFinder) for f in sys.meta_path)

    assert count_finders() == 0
    install_inplace(["pkg_a"], ["/src"])
    assert count_finders() == 1
    install_inplace(["pkg_a"], ["/src"])
    assert count_finders() == 1
    # A different package still registers its own finder.
    install_inplace(["pkg_b"], ["/src"])
    assert count_finders() == 2


def test_no_expensive_module_level_imports():
    """A .pth file loads the shim at every interpreter start, so keep it cheap."""
    source = Path(_editable_redirect.__file__).read_text(encoding="utf-8")

    imported: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module != "__future__":
            imported.add(node.module or "")

    assert imported == {"os", "sys"}


_PATH_ORDER_SCRIPT = """
import os, sys
from scikit_build_core.resources._editable_redirect import ScikitBuildRedirectingFinder
site, src = sys.argv[1], sys.argv[2]
finder = ScikitBuildRedirectingFinder(
    known_source_files={"pkg": os.path.join(src, "pkg", "__init__.py")},
    known_wheel_files={},
    known_directories={"pkg": sorted([os.path.join(src, "pkg"), "pkg"])},
    known_packages=["pkg"],
    path=None, rebuild=False, verbose=False, build_options=[],
    install_options=[], dir=site, install_dir="",
)
spec = finder.find_spec("pkg")
print(*spec.submodule_search_locations, sep=os.pathsep)
"""


def test_redirect_path_order_install_first(tmp_path: Path):
    """__path__ lists the install tree before the source tree on every hash
    seed, and importlib.resources picks the install-tree copy of a file
    present in both trees (#1565)."""
    src_pkg = tmp_path / "src" / "pkg"
    (src_pkg / "data").mkdir(parents=True)
    (src_pkg / "__init__.py").write_text("")
    (src_pkg / "data" / "both.txt").write_text("source")
    site = tmp_path / "site-packages"
    install_pkg = site / "pkg"
    (install_pkg / "data").mkdir(parents=True)
    (install_pkg / "data" / "both.txt").write_text("install")

    finder = ScikitBuildRedirectingFinder(
        known_source_files={"pkg": str(src_pkg / "__init__.py")},
        known_wheel_files={},
        known_directories={"pkg": sorted([str(src_pkg), "pkg"])},
        known_packages=["pkg"],
        path=None,
        rebuild=False,
        verbose=False,
        build_options=[],
        install_options=[],
        dir=str(site),
        install_dir="",
    )
    spec = finder.find_spec("pkg")
    assert spec is not None
    assert spec.submodule_search_locations == [str(install_pkg), str(src_pkg)]
    # The spec gets a copy, so appending to it cannot change the finder.
    assert (
        spec.submodule_search_locations is not finder.submodule_search_locations["pkg"]
    )
    assert spec.loader is not None
    reader = spec.loader.get_resource_reader("pkg")  # type: ignore[attr-defined]
    assert (reader.files() / "data" / "both.txt").read_text() == "install"

    # Hash randomization is per process: several seeds must agree.
    orders = set()
    for seed in range(8):
        out = subprocess.run(
            [sys.executable, "-c", _PATH_ORDER_SCRIPT, str(site), str(src_pkg.parent)],
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            check=True,
            capture_output=True,
            text=True,
        )
        orders.add(out.stdout.strip())
    assert orders == {os.pathsep.join([str(install_pkg), str(src_pkg)])}
