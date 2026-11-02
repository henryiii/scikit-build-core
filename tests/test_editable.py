from __future__ import annotations

import platform
import textwrap
from pathlib import Path

import pytest


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize(
    "py_pkg",
    [
        pytest.param(
            True,
            id="package",
        ),
        pytest.param(
            False,
            id="datafolder",
        ),
    ],
)
@pytest.mark.parametrize("package", ["navigate_editable"], indirect=True)
@pytest.mark.usefixtures("package")
def test_navigate_editable(isolated, isolate, py_pkg):
    if py_pkg:
        init_py = Path("python/shared_pkg/data/__init__.py")
        init_py.touch()

    isolated.install(
        "-v",
        "--config-settings=build-dir=build/{wheel_tag}",
        *isolate.flags,
        "-e",
        ".",
        installer="pip",
    )

    value = isolated.execute("import shared_pkg; shared_pkg.call_c_method()")
    assert value == "c_method"

    value = isolated.execute("import shared_pkg; shared_pkg.call_py_method()")
    assert value == "py_method"

    value = isolated.execute("import shared_pkg; shared_pkg.read_py_data_txt()")
    assert value == "Some_value_Py"

    value = isolated.execute("import shared_pkg; shared_pkg.read_c_generated_txt()")
    assert value == "Some_value_C"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("isolate", {False}, indirect=True)
@pytest.mark.parametrize("editable", ["redirect", "inplace"], indirect=True)
@pytest.mark.parametrize(
    "multiple_packages",
    [["cython_pxd_editable/pkg1", "cython_pxd_editable/pkg2"]],
    indirect=True,
)
def test_cython_pxd(multiple_packages, editable, isolated, isolate):
    isolated.install("cython")

    # install the packages in order with one dependent on the other
    for package in multiple_packages:
        isolated.install(
            "-v",
            *isolate.flags,
            *editable.flags,
            str(package.workdir),
            installer="pip",
        )


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["simplest_c"], indirect=True)
@pytest.mark.parametrize("isolate", {False}, indirect=True)
@pytest.mark.usefixtures("package")
def test_install_dir(isolated, isolate):
    settings_overrides = {
        "build-dir": "build/{wheel_tag}",
        "wheel.install-dir": "other_pkg",
        "editable.rebuild": "true",
    }
    # Create a dummy other_pkg package to satisfy the import
    other_pkg_src = Path("./src/other_pkg")
    other_pkg_src.joinpath("simplest").mkdir(parents=True)
    other_pkg_src.joinpath("__init__.py").write_text(
        textwrap.dedent(
            """
            from .simplest._module import square
            """
        )
    )
    other_pkg_src.joinpath("simplest/__init__.py").touch()

    isolated.install(
        "-v",
        *[f"--config-settings={k}={v}" for k, v in settings_overrides.items()],
        *isolate.flags,
        "-e",
        ".",
        installer="pip",
    )

    # A rebuildable editable installs the platlib into a persistent tree inside
    # the build-dir; the redirect references it there, so nothing lands in
    # site-packages and rebuilds need no reconfigure (#1135).
    assert not list((isolated.platlib / "other_pkg").glob("simplest/_module*"))

    # The compiled module lives under the build tree, honoring wheel.install-dir
    # (other_pkg/), not at the unprefixed location (simplest/).
    install_tree = Path("build").glob("*/install/platlib")
    platlib = next(install_tree)
    c_module_glob = list(platlib.glob("other_pkg/simplest/_module*"))
    assert len(c_module_glob) == 1
    c_module = c_module_glob[0]
    assert c_module.exists()
    failed_c_module = platlib / "simplest" / c_module.name
    assert not failed_c_module.exists()

    # Run an import in order to re-trigger the rebuild and check paths again. The
    # module resolves to the build-tree copy, which is refreshed in place.
    out = isolated.execute("import other_pkg.simplest")
    assert "Running cmake" in out
    assert c_module.exists()
    assert not failed_c_module.exists()
    resolved = isolated.execute(
        "import other_pkg.simplest._module as m; print(m.__file__)"
    )
    assert resolved.splitlines()[-1] == str(c_module.resolve())
    assert str(isolated.platlib) not in resolved


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["simplest_c"], indirect=True)
@pytest.mark.parametrize("isolate", {False}, indirect=True)
@pytest.mark.usefixtures("package")
def test_rebuild_import_during_build(isolated, isolate):
    # A build step that imports the package (nanobind's stubgen, for example)
    # must resolve it from the build tree, not the install tree the redirect
    # points at: on reinstall that tree is wiped before the build, and on an
    # import-triggered rebuild it still holds the previous build (#1612).
    with Path("CMakeLists.txt").open("a", encoding="utf-8") as f:
        f.write(
            textwrap.dedent(
                """
                set_target_properties(_module PROPERTIES LIBRARY_OUTPUT_DIRECTORY
                                      "${CMAKE_BINARY_DIR}/pylib/simplest$<0:>")
                file(WRITE "${CMAKE_BINARY_DIR}/pylib/simplest/__init__.py" "")
                add_custom_target(
                  import_check ALL
                  COMMAND ${CMAKE_COMMAND} -E env "PYTHONPATH=${CMAKE_BINARY_DIR}/pylib"
                          ${Python_EXECUTABLE} -c
                          "import simplest._module as m; open('${CMAKE_BINARY_DIR}/imported.txt', 'w').write(m.__file__)"
                  DEPENDS _module
                  VERBATIM)
                """
            )
        )
    settings_overrides = {
        "build-dir": "build/{wheel_tag}",
        "editable.rebuild": "true",
    }
    install_args = [
        "-v",
        *[f"--config-settings={k}={v}" for k, v in settings_overrides.items()],
        *isolate.flags,
        "-e",
        ".",
    ]

    def imported_from() -> Path:
        imported = next(Path("build").glob("*/imported.txt"))
        resolved = Path(imported.read_text(encoding="utf-8")).resolve()
        imported.unlink()
        return resolved

    isolated.install(*install_args, installer="pip")
    build_dir = next(Path("build").glob("*")).resolve()
    assert imported_from().parent == build_dir / "pylib" / "simplest"

    # The redirect from the first install is active in the build's Python
    # processes now.
    isolated.install(*install_args, installer="pip")
    assert imported_from().parent == build_dir / "pylib" / "simplest"

    out = isolated.execute("import simplest")
    assert "Running cmake" in out
    assert imported_from().parent == build_dir / "pylib" / "simplest"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["simplest_c"], indirect=True)
