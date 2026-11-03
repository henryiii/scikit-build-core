from __future__ import annotations

import importlib.metadata
import subprocess
import sys
import tarfile
import textwrap
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pytest
import setuptools
import setuptools.command.sdist
from conftest import VEnv
from packaging.version import Version

from scikit_build_core._compat.setuptools.errors import SetupError
from scikit_build_core.setuptools import build_cmake, wrapper
from scikit_build_core.setuptools import build_meta as setuptools_build_meta
from scikit_build_core.setuptools.build_meta import build_sdist, build_wheel

try:
    from vcs_versioning.overrides import GlobalOverrides
except ImportError:  # pragma: no cover - setuptools-scm < 10 or missing dependency
    GlobalOverrides = None  # type: ignore[assignment, misc]

pytestmark = pytest.mark.setuptools
setuptools_version = Version(importlib.metadata.version("setuptools"))
build_editable = getattr(setuptools_build_meta, "build_editable", None)

# sdist consults build sub-commands' get_source_files() only since
# setuptools 62.4; older versions won't pick up CMakeLists.txt.
SDIST_USES_SUBCOMMAND_SOURCES = hasattr(
    setuptools.command.sdist.sdist, "_add_defaults_build_sub_commands"
)


@dataclass(frozen=True)
class SetuptoolsInstallDirCase:
    package: str
    module: str
    wheel_prefix: str
    editable_dir: Path
    wheel_missing: str | None = None


SETUPTOOLS_INSTALL_DIR_CASES = [
    SetuptoolsInstallDirCase(
        package="plugin_setuptools_install_dir",
        module="plugin_example",
        wheel_prefix="plugin_example",
        editable_dir=Path("src/plugin_example"),
    ),
    SetuptoolsInstallDirCase(
        package="wrapper_setuptools_install_dir",
        module="wrapper_example",
        wheel_prefix="wrapper_example",
        editable_dir=Path("src/wrapper_example"),
        wheel_missing="src/wrapper_example/__init__.py",
    ),
    SetuptoolsInstallDirCase(
        package="wrapper_setuptools_install_dir_pkgdir",
        module="wrapper_pkgdir",
        wheel_prefix="wrapper_pkgdir",
        editable_dir=Path("src/wrapper_pkgdir"),
        wheel_missing="src/wrapper_pkgdir/__init__.py",
    ),
]

SETUPTOOLS_INSTALL_DIR_CASE_IDS = ["plugin", "wrapper", "wrapper_pkgdir"]


def _assert_extension_import(venv: VEnv, module: str) -> None:
    add = venv.execute(f"import {module}; print({module}.add(1, 2))")
    assert add.strip() == "3"


@pytest.fixture(autouse=True)
def setuptools_scm_overrides():
    if GlobalOverrides is None:
        yield
        return

    with GlobalOverrides.from_env("SETUPTOOLS_SCM"):
        yield


