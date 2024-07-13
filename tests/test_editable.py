import sys
import textwrap
from pathlib import Path

import pytest
from conftest import PackageInfo, process_package


@pytest.mark.compile()
@pytest.mark.configure()
@pytest.mark.integration()
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


@pytest.mark.compile()
@pytest.mark.configure()
@pytest.mark.integration()
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


@pytest.mark.compile()
@pytest.mark.configure()
@pytest.mark.integration()
@pytest.mark.parametrize(
    ("editable", "editable_mode"), [(False, ""), (True, "redirect"), (True, "inplace")]
)
def test_importlib_resources(monkeypatch, tmp_path, editable, editable_mode, isolated):
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
        package1 = PackageInfo(
            "importlib_editable",
        )
        process_package(package1, tmp_path, m)

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

    value = isolated.execute(
        textwrap.dedent(
            """
            import importlib.resources
            import example
            root = importlib.resources.files(example)
            print(any('testfile' in str(x) for x in root.iterdir()))
            """
        )
    )
    assert value == "True"