@pytest.mark.parametrize("isolate", {False}, indirect=True)
@pytest.mark.usefixtures("package")
@pytest.mark.parametrize("rebuild", [None, "false"])
def test_editable_rebuild_dir(isolated, isolate, rebuild):
    # editable.rebuild-dir installs into a user-chosen tree (with the same
    # template substitutions) and turns on rebuild-on-import unless
    # editable.rebuild is explicitly false.
    settings_overrides = {
        "build-dir": "build/{wheel_tag}",
        "editable.rebuild-dir": "rebuild_tree/{wheel_tag}",
    }
    if rebuild is not None:
        settings_overrides["editable.rebuild"] = rebuild

    isolated.install(
        "-v",
        *[f"--config-settings={k}={v}" for k, v in settings_overrides.items()],
        *isolate.flags,
        "-e",
        ".",
        installer="pip",
    )

    # The install tree lands under rebuild-dir, not under build-dir/install.
    assert not list(Path("build").glob("*/install/platlib/simplest/_module*"))
    rebuild_tree = next(Path("rebuild_tree").glob("*"))
    c_module_glob = list(rebuild_tree.glob("simplest/_module*"))
    assert len(c_module_glob) == 1
    c_module = c_module_glob[0]

    # Nothing compiled lands in site-packages, and imports resolve to the
    # rebuild-dir copy, which is refreshed in place on rebuild.
    assert not list((isolated.platlib / "simplest").glob("_module*"))
    out = isolated.execute("import simplest")
    assert ("Running cmake" in out) == (rebuild is None)
    resolved = isolated.execute("import simplest._module as m; print(m.__file__)")
    assert resolved.splitlines()[-1] == str(c_module.resolve())
    assert str(isolated.platlib) not in resolved


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["simplest_c"], indirect=True)
@pytest.mark.parametrize("isolate", {False}, indirect=True)
@pytest.mark.usefixtures("package")
def test_inplace_loader_rebuild(isolated, isolate):
    # Inplace editables expose module.__loader__.rebuild(), which runs
    # cmake --build in the source tree (editable verbose is on by default).
    isolated.install(
        "-v",
        "--config-settings=editable.mode=inplace",
        *isolate.flags,
        "-e",
        ".",
        installer="pip",
    )

    out = isolated.execute(
        "import simplest; simplest.__loader__.rebuild(); print('rebuilt')"
    )
    assert "Running cmake --build" in out
    assert out.splitlines()[-1] == "rebuilt"

    # The docs-recommended pattern: rebuild via find_spec before the first
    # import, so the fresh extension is the one that gets loaded.
    out = isolated.execute(
        "import importlib.util;"
        " importlib.util.find_spec('simplest').loader.rebuild();"
        " import simplest; print('rebuilt')"
    )
    assert "Running cmake --build" in out
    assert out.splitlines()[-1] == "rebuilt"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["importlib_editable"], indirect=True)
