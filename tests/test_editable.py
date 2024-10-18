import sys
import textwrap
from pathlib import Path

import pytest
from conftest import PackageInfo, process_package


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("isolate", [True, False], ids=["isolated", "notisolated"])
@pytest.mark.parametrize(
    "package",
    [
        pytest.param(
            True,
            id="package",
            marks=[pytest.mark.xfail(reason="Only data folders supported currently")],
        ),
        pytest.param(False, id="datafolder"),
    ],
)
@pytest.mark.usefixtures("navigate_editable")
@pytest.mark.xfail(
    sys.version_info[:2] == (3, 9), reason="Python 3.9 not supported yet"
)
def test_navigate_editable(isolated, isolate, package):
    isolate_args = ["--no-build-isolation"] if not isolate else []
    isolated.install("pip>=23")
    if not isolate:
        isolated.install("scikit-build-core")

    if package:
        init_py = Path("python/shared_pkg/data/__init__.py")
        init_py.touch()

    isolated.install(
        "-v", "--config-settings=build-dir=build/{wheel_tag}", *isolate_args, "-e", "."
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
@pytest.mark.parametrize(
    ("editable", "editable_mode"), [(False, ""), (True, "redirect"), (True, "inplace")]
)
def test_cython_pxd(monkeypatch, tmp_path, editable, editable_mode, isolated):
    editable_flag = ["-e"] if editable else []

    config_mode_flags = []
    if editable:
        config_mode_flags.append(f"--config-settings=editable.mode={editable_mode}")
    if editable_mode != "inplace":
        config_mode_flags.append("--config-settings=build-dir=build/{wheel_tag}")

    package1 = PackageInfo(
        "cython_pxd_editable/pkg1",
    )
    tmp_path1 = tmp_path / "pkg1"
    tmp_path1.mkdir()
    process_package(package1, tmp_path1, monkeypatch)

    ninja = [
        "ninja" for f in isolated.wheelhouse.iterdir() if f.name.startswith("ninja-")
    ]
    cmake = [
        "cmake" for f in isolated.wheelhouse.iterdir() if f.name.startswith("cmake-")
    ]

    isolated.install("pip>23")
    isolated.install("cython", "scikit-build-core", *ninja, *cmake)

    isolated.install(
        "-v",
        *config_mode_flags,
        "--no-build-isolation",
        *editable_flag,
        ".",
    )

    package2 = PackageInfo(
        "cython_pxd_editable/pkg2",
    )
    tmp_path2 = tmp_path / "pkg2"
    tmp_path2.mkdir()
    process_package(package2, tmp_path2, monkeypatch)

    isolated.install(
        "-v",
        *config_mode_flags,
        "--no-build-isolation",
        *editable_flag,
        ".",
    )


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.usefixtures("package_simplest_c")
def test_install_dir(isolated):
    isolated.install("pip>=23")
    isolated.install("scikit-build-core")

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
        "--no-build-isolation",
        "-e",
        ".",
    )

    # Make sure the package is correctly installed in the subdirectory
    other_pkg_path = isolated.platlib / "other_pkg"
    c_module_glob = list(other_pkg_path.glob("simplest/_module*"))
    assert len(c_module_glob) == 1
    c_module = c_module_glob[0]
    assert c_module.exists()
    # If `install-dir` was not taken into account it would install here
    failed_c_module = other_pkg_path / "../simplest" / c_module.name
    assert not failed_c_module.exists()

    # Run an import in order to re-trigger the rebuild and check paths again
    out = isolated.execute("import other_pkg.simplest")
    assert "Running cmake" in out
    assert c_module.exists()
    assert not failed_c_module.exists()


