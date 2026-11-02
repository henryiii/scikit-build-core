from __future__ import annotations

import sys
import sysconfig
import zipfile

import pytest
from packaging.utils import InvalidName

from scikit_build_core.__main__ import main
from scikit_build_core._compat import tomllib
from scikit_build_core.build import build_wheel
from scikit_build_core.init.__main__ import BACKENDS, generate_project

TYPE_CHECKING = False
if TYPE_CHECKING:
    from pathlib import Path

    from conftest import VEnv

# Source filename written into the package for each backend.
SOURCES = {
    "c": "_core.c",
    "abi3": "_core.c",
    "abi3t": "_core.c",
    "pybind11": "_core.cpp",
    "nanobind": "_core.cpp",
    "cython": "_core.pyx",
    "swig": "_core.c",
    "fortran": "_core.f",
    "ctypes": "_core.c",
}

EXTRA_REQUIRES = {
    "c": [],
    "abi3": [],
    "abi3t": [],
    "pybind11": ["pybind11"],
    "nanobind": ["nanobind"],
    "cython": ["cython", "cython-cmake"],
    "swig": ["swig"],
    "fortran": ["numpy", "f2py-cmake"],
    "ctypes": [],
}


@pytest.mark.parametrize("backend", BACKENDS)
def test_init_generates_files(backend: str, tmp_path: Path) -> None:
    project = tmp_path / "proj"
    main(["init", str(project), "--backend", backend, "--name", "my-pkg"])

    pkg = project / "src" / "my_pkg"
    assert (project / "CMakeLists.txt").is_file()
    init = (pkg / "__init__.py").read_text()
    if backend == "ctypes":
        assert "ctypes.CDLL" in init
    else:
        assert init == 'from ._core import square\n\n__all__ = ["square"]\n'
    assert (pkg / SOURCES[backend]).is_file()
    if backend == "swig":
        assert (pkg / "_core.i").is_file()

    data = tomllib.loads((project / "pyproject.toml").read_text())
    assert data["project"]["name"] == "my-pkg"
    assert data["build-system"]["requires"] == [
        "scikit-build-core",
        *EXTRA_REQUIRES[backend],
    ]

    cmake = (project / "CMakeLists.txt").read_text()
    assert "_core" in cmake
    assert "${SKBUILD_PROJECT_NAME}" in cmake


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.skipif(
    sys.implementation.name != "cpython" or sys.version_info < (3, 15),
    reason="The abi3t template requires CPython 3.15+",
)
@pytest.mark.skipif(
    sysconfig.get_platform().startswith(("win", "msys", "mingw")),
    reason="Test requires a Stable ABI filename suffix",
)
def test_init_abi3t_wheel_suffix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, virtualenv: VEnv
) -> None:
    project = tmp_path / "proj"
    generate_project(project, "abi3t", "my-pkg")
    monkeypatch.chdir(project)
    dist = tmp_path / "dist"
    dist.mkdir()

    wheel = dist / build_wheel(str(dist))
    abi = "abi3t" if sysconfig.get_config_var("Py_GIL_DISABLED") else "abi3"
    suffix = "dll" if sys.platform.startswith("cygwin") else "so"
    # FindPython may choose a platform-qualified SOSABI on Python 3.15+.
    # The template must apply scikit-build-core's selected suffix instead.
    with zipfile.ZipFile(wheel) as archive:
        assert f"my_pkg/_core.{abi}.{suffix}" in archive.namelist()

    virtualenv.install(str(wheel))
    assert virtualenv.execute("import my_pkg; print(my_pkg.square(2))") == "4.0"


@pytest.mark.compile
@pytest.mark.configure
def test_init_ctypes_wheel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, virtualenv: VEnv
) -> None:
    project = tmp_path / "proj"
    generate_project(project, "ctypes", "my-pkg")
    monkeypatch.chdir(project)
    dist = tmp_path / "dist"
    dist.mkdir()

    wheel = dist / build_wheel(str(dist))
    assert wheel.name.startswith("my_pkg-0.0.1-py3-none-")
    suffix = "dll" if sys.platform.startswith(("win", "cygwin")) else "so"
    with zipfile.ZipFile(wheel) as archive:
        assert f"my_pkg/_core.{suffix}" in archive.namelist()

    virtualenv.install(str(wheel))
    assert virtualenv.execute("import my_pkg; print(my_pkg.square(2))") == "4.0"