@pytest.mark.usefixtures("package")
def test_direct_import(editable, isolated):
    # TODO: Investigate these failures
    if platform.system() == "Windows" and editable.mode == "inplace":
        pytest.xfail("Windows fails to import the top-level extension module")

    isolated.install(
        "-v",
        *editable.flags,
        ".",
        installer="pip",
    )

    isolated.execute("import pkg")
    isolated.execute("import pmod")
    isolated.execute("import emod")

    if editable.mode:
        # Both editable modes wrap the loader so module.__loader__.rebuild() is
        # available on demand (redirect via #1403, inplace via its finder).
        out = isolated.execute(
            "import pkg; print(callable(getattr(pkg.__loader__, 'rebuild', None)))"
        )
        assert out.splitlines()[-1] == "True"
        # The loader also lists the package's search locations (#1565).
        out = isolated.execute(
            "import pkg; print(pkg.__loader__.paths == list(pkg.__path__))"
        )
        assert out.splitlines()[-1] == "True"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["importlib_editable"], indirect=True)
@pytest.mark.usefixtures("package")
def test_importlib_resources(editable, isolated):
    # TODO: Investigate these failures
    if platform.system() == "Windows" and editable.mode == "inplace":
        pytest.xfail("Windows fails to import the top-level extension module")

    isolated.install(
        "-v",
        *editable.flags,
        ".",
        installer="pip",
    )

    isolated.execute(
        textwrap.dedent(
            """
            from importlib import import_module
            from importlib.resources import files
            from pathlib import Path

            def is_extension(path):
                for ext in (".so", ".pyd"):
                    if ext in path.suffixes:
                        return True
                return False

            def check_pkg(pkg_name):
                try:
                    pkg = import_module(pkg_name)
                    pkg_root = files(pkg)
                    print(f"pkg_root: [{type(pkg_root)}] {pkg_root}")
                    pkg_files = list(pkg_root.iterdir())
                    for path in pkg_files:
                        print(f"path: [{type(path)}] {path}")
                    assert any(is_extension(path) for path in pkg_files if isinstance(path, Path))
                except Exception as err:
                    msg = f"Failed in {str(pkg)}"
                    raise RuntimeError(msg) from err

            check_pkg("pkg")
            check_pkg("pkg.sub_a")
            check_pkg("pkg.sub_b")
            check_pkg("pkg.sub_b.sub_c")
            check_pkg("pkg.sub_b.sub_d")
            """
        )
    )


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["simplest_c"], indirect=True)
@pytest.mark.parametrize("isolate", {False}, indirect=True)
@pytest.mark.parametrize("editable", ["redirect", "inplace"], indirect=True)
@pytest.mark.usefixtures("package")
def test_editable_with_beartype_claw(isolated, isolate, editable):
    """beartype.claw instruments editable modules (#1492).

    beartype.claw registers a PEP 302 sys.path_hooks loader that rewrites
    modules of registered packages at load time. The editable finders must
    resolve loaders through that machinery, or instrumentation is silently
    skipped.
    """
    Path("src/simplest/typed.py").write_text("def f(x: int) -> int:\n    return x\n")

    isolated.install("beartype")
    # beartype may not support the newest Python yet (e.g. 0.22.9 fails to
    # import on 3.15); skip rather than fail, and un-skip automatically once
    # a supporting release is out.
    try:
        isolated.execute("import beartype")
    except SystemExit:
        pytest.skip("beartype cannot be imported on this Python")
    isolated.install(
        "-v",
        *isolate.flags,
        *editable.flags,
        ".",
        installer="pip",
    )

    result = isolated.execute(
        textwrap.dedent(
            """
            from beartype.claw import beartype_package
            beartype_package("simplest")
            import simplest.typed
            try:
                simplest.typed.f("not an int")
            except Exception as exc:
                print(type(exc).__name__)
            else:
                print("no error raised")
            """
        )
    )
    assert result.splitlines()[-1] == "BeartypeCallHintParamViolation"