def _setup_package_for_editable_layout_tests(
    monkeypatch, tmp_path, editable, editable_mode, isolated
):
    editable_flag = ["-e"] if editable else []

    config_mode_flags = []
    if editable:
        config_mode_flags.append(f"--config-settings=editable.mode={editable_mode}")
    if editable_mode != "inplace":
        config_mode_flags.append("--config-settings=build-dir=build/{wheel_tag}")

    # Use a context so that we only change into the directory up until the point where
    # we run the editable install. We do not want to be in that directory when importing
    # to avoid importing the source directory instead of the installed package.
    with monkeypatch.context() as m:
        package = PackageInfo("importlib_editable")
        process_package(package, tmp_path, m)

        ninja = [
            "ninja"
            for f in isolated.wheelhouse.iterdir()
            if f.name.startswith("ninja-")
        ]
        cmake = [
            "cmake"
            for f in isolated.wheelhouse.iterdir()
            if f.name.startswith("cmake-")
        ]

        isolated.install("pip>23")
        isolated.install("scikit-build-core", *ninja, *cmake)

        isolated.install(
            "-v",
            *config_mode_flags,
            "--no-build-isolation",
            *editable_flag,
            ".",
        )


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize(
    ("editable", "editable_mode"), [(False, ""), (True, "redirect"), (True, "inplace")]
)
def test_direct_import(monkeypatch, tmp_path, editable, editable_mode, isolated):
    _setup_package_for_editable_layout_tests(  # type: ignore[no-untyped-call]
        monkeypatch, tmp_path, editable, editable_mode, isolated
    )
    isolated.execute("import pkg")


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize(
    ("editable", "editable_mode", "check"),
    [
        # Without editable
        (False, "", "isinstance(files(pkg), pathlib.Path)"),
        (False, "", "any(str(x).endswith('.so') for x in files(pkg).iterdir())"),
        (False, "", "isinstance(files(pkg.sub_a), pathlib.Path)"),
        (
            False,
            "",
            "any(str(x).endswith('.so') for x in files(pkg.sub_a).iterdir())",
        ),
        (False, "", "isinstance(files(pkg.sub_b), pathlib.Path)"),
        (
            False,
            "",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b).iterdir())",
        ),
        (False, "", "isinstance(files(pkg.sub_b.sub_c), pathlib.Path)"),
        (
            False,
            "",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b.sub_c).iterdir())",
        ),
        (False, "", "isinstance(files(pkg.sub_b.sub_d), pathlib.Path)"),
        (
            False,
            "",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b.sub_d).iterdir())",
        ),
        # Editable redirect
        (True, "redirect", "isinstance(files(pkg), pathlib.Path)"),
        pytest.param(
            True,
            "redirect",
            "any(str(x).endswith('.so') for x in files(pkg).iterdir())",
            marks=pytest.mark.xfail,
        ),
        (True, "redirect", "isinstance(files(pkg.sub_a), pathlib.Path)"),
        pytest.param(
            True,
            "redirect",
            "any(str(x).endswith('.so') for x in files(pkg.sub_a).iterdir())",
            marks=pytest.mark.xfail,
        ),
        (True, "redirect", "isinstance(files(pkg.sub_b), pathlib.Path)"),
        pytest.param(
            True,
            "redirect",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b).iterdir())",
            marks=pytest.mark.xfail,
        ),
        (True, "redirect", "isinstance(files(pkg.sub_b.sub_c), pathlib.Path)"),
        pytest.param(
            True,
            "redirect",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b.sub_c).iterdir())",
            marks=pytest.mark.xfail,
        ),
        (True, "redirect", "isinstance(files(pkg.sub_b.sub_d), pathlib.Path)"),
        pytest.param(
            True,
            "redirect",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b.sub_d).iterdir())",
            marks=pytest.mark.xfail,
        ),
        # Editable inplace
        (True, "inplace", "isinstance(files(pkg), pathlib.Path)"),
        (True, "inplace", "any(str(x).endswith('.so') for x in files(pkg).iterdir())"),
        (True, "inplace", "isinstance(files(pkg.sub_a), pathlib.Path)"),
        (
            True,
            "inplace",
            "any(str(x).endswith('.so') for x in files(pkg.sub_a).iterdir())",
        ),
        (True, "inplace", "isinstance(files(pkg.sub_b), pathlib.Path)"),
        (
            True,
            "inplace",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b).iterdir())",
        ),
        (True, "inplace", "isinstance(files(pkg.sub_b.sub_c), pathlib.Path)"),
        (
            True,
            "inplace",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b.sub_c).iterdir())",
        ),
        (True, "inplace", "isinstance(files(pkg.sub_b.sub_d), pathlib.Path)"),
        (
            True,
            "inplace",
            "any(str(x).endswith('.so') for x in files(pkg.sub_b.sub_d).iterdir())",
        ),
    ],
)
def test_importlib_resources(
    monkeypatch, tmp_path, editable, editable_mode, isolated, check
):
    _setup_package_for_editable_layout_tests(  # type: ignore[no-untyped-call]
        monkeypatch, tmp_path, editable, editable_mode, isolated
    )
    isolated.execute(
        textwrap.dedent(
            f"""
            from importlib.resources import files
            from importlib.readers import MultiplexedPath
            import pkg
            import pathlib
            assert {check}
            """
        )
    )