def test_init_default_name_from_directory(tmp_path: Path) -> None:
    project = tmp_path / "Spam.Eggs"
    main(["init", str(project), "--backend", "c"])

    data = tomllib.loads((project / "pyproject.toml").read_text())
    assert data["project"]["name"] == "spam-eggs"
    assert (project / "src" / "spam_eggs" / "_core.c").is_file()


def test_init_refuses_nonempty_directory(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("hi")
    with pytest.raises(SystemExit):
        main(["init", str(tmp_path), "--backend", "c"])
    assert not (tmp_path / "pyproject.toml").exists()


def test_init_force_into_nonempty_directory(tmp_path: Path) -> None:
    (tmp_path / "existing.txt").write_text("hi")
    main(["init", str(tmp_path), "--backend", "c", "--name", "my-pkg", "--force"])
    assert (tmp_path / "pyproject.toml").is_file()
    assert (tmp_path / "existing.txt").is_file()


def test_init_nonempty_errors_before_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A non-empty directory must error out without ever prompting for a backend.
    (tmp_path / "existing.txt").write_text("hi")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _no_input(_prompt: str) -> str:
        msg = "input() should not be called for a non-empty directory"
        raise AssertionError(msg)

    monkeypatch.setattr("builtins.input", _no_input)
    with pytest.raises(SystemExit):
        main(["init", str(tmp_path)])


def test_init_non_interactive_requires_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(SystemExit):
        main(["init", str(tmp_path)])
    assert not (tmp_path / "pyproject.toml").exists()


@pytest.mark.parametrize(
    "name", ["/abs/foo", "../evil", "foo bar", 'foo"bar', "foo/bar"]
)
def test_init_rejects_unsafe_name(name: str, tmp_path: Path) -> None:
    # An unsafe ``--name`` must error out before any files are written; otherwise
    # a slash in the derived module is substituted into template paths and writes
    # files outside the target directory.
    project = tmp_path / "proj"
    with pytest.raises(SystemExit):
        main(["init", str(project), "--backend", "c", "--name", name])
    assert not (project / "pyproject.toml").exists()
    assert list(tmp_path.iterdir()) in ([], [project])
    if project.exists():
        assert not any(project.iterdir())


@pytest.mark.parametrize("name", ["/abs/foo", "../evil", "foo bar"])
def test_generate_project_rejects_unsafe_name(name: str, tmp_path: Path) -> None:
    with pytest.raises(InvalidName):
        generate_project(tmp_path / "proj", "c", name)


def test_init_rejects_non_identifier_module(tmp_path: Path) -> None:
    # "1demo" is a valid distribution name (packaging allows leading digits) but
    # its derived module "1demo" is not a valid Python identifier; the CLI must
    # reject it up front instead of scaffolding an unimportable package.
    project = tmp_path / "proj"
    with pytest.raises(SystemExit):
        main(["init", str(project), "--backend", "c", "--name", "1demo"])
    assert not (project / "pyproject.toml").exists()


def test_init_rejects_existing_file_as_directory(tmp_path: Path) -> None:
    # A plain file at the target path must produce a clear error, not a raw
    # FileExistsError from deep inside template generation.
    target = tmp_path / "existing-file"
    target.write_text("hi")
    with pytest.raises(SystemExit):
        main(["init", str(target), "--backend", "c", "--name", "my-pkg"])


def test_init_interactive_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    # First an invalid entry, then "3" which is the "c" backend.
    answers = iter(["bogus", "3"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    project = tmp_path / "proj"
    main(["init", str(project), "--name", "my-pkg"])
    assert BACKENDS[2] == "c"
    assert (project / "src" / "my_pkg" / "_core.c").is_file()