@pytest.mark.parametrize("package", ["simple_setuptools_ext"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep517_sdist(tmp_path: Path):
    correct_metadata = textwrap.dedent(
        """\
        Name: cmake-example
        Version: 0.0.1
        Requires-Python: >=3.10
        Provides-Extra: test
        """
        # TODO: why is this missing?
        # Requires-Dist: pytest>=6.0; extra == "test"
        # This was removed in https://github.com/pypa/setuptools/pull/4698 as part of 2.2 support:
        # Metadata-Version: 2.1
    )
    metadata_set = set(correct_metadata.strip().splitlines())

    dist = tmp_path / "dist"
    out = build_sdist(str(dist))

    (sdist,) = dist.iterdir()
    sdist = sdist.resolve()  # Windows mingw64 and UCRT now requires this
    assert sdist.name in {"cmake-example-0.0.1.tar.gz", "cmake_example-0.0.1.tar.gz"}
    assert sdist == dist / out
    cmake_example = sdist.name[:13]

    expected = [
        "PKG-INFO",
        "src",
        "src/cmake_example.egg-info",
        "src/cmake_example.egg-info/PKG-INFO",
        "src/cmake_example.egg-info/SOURCES.txt",
        "src/cmake_example.egg-info/dependency_links.txt",
        "src/cmake_example.egg-info/not-zip-safe",
        "src/cmake_example.egg-info/requires.txt",
        "src/cmake_example.egg-info/top_level.txt",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
        "LICENSE",
    ]
    if SDIST_USES_SUBCOMMAND_SOURCES:
        expected.append("CMakeLists.txt")
        # Opted in via sdist.include in the package's pyproject.toml.
        expected.append("src/main.c")

    with tarfile.open(sdist) as f:
        file_names = set(f.getnames())
        assert file_names == {f"{cmake_example}-0.0.1/{x}" for x in expected} | {
            f"{cmake_example}-0.0.1"
        }
        pkg_info = f.extractfile(f"{cmake_example}-0.0.1/PKG-INFO")
        assert pkg_info
        pkg_info_contents = set(pkg_info.read().decode().strip().splitlines())
        assert metadata_set <= pkg_info_contents


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.broken_on_urct
@pytest.mark.parametrize("package", ["simple_setuptools_ext"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep517_wheel(virtualenv, tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    (wheel,) = dist.glob("cmake_example-0.0.1-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_names = {Path(n).parts[0] for n in zf.namelist()}

    assert len(file_names) == 2
    assert "cmake_example-0.0.1.dist-info" in file_names
    file_names.remove("cmake_example-0.0.1.dist-info")
    (so_file,) = file_names

    assert so_file.startswith("cmake_example")
    print("SOFILE:", so_file)

    virtualenv.install(wheel)

    version = virtualenv.execute(
        "import cmake_example; print(cmake_example.__version__)"
    )
    assert version.strip() == "0.0.1"

    add = virtualenv.execute("import cmake_example; print(cmake_example.add(1, 2))")
    assert add.strip() == "3"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.broken_on_urct
@pytest.mark.skipif(
    build_editable is None, reason="Requires setuptools editable support"
)
@pytest.mark.parametrize("package", ["simple_setuptools_ext"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep517_editable(virtualenv, tmp_path: Path):
    assert build_editable is not None
    dist = tmp_path / "dist"
    out = build_editable(str(dist))
    (wheel,) = dist.glob("cmake_example-0.0.1-0.editable-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_names = {Path(n).parts[0] for n in zf.namelist()}

    assert file_names == {
        "__editable__.cmake_example-0.0.1.pth",
        "cmake_example-0.0.1.dist-info",
    }

    virtualenv.install(wheel)

    module_dir = virtualenv.execute(
        "import pathlib, cmake_example; print(pathlib.Path(cmake_example.__file__).resolve().parent)"
    )
    assert Path(module_dir) == Path("src").resolve()

    version = virtualenv.execute(
        "import cmake_example; print(cmake_example.__version__)"
    )
    assert version.strip() == "0.0.1"

    add = virtualenv.execute("import cmake_example; print(cmake_example.add(1, 2))")
    assert add.strip() == "3"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.broken_on_urct
@pytest.mark.skipif(
    build_editable is None, reason="Requires setuptools editable support"
)
# _LinkTree emits an InformationOnly note about the aux dir on exit.
@pytest.mark.filterwarnings("ignore:Editable installation")
@pytest.mark.parametrize(
    "config_settings",
    [{"editable-mode": "strict"}, {"editable_mode": "strict"}],
    ids=["dash", "underscore"],
)
@pytest.mark.parametrize("package", ["simple_setuptools_ext"], indirect=True)
def test_pep517_editable_strict(virtualenv, package, config_settings, tmp_path: Path):
    # Strict mode (pip install -e . --config-settings editable_mode=strict) uses
    # setuptools' _LinkTree: unmapped build_lib outputs are copied into the
    # persistent aux dir, so the CMake artifact must NOT touch the source tree.
    assert build_editable is not None
    dist = tmp_path / "dist"
    out = build_editable(str(dist), config_settings=config_settings)
    (wheel,) = dist.glob("cmake_example-0.0.1-0.editable-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_names = {Path(n).parts[0] for n in zf.namelist()}

    assert file_names == {
        "__editable__.cmake_example-0.0.1.pth",
        "cmake_example-0.0.1.dist-info",
    }

    # The strict link tree lives in build/__editable__.<name>-<tag>/ and must
    # hold the compiled extension.
    (aux_dir,) = package.workdir.glob("build/__editable__.cmake_example-*")
    assert any(p.suffix in {".so", ".pyd", ".dylib"} for p in aux_dir.rglob("*"))

    # The key win over setuptools' build_ext: the source tree stays clean.
    src_dir = package.workdir / "src"
    assert not any(p.suffix in {".so", ".pyd", ".dylib"} for p in src_dir.rglob("*"))

    virtualenv.install(wheel)

    module_dir = virtualenv.execute(
        "import pathlib, cmake_example; print(pathlib.Path(cmake_example.__file__).resolve().parent)"
    )
    assert Path(module_dir).resolve() == aux_dir.resolve()

    version = virtualenv.execute(
        "import cmake_example; print(cmake_example.__version__)"
    )
    assert version.strip() == "0.0.1"

    add = virtualenv.execute("import cmake_example; print(cmake_example.add(1, 2))")
    assert add.strip() == "3"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.broken_on_urct
@pytest.mark.parametrize("package", ["simple_setuptools_ext"], indirect=True)
def test_build_ext_inplace_without_editable_mode(package):
    # A direct "setup.py build_ext --inplace" involves no editable wheel, so it
    # must not require editable.mode = "inplace" (classic scikit-build didn't).
    pyproject = package.workdir / "pyproject.toml"
    contents = pyproject.read_text(encoding="utf-8")
    assert 'editable.mode = "inplace"\n' in contents
    pyproject.write_text(
        contents.replace('editable.mode = "inplace"\n', ""), encoding="utf-8"
    )

    subprocess.run(
        [sys.executable, "setup.py", "build_ext", "--inplace"],
        cwd=package.workdir,
        check=True,
    )

    add = subprocess.run(
        [sys.executable, "-c", "import cmake_example; print(cmake_example.add(1, 2))"],
        cwd=package.workdir / "src",
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert add.strip() == "3"


@pytest.mark.parametrize("package", ["toml_setuptools_ext"], indirect=True)
@pytest.mark.usefixtures("package")
@pytest.mark.skipif(
    setuptools_version < Version("61.0"), reason="Requires setuptools 61+"
)
def test_toml_sdist(tmp_path: Path):
    correct_metadata = textwrap.dedent(
        """\
        Name: cmake-example
        Version: 0.0.1
        Requires-Python: >=3.10
        """
        # This was removed in https://github.com/pypa/setuptools/pull/4698 as part of 2.2 support:
        # Metadata-Version: 2.1
    )
    metadata_set = set(correct_metadata.strip().splitlines())

    dist = tmp_path / "dist"
    out = build_sdist(str(dist))

    (sdist,) = dist.iterdir()
    sdist = sdist.resolve()  # Windows mingw64 and UCRT now requires this
    assert sdist.name in {"cmake-example-0.0.1.tar.gz", "cmake_example-0.0.1.tar.gz"}
    assert sdist == dist / out
    cmake_example = sdist.name[:13]

    expected = [
        "PKG-INFO",
        "src",
        "src/cmake_example.egg-info",
        "src/cmake_example.egg-info/PKG-INFO",
        "src/cmake_example.egg-info/SOURCES.txt",
        "src/cmake_example.egg-info/dependency_links.txt",
        "src/cmake_example.egg-info/top_level.txt",
        "pyproject.toml",
        "setup.cfg",
        "LICENSE",
        # TODO: "src/main.c",
    ]
    if SDIST_USES_SUBCOMMAND_SOURCES:
        expected.append("CMakeLists.txt")

    with tarfile.open(sdist) as f:
        file_names = set(f.getnames())
        assert file_names == {f"{cmake_example}-0.0.1/{x}" for x in expected} | {
            f"{cmake_example}-0.0.1"
        }
        pkg_info = f.extractfile(f"{cmake_example}-0.0.1/PKG-INFO")
        assert pkg_info
        pkg_info_contents = set(pkg_info.read().decode().strip().splitlines())
        assert metadata_set <= pkg_info_contents


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.parametrize("package", ["toml_setuptools_ext"], indirect=True)
@pytest.mark.usefixtures("package")
@pytest.mark.skipif(
    setuptools_version < Version("61.0"), reason="Requires setuptools 61+"
)
def test_toml_wheel(virtualenv, tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    (wheel,) = dist.glob("cmake_example-0.0.1-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_names = {Path(n).parts[0] for n in zf.namelist()}

    assert len(file_names) == 2
    assert "cmake_example-0.0.1.dist-info" in file_names
    file_names.remove("cmake_example-0.0.1.dist-info")
    (so_file,) = file_names

    assert so_file.startswith("cmake_example")
    print("SOFILE:", so_file)

    virtualenv.install(wheel)

    version = virtualenv.execute(
        "import cmake_example; print(cmake_example.__version__)"
    )
    assert version.strip() == "0.0.1"

    add = virtualenv.execute("import cmake_example; print(cmake_example.add(1, 2))")
    assert add.strip() == "3"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.parametrize("package", ["mixed_setuptools"], indirect=True)
@pytest.mark.usefixtures("package")
def test_mixed_wheel(virtualenv, tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    (wheel,) = dist.glob("mixed_setuptools-3.1.4-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_names = {Path(n).parts[0] for n in zf.namelist()}

    assert len(file_names) == 2
    assert "mixed_setuptools-3.1.4.dist-info" in file_names
    file_names.remove("mixed_setuptools-3.1.4.dist-info")
    (so_file,) = file_names

    assert so_file.startswith("mixed_setuptools")
    print("SOFILE:", so_file)

    virtualenv.install(wheel)

    add = virtualenv.execute(
        "import mixed_setuptools; print(mixed_setuptools.add(1, 2))"
    )
    assert add.strip() == "3"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.xfail(
    sys.platform.startswith("cygwin"),
    reason="Cygwin fails here with ld errors",
    strict=False,
)
@pytest.mark.parametrize(
    ("package", "case"),
    [(case.package, case) for case in SETUPTOOLS_INSTALL_DIR_CASES],
    indirect=["package"],
    ids=SETUPTOOLS_INSTALL_DIR_CASE_IDS,
)
def test_cmake_install_dir_wheel(
    package, case: SetuptoolsInstallDirCase, tmp_path: Path
):
    assert package.name == case.package

    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    wheel = (dist / out).resolve()
    assert wheel.name.startswith(f"{case.wheel_prefix}-0.0.1-")

    with zipfile.ZipFile(wheel) as zf:
        file_names = set(zf.namelist())

    assert f"{case.module}/__init__.py" in file_names
    assert any(name.startswith(f"{case.module}/_core.") for name in file_names)
    if case.wheel_missing is not None:
        assert case.wheel_missing not in file_names

    venv = VEnv(tmp_path / "wheel-venv")
    venv.install(str(wheel))
    _assert_extension_import(venv, case.module)


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.xfail(
    sys.platform.startswith("cygwin"),
    reason="Cygwin fails here with ld errors",
    strict=False,
)
@pytest.mark.parametrize(
    "package", ["wrapper_setuptools_classic_layout"], indirect=True
)
@pytest.mark.usefixtures("package")
def test_wrapper_classic_layout_wheel(tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    wheel = (dist / out).resolve()

    with zipfile.ZipFile(wheel) as zf:
        file_names = set(zf.namelist())

    assert "classic_layout_example/__init__.py" in file_names
    assert any(name.startswith("classic_layout_example/_core.") for name in file_names)
    assert any(
        name.endswith(".data/data/include/classic_layout_example/example.h")
        for name in file_names
    )
    assert not any(
        name.startswith("python/classic_layout_example/") for name in file_names
    )
    assert not any(name.startswith("include/") for name in file_names)

    venv = VEnv(tmp_path / "classic-layout-venv")
    venv.install(str(wheel))
    _assert_extension_import(venv, "classic_layout_example")


def test_wrapper_staged_install_layout(tmp_path: Path):
    """The wrapper stages the CMake install at
    <build_ext build_temp>/_skbuild/cmake-install. Classic scikit-build's
    skbuild.constants.CMAKE_INSTALL_DIR() compat shim advertises this path to
    downstream setup.py files (the DracoPy pattern); coordinate with
    scikit-build before changing the layout."""
    dist = setuptools.Distribution()
    setattr(dist, build_cmake.WRAPPER_COMPAT, True)
    cmd = build_cmake.BuildCMake(dist)
    # Non-editable build: classic-layout compat is active.
    cmd._editable_mode = build_cmake._EditableMode.DISABLED

    build_temp = tmp_path / "_skbuild"
    assert cmd._get_staged_install_prefix(build_temp) == build_temp / "cmake-install"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.skipif(
    build_editable is None, reason="Requires setuptools editable support"
)
@pytest.mark.xfail(
    sys.platform.startswith("cygwin"),
    reason="Cygwin fails here with ld errors",
    strict=False,
)
# Per-package package_dir makes setuptools fall back to the meta-path finder,
# which emits an InformationOnly note (turned into an error by filterwarnings).
@pytest.mark.filterwarnings("ignore:Editable installation")
@pytest.mark.parametrize(
    ("package", "case"),
    [(case.package, case) for case in SETUPTOOLS_INSTALL_DIR_CASES],
    indirect=["package"],
    ids=SETUPTOOLS_INSTALL_DIR_CASE_IDS,
)
def test_cmake_install_dir_editable(
    package, case: SetuptoolsInstallDirCase, tmp_path: Path
):
    assert build_editable is not None
    assert package.name == case.package

    dist = tmp_path / "dist"
    out = build_editable(str(dist))
    wheel = (dist / out).resolve()
    assert wheel.name.startswith(f"{case.wheel_prefix}-0.0.1-0.editable-")

    venv = VEnv(tmp_path / "editable-venv")
    venv.install(wheel)

    module_dir = venv.execute(
        f"import pathlib, {case.module}; print(pathlib.Path({case.module}.__file__).resolve().parent)"
    )
    assert Path(module_dir) == (package.workdir / case.editable_dir).resolve()
    _assert_extension_import(venv, case.module)


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.broken_on_urct
@pytest.mark.parametrize("package", ["simple_setuptools_ext"], indirect=True)
@pytest.mark.usefixtures("package")
def test_manifest_hook_wheel(virtualenv, tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    (wheel,) = dist.glob("cmake_example-0.0.1-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_names = set(zf.namelist())

    assert "LICENSE" not in file_names
    assert any(Path(name).stem.startswith("cmake_example") for name in file_names)

    virtualenv.install(wheel)
    add = virtualenv.execute("import cmake_example; print(cmake_example.add(1, 2))")
    assert add.strip() == "3"


@pytest.mark.parametrize("wrapper_compat", [True, False], ids=["wrapper", "plugin"])
def test_skbuild_configure_and_build_options(
    wrapper_compat: bool, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Classic scikit-build compatibility env vars, honored only by the wrapper
    # (scikit_build_core.setuptools.wrapper.setup), not the general plugin.
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CMakeLists.txt").touch()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("SKBUILD_CONFIGURE_OPTIONS", "-DFOO=ON -DBAR='a b'")
    monkeypatch.setenv("SKBUILD_BUILD_OPTIONS", "-- -l4")

    captured: dict[str, list[str]] = {}

    class StopRunError(Exception):
        pass

    class FakeConfig:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            self.env: dict[str, str] = {}
            self.build_type = "Release"

    class FakeBuilder:
        def __init__(self, *, config: object, **_kwargs: object) -> None:
            self.config = config

        def get_cmake_args(self) -> list[str]:
            return []

        def configure(self, *, configure_args: list[str], **_kwargs: object) -> None:
            captured["configure"] = list(configure_args)

        def build(self, *, build_args: list[str]) -> None:
            captured["build"] = list(build_args)
            raise StopRunError

    monkeypatch.setattr(
        "scikit_build_core.cmake.CMake.default_search",
        classmethod(lambda *_args, **_kwargs: object()),
    )
    monkeypatch.setattr(build_cmake, "CMaker", FakeConfig)
    monkeypatch.setattr(build_cmake, "Builder", FakeBuilder)

    dist = setuptools.Distribution({"name": "x", "version": "0.0.1"})
    if wrapper_compat:
        setattr(dist, build_cmake.WRAPPER_COMPAT, True)
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.build_lib = str(tmp_path / "build")
    cmd.build_temp = str(tmp_path / "tmp")
    cmd.plat_name = "linux-x86_64"
    cmd.source_dir = "."
    cmd.cmake_args = ["-DDIST=1"]

    with pytest.raises(StopRunError):
        cmd.run()

    if wrapper_compat:
        assert captured["configure"] == ["-DDIST=1", "-DFOO=ON", "-DBAR=a b"]
        assert captured["build"] == ["--", "-l4"]
    else:
        assert captured["configure"] == ["-DDIST=1"]
        assert captured["build"] == []


def test_manifest_hook_must_be_callable():
    with pytest.raises(
        SetupError,
        match="cmake_process_manifest_hook must be callable",
    ):
        build_cmake.cmake_process_manifest_hook(
            setuptools.Distribution(),
            "cmake_process_manifest_hook",
            object(),  # type: ignore[arg-type]
        )


def test_validate_settings_raises_setup_error():
    # Must use a real exception (not bare assert) so it survives python -O.
    settings = build_cmake._load_settings()
    settings.wheel.py_api = "cp39"
    with pytest.raises(SetupError, match=r"wheel\.py_api is not supported"):
        build_cmake._validate_settings(settings)


def test_validate_settings_rejects_build_type_list():
    # The setuptools plugin builds a single config; a multi-config build-type
    # list would be silently truncated to the first entry, so reject it.
    settings = build_cmake._load_settings()
    settings.cmake.build_type = ["Release", "Debug"]
    with pytest.raises(SetupError, match=r"cmake\.build-type lists"):
        build_cmake._validate_settings(settings)


def test_validate_settings_allows_single_build_type_list():
    settings = build_cmake._load_settings()
    settings.cmake.build_type = ["Release"]
    build_cmake._validate_settings(settings)


def test_editable_install_dir_honors_per_package_dir(tmp_path, monkeypatch):
    # Per-package package_dir (as opposed to {"": "src"}): the wrapper
    # translates cmake_install_dir relative to src, so the editable source root
    # must also be src, not "." (which would create a junk ./wrapper_example).
    monkeypatch.chdir(tmp_path)
    # Materialize the source tree: resolving a nonexistent path is unreliable
    # before Python 3.10 (Windows leaves it relative), and samefile below needs
    # to stat it. A real editable install always has the source present.
    (tmp_path / "src" / "wrapper_example").mkdir(parents=True)
    dist = setuptools.Distribution(
        {
            "name": "wrapper-example",
            "version": "0.0.1",
            "packages": ["wrapper_example"],
            "package_dir": {"wrapper_example": "src/wrapper_example"},
        }
    )
    setattr(dist, build_cmake.WRAPPER_COMPAT, True)
    dist.cmake_install_dir = "src/wrapper_example"  # type: ignore[attr-defined]

    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.build_lib = str(tmp_path / "build")
    cmd._editable_mode = build_cmake._EditableMode.LENIENT

    install_dir = cmd._get_install_dir()
    # samefile compares stat identity, immune to Windows 8.3 short-name
    # aliasing (RUNNER~1 vs runneradmin) that resolve() misses on cygwin.
    assert install_dir.is_absolute()
    assert install_dir.samefile(tmp_path / "src" / "wrapper_example")


def test_finalize_options_honors_directly_set_editable_mode():
    # editable_wheel's SubCommand protocol sets cmd.editable_mode = True
    # directly on build sub-commands before finalize_options runs; build_ext's
    # own flags (editable_mode/inplace both False here) must not clobber it.
    dist = setuptools.Distribution({"name": "cmake-example", "version": "0.0.1"})
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.editable_mode = True

    cmd.finalize_options()

    assert cmd.editable_mode is True
    # No editable_wheel command object with mode="strict", so LENIENT.
    assert cmd._editable_mode is build_cmake._EditableMode.LENIENT


def test_get_source_files_finds_configured_cmakelists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub" / "deps").mkdir(parents=True)
    (tmp_path / "sub" / "CMakeLists.txt").touch()
    # The entry-point pattern is anchored, so nested ones don't match.
    (tmp_path / "sub" / "deps" / "CMakeLists.txt").touch()

    dist = setuptools.Distribution({"name": "cmake-example", "version": "0.0.1"})
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.source_dir = "sub"

    assert cmd.get_source_files() == ["sub/CMakeLists.txt"]


def test_get_source_files_empty_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    dist = setuptools.Distribution({"name": "cmake-example", "version": "0.0.1"})
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.source_dir = "sub"  # never created

    assert cmd.get_source_files() == []


def test_get_source_files_honors_sdist_include_exclude(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CMakeLists.txt").touch()
    src = tmp_path / "src"
    src.mkdir()
    (src / "main.c").touch()
    (src / "vendored.c").touch()
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            sdist.inclusion-mode = "explicit"
            sdist.include = ["src/*.c"]
            sdist.exclude = ["src/vendored.c"]
            """
        ),
        encoding="utf-8",
    )

    dist = setuptools.Distribution({"name": "cmake-example", "version": "0.0.1"})
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.source_dir = "."

    assert cmd.get_source_files() == ["CMakeLists.txt", "src/main.c"]


def test_get_source_files_requires_explicit_inclusion_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "CMakeLists.txt").touch()
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            sdist.include = ["src/*.c"]
            """
        ),
        encoding="utf-8",
    )

    dist = setuptools.Distribution({"name": "cmake-example", "version": "0.0.1"})
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.source_dir = "."

    with pytest.raises(SetupError, match=r"inclusion-mode = .explicit."):
        cmd.get_source_files()


def test_validate_settings_editable_mode_only_required_for_pep660():
    settings = build_cmake._load_settings()
    assert settings.editable.mode == "redirect"
    # Plain builds (including build_ext --inplace) don't require the setting.
    build_cmake._validate_settings(settings)
    with pytest.raises(SetupError, match=r"editable\.mode = 'inplace'"):
        build_cmake._validate_settings(settings, pep660_editable=True)


def test_wrapper_setup_raises_setup_error():
    with pytest.raises(SetupError, match="cmake_with_sdist not supported"):
        wrapper.setup(cmake_with_sdist=True)


def test_cmake_install_target_keyword_validates_type():
    with pytest.raises(SetupError, match="cmake_install_target must be a string"):
        build_cmake.cmake_install_target(
            setuptools.Distribution(),
            "cmake_install_target",
            object(),  # type: ignore[arg-type]
        )


def test_cmake_install_target_maps_to_install_targets():
    settings = build_cmake._load_settings()
    settings.install.targets = ["existing"]
    dist = setuptools.Distribution()
    dist.cmake_install_target = "install-distribution"  # type: ignore[attr-defined]
    new = build_cmake._apply_cmake_install_target(settings, dist)
    assert new.install.targets == ["existing", "install-distribution"]
    assert settings.install.targets == ["existing"]


@pytest.mark.parametrize("target", [None, "install"])
def test_cmake_install_target_default_is_noop(target):
    settings = build_cmake._load_settings()
    dist = setuptools.Distribution()
    if target is not None:
        dist.cmake_install_target = target  # type: ignore[attr-defined]
    assert build_cmake._apply_cmake_install_target(settings, dist) is settings


def test_load_settings_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            wheel.cmake = false

            [[tool.scikit-build.overrides]]
            if.state = "editable"
            wheel.cmake = true
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    # Default state is sdist, so the editable override should not apply.
    assert build_cmake._load_settings().wheel.cmake is False
    assert build_cmake._load_settings(state="wheel").wheel.cmake is False
    assert build_cmake._load_settings(state="editable").wheel.cmake is True


@pytest.mark.skipif(
    build_editable is None, reason="Requires setuptools editable support"
)
def test_build_editable_threads_config_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # A config-setting like `pip install -e . -C editable.mode=inplace` must be
    # visible to build_cmake, not only to the metadata/validation hook. Without
    # threading, the build half loads default settings and rejects the install.
    import setuptools.build_meta

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.scikit-build]\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    captured: dict[str, str] = {}

    def fake_build_editable(
        _wheel_directory: str,
        _config_settings: dict[str, str | list[str]] | None = None,
        _metadata_directory: str | None = None,
    ) -> str:
        settings = build_cmake._load_settings(state="editable")
        captured["mode"] = settings.editable.mode
        # Must not raise "requires editable.mode = 'inplace'".
        build_cmake._validate_settings(settings, pep660_editable=True)
        return "wheel"

    monkeypatch.setattr(setuptools.build_meta, "build_editable", fake_build_editable)

    assert build_editable is not None
    result = build_editable(str(tmp_path), {"editable.mode": "inplace"})
    assert result == "wheel"
    assert captured["mode"] == "inplace"


def test_wrapper_forwards_manifest_hook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Without a CMakeLists.txt, the wrapper skips CMake entirely
    (tmp_path / "CMakeLists.txt").touch()
    monkeypatch.chdir(tmp_path)

    dist = setuptools.Distribution()

    def passthrough_hook(cmake_manifest: list[str]) -> list[str]:
        return cmake_manifest

    def fake_setup(**kwargs: object) -> setuptools.Distribution:
        assert kwargs["cmake_process_manifest_hook"] is passthrough_hook
        return dist

    monkeypatch.setattr(setuptools, "setup", fake_setup)

    assert (
        wrapper.setup(
            cmake_source_dir=".",
            cmake_process_manifest_hook=passthrough_hook,
        )
        is dist
    )


def test_get_requires_uses_hook_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # Each hook must read the settings with its own state, so that
    # `if.state = "wheel"` / `"editable"` overrides reach the injected
    # cmake requirement.
    (tmp_path / "CMakeLists.txt").write_text(
        "cmake_minimum_required(VERSION 3.15)\n", encoding="utf-8"
    )
    (tmp_path / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["setuptools", "scikit-build-core"]
            build-backend = "scikit_build_core.setuptools.build_meta"

            [project]
            name = "state-example"
            version = "0.0.1"

            [tool.scikit-build]
            sdist.cmake = true

            [[tool.scikit-build.overrides]]
            if.state = "wheel"
            cmake.version = ">=99.1"

            [[tool.scikit-build.overrides]]
            if.state = "editable"
            cmake.version = ">=99.2"
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("CMAKE_EXECUTABLE", raising=False)
    monkeypatch.chdir(tmp_path)

    assert "cmake>=99.1" in setuptools_build_meta.get_requires_for_build_wheel()

    sdist_requires = setuptools_build_meta.get_requires_for_build_sdist()
    assert not [r for r in sdist_requires if r.startswith("cmake>=99")]

    get_requires_for_build_editable = getattr(
        setuptools_build_meta, "get_requires_for_build_editable", None
    )
    if get_requires_for_build_editable is not None:
        assert "cmake>=99.2" in get_requires_for_build_editable()


def test_finalize_options_parses_cmake_args():
    # Separators must not produce empty arguments, and a quoted value must stay
    # a single argument.
    dist = setuptools.Distribution({"name": "cmake-example", "version": "0.0.1"})
    cmd = build_cmake.BuildCMake(dist)
    cmd.initialize_options()
    cmd.cmake_args = '-DA=1;;-DB=2  -DC="x y"  ; '

    cmd.finalize_options()

    result: list[str] | str | None = cmd.cmake_args
    assert result == ["-DA=1", "-DB=2", "-DC=x y"]
