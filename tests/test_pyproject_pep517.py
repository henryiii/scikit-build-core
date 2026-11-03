import gzip
import hashlib
import inspect
import shutil
import sys
import tarfile
import time
import zipfile
from importlib.metadata import PathDistribution
from pathlib import Path

import pytest

from scikit_build_core.build import (
    _file_processor,
    build_sdist,
    build_wheel,
    prepare_metadata_for_build_wheel,
)

ENTRYPOINTS = """\
[one.two]
three = four

[console_scripts]
something = other

[gui_scripts]
guithing = a.b:c
"""

mark_hashes_different = pytest.mark.xfail(
    sys.platform.startswith(("win", "cygwin")),
    reason="hashes differ on Windows",
    strict=False,
)


def compute_uncompressed_hash(inp: Path) -> str:
    with gzip.open(inp, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


@pytest.mark.usefixtures("package_simple_pyproject_ext")
def test_pep517_sdist(tmp_path: Path):
    expected_metadata = (
        inspect.cleandoc(
            """
            Metadata-Version: 2.2
            Name: CMake.Example
            Version: 0.0.1
            Requires-Python: >=3.10
            Provides-Extra: test
            Requires-Dist: pytest>=6.0; extra == "test"
            """
        )
        + "\n\n"
    )
    dist = tmp_path / "dist"
    out = build_sdist(str(dist))

    (sdist,) = dist.iterdir()
    sdist = sdist.resolve()  # Windows mingw64 and UCRT now requires this
    assert sdist.name == "cmake_example-0.0.1.tar.gz"
    assert sdist == dist / out

    with tarfile.open(sdist) as f:
        file_names = set(f.getnames())
        assert file_names == {
            f"cmake_example-0.0.1/{x}"
            for x in (
                "CMakeLists.txt",
                "pyproject.toml",
                "src/main.cpp",
                "PKG-INFO",
                "LICENSE",
            )
        }
        pkg_info = f.extractfile("cmake_example-0.0.1/PKG-INFO")
        assert pkg_info
        pkg_info_contents = pkg_info.read().decode()
        assert pkg_info_contents == expected_metadata


@mark_hashes_different
def test_pep517_sdist_hash(monkeypatch, package_simple_pyproject_ext, tmp_path: Path):
    # Unset SOURCE_DATE_EPOCH in order to guarantee the hash match
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    dist = tmp_path / "dist"
    out = build_sdist(str(dist))
    sdist = dist / out
    sdist_hash = compute_uncompressed_hash(sdist)
    assert sdist_hash == package_simple_pyproject_ext.sdist_hash
    mode = sdist.stat().st_mode
    assert mode == 33188
    with gzip.open(sdist, "rb") as f:
        f.read()
        assert f.mtime == 1667997441


@pytest.mark.usefixtures("package_simple_pyproject_ext")
def test_pep517_sdist_time_hash(tmp_path: Path):
    dist = tmp_path / "dist"

    out = build_sdist(str(dist))
    sdist = dist / out
    hash1 = hashlib.sha256(sdist.read_bytes()).hexdigest()

    time.sleep(2)
    Path("src/main.cpp").touch()

    shutil.rmtree(dist)

    out = build_sdist(str(dist))
    sdist = dist / out

    hash2 = hashlib.sha256(sdist.read_bytes()).hexdigest()

    assert hash1 == hash2


@pytest.mark.usefixtures("package_simple_pyproject_ext")
def test_pep517_sdist_time_hash_nonreproducable(tmp_path: Path):
    dist = tmp_path / "dist"

    out = build_sdist(str(dist), {"sdist.reproducible": "false"})
    sdist = dist / out
    hash1 = hashlib.sha256(sdist.read_bytes()).hexdigest()

    time.sleep(2)

    shutil.rmtree(dist)

    out = build_sdist(str(dist))
    sdist = dist / out

    hash2 = hashlib.sha256(sdist.read_bytes()).hexdigest()

    assert hash1 != hash2


@mark_hashes_different
@pytest.mark.parametrize("reverse_order", [False, True])
def test_pep517_sdist_time_hash_set_epoch(
    monkeypatch, reverse_order, package_simple_pyproject_ext, tmp_path: Path
):
    dist = tmp_path / "dist"
    monkeypatch.setenv(
        "SOURCE_DATE_EPOCH", package_simple_pyproject_ext.source_date_epoch
    )

    _each_unignored_file = _file_processor.each_unignored_file

    def each_unignored_file_ordered(*args, **kwargs):
        return sorted(_each_unignored_file(*args, **kwargs), reverse=reverse_order)

    monkeypatch.setattr(
        _file_processor, "each_unignored_file", each_unignored_file_ordered
    )

    out = build_sdist(str(dist), {"sdist.reproducible": "true"})
    sdist = dist / out
    sdist_hash = compute_uncompressed_hash(sdist)
    assert sdist_hash == package_simple_pyproject_ext.sdist_dated_hash


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.parametrize(
    "package", ["simple_pyproject_script_with_flags"], indirect=True
)
@pytest.mark.usefixtures("package")
@pytest.mark.parametrize(
    ("env_var", "setting"),
    [
        ("CMAKE_ARGS", '-DCMAKE_C_FLAGS="-DFOO=1 -DBAR="'),
        ("SKBUILD_CMAKE_ARGS", "-DCMAKE_C_FLAGS=-DFOO=1 -DBAR="),
    ],
)
def test_passing_cxx_flags(monkeypatch, env_var, setting, tmp_path: Path):
    # Note: This is sensitive to the types of quotes for SKBUILD_CMAKE_ARGS
    monkeypatch.setenv(env_var, setting)
    dist = tmp_path / "dist"
    build_wheel(str(dist), {"build.targets": ["cmake_example"]})  # Could leave empty
    (wheel,) = dist.glob("cmake_example-0.0.1-py3-none-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    with zipfile.ZipFile(wheel) as f:
        file_names = set(f.namelist())

    ext = ".exe" if sys.platform.startswith(("win", "cygwin")) else ""

    assert file_names == {
        "cmake_example-0.0.1.dist-info/RECORD",
        "cmake_example-0.0.1.dist-info/WHEEL",
        f"cmake_example-0.0.1.data/scripts/cmake_example{ext}",
        "cmake_example-0.0.1.dist-info/METADATA",
        "cmake_example-0.0.1.dist-info/licenses/LICENSE",
    }


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.usefixtures("package_simple_pyproject_ext", "pybind11")
def test_pep517_wheel(virtualenv, tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(
        str(dist), {"build.targets": ["cmake_example"]}
    )  # Could leave empty
    (wheel,) = dist.glob("cmake_example-0.0.1-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_paths = {Path(p) for p in zf.namelist()}
        file_names = {p.parts[0] for p in file_paths}

        with zf.open("cmake_example-0.0.1.dist-info/METADATA") as f:
            metadata = f.read().decode("utf-8")

        with zf.open("cmake_example-0.0.1.dist-info/entry_points.txt") as f:
            entry_points = f.read().decode("utf-8")

    assert Path("cmake_example-0.0.1.dist-info/licenses/LICENSE") in file_paths

    assert len(file_names) == 2
    assert "cmake_example-0.0.1.dist-info" in file_names
    file_names.remove("cmake_example-0.0.1.dist-info")
    (so_file,) = file_names

    assert so_file.startswith("cmake_example")
    print("SOFILE:", so_file)

    print(entry_points == ENTRYPOINTS)
    assert 'Requires-Dist: pytest>=6.0; extra == "test"' in metadata
    assert "Metadata-Version: 2.2" in metadata
    assert "Name: CMake.Example" in metadata
    assert "Version: 0.0.1" in metadata
    assert "Requires-Python: >=3.10" in metadata
    assert "Provides-Extra: test" in metadata

    virtualenv.install(wheel)

    version = virtualenv.execute(
        "import cmake_example; print(cmake_example.__version__)",
    )
    assert version.strip() == "0.0.1"

    add = virtualenv.execute(
        "import cmake_example; print(cmake_example.add(1, 2))",
    )
    assert add.strip() == "3"


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.parametrize("package", ["simple_pyproject_source_dir"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep517_wheel_source_dir(virtualenv, tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist), config_settings={"skbuild.wheel.build-tag": "1foo"})
    (wheel,) = dist.glob("cmake_example-0.0.1-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_paths = {Path(p) for p in zf.namelist()}
        file_names = {p.parts[0] for p in file_paths}

        with zf.open("cmake_example-0.0.1.dist-info/METADATA") as f:
            metadata = f.read().decode("utf-8")

        with zf.open("cmake_example-0.0.1.dist-info/WHEEL") as f:
            wheel_metadata = f.read().decode("utf-8")

        with zf.open("cmake_example-0.0.1.dist-info/entry_points.txt") as f:
            entry_points = f.read().decode("utf-8")

    assert Path("cmake_example-0.0.1.dist-info/licenses/LICENSE") in file_paths

    assert len(file_names) == 2
    assert "cmake_example-0.0.1.dist-info" in file_names
    file_names.remove("cmake_example-0.0.1.dist-info")
    (so_file,) = file_names

    assert so_file.startswith("cmake_example")
    print("SOFILE:", so_file)

    print(entry_points == ENTRYPOINTS)
    assert 'Requires-Dist: pytest>=6.0; extra == "test"' in metadata
    assert "Metadata-Version: 2.2" in metadata
    assert "Name: CMake.Example" in metadata
    assert "Version: 0.0.1" in metadata
    assert "Requires-Python: >=3.10" in metadata
    assert "Provides-Extra: test" in metadata

    assert "Build: 1foo" in wheel_metadata
    assert "Wheel-Version: 1.0" in wheel_metadata
    assert "Generator: scikit-build" in wheel_metadata
    assert "Root-Is-Purelib: false" in wheel_metadata

    virtualenv.install(wheel)

    version = virtualenv.execute(
        "import cmake_example; print(cmake_example.__version__)",
    )
    assert version.strip() == "0.0.1"

    add = virtualenv.execute(
        "import cmake_example; print(cmake_example.add(1, 2))",
    )
    assert add.strip() == "3"


@pytest.mark.skip(reason="Doesn't work yet")
@pytest.mark.compile
@pytest.mark.configure
def test_pep517_wheel_time_hash(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "12345")
    dist = tmp_path / "dist"
    out = build_wheel(str(dist))
    wheel = dist / out
    hash1 = hashlib.sha256(wheel.read_bytes()).hexdigest()

    time.sleep(2)
    Path("src/main.cpp").touch()

    shutil.rmtree(dist)

    out = build_wheel(str(dist))
    wheel = dist / out

    hash2 = hashlib.sha256(wheel.read_bytes()).hexdigest()

    assert hash1 == hash2


@pytest.mark.usefixtures("package_simple_pyproject_ext")
def test_prepare_metadata_for_build_wheel(tmp_path):
    mddir = tmp_path / "dist"
    mddir.mkdir()
    out = prepare_metadata_for_build_wheel(str(mddir), {})
    metadata = PathDistribution(mddir / out).metadata
    answer = {
        "Metadata-Version": "2.2",
        "Name": "CMake.Example",
        "Version": "0.0.1",
        "Requires-Python": ">=3.10",
        "Provides-Extra": "test",
        "Requires-Dist": 'pytest>=6.0; extra == "test"',
    }

    for k, b in answer.items():
        assert metadata[k] == b

    assert len(metadata) == len(answer)


@pytest.mark.usefixtures("package_simple_pyproject_ext")
def test_prepare_metadata_for_build_wheel_by_hand(tmp_path):
    mddir = tmp_path / "dist"
    mddir.mkdir()
    out = prepare_metadata_for_build_wheel(str(mddir), {})
    print("Metadata dir:", (mddir / out).resolve())
    metadata = PathDistribution(mddir / out).metadata
    answer = {
        "Metadata-Version": "2.2",
        "Name": "CMake.Example",
        "Version": "0.0.1",
        "Requires-Python": ">=3.10",
        "Provides-Extra": "test",
        "Requires-Dist": 'pytest>=6.0; extra == "test"',
    }

    for k, b in answer.items():
        assert metadata[k] == b

    assert len(metadata) == len(answer)


@pytest.mark.parametrize("package", ["pep639_pure"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep639_license_files_metadata(tmp_path):
    mddir = tmp_path / "dist"
    mddir.mkdir()
    out = prepare_metadata_for_build_wheel(str(mddir), {})
    metadata = PathDistribution(mddir / out).metadata
    answer = {
        "Metadata-Version": ["2.4"],
        "Name": ["pep639_pure"],
        "Version": ["0.1.0"],
        "License-Expression": ["MIT"],
        "License-File": ["LICENSE1.txt", "nested/more/LICENSE2.txt"],
    }

    for k, b in answer.items():
        assert metadata.get_all(k, None) == b

    assert len(metadata) == sum(len(v) for v in answer.values())


@pytest.mark.parametrize("package", ["pep639_pure"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep639_license_files_sdist(tmp_path: Path):
    expected_metadata = (
        inspect.cleandoc(
            """
                Metadata-Version: 2.4
                Name: pep639_pure
                Version: 0.1.0
                License-Expression: MIT
                License-File: LICENSE1.txt
                License-File: nested/more/LICENSE2.txt
            """
        )
        + "\n\n"
    )

    dist = tmp_path / "dist"
    out = build_sdist(str(dist))

    (sdist,) = dist.iterdir()
    sdist = sdist.resolve()  # Windows mingw64 and UCRT now requires this
    assert sdist.name == "pep639_pure-0.1.0.tar.gz"
    assert sdist == dist / out

    with tarfile.open(sdist) as f:
        file_names = set(f.getnames())
        assert file_names == {
            f"pep639_pure-0.1.0/{x}"
            for x in (
                "pyproject.toml",
                "PKG-INFO",
                "LICENSE1.txt",
                "nested/more/LICENSE2.txt",
            )
        }
        pkg_info = f.extractfile("pep639_pure-0.1.0/PKG-INFO")
        assert pkg_info
        pkg_info_contents = pkg_info.read().decode()
        assert pkg_info_contents == expected_metadata


@pytest.mark.parametrize("package", ["pep639_pure"], indirect=True)
@pytest.mark.usefixtures("package")
def test_pep639_license_files_wheel(tmp_path: Path):
    dist = tmp_path / "dist"
    out = build_wheel(str(dist), {})
    (wheel,) = dist.glob("pep639_pure-0.1.0-*.whl")
    wheel = wheel.resolve()  # Windows mingw64 and UCRT now requires this
    assert wheel == dist / out

    with zipfile.ZipFile(wheel) as zf:
        file_paths = {Path(p) for p in zf.namelist()}
        with zf.open("pep639_pure-0.1.0.dist-info/METADATA") as f:
            metadata = f.read().decode("utf-8")

    assert Path("pep639_pure-0.1.0.dist-info/licenses/LICENSE1.txt") in file_paths
    assert (
        Path("pep639_pure-0.1.0.dist-info/licenses/nested/more/LICENSE2.txt")
        in file_paths
    )

    assert "LICENSE1.txt" in metadata
    assert "nested/more/LICENSE2.txt" in metadata


def test_pep639_license_files_optout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    An explicit ``license-files = []`` opts out of shipping license files, even
    if a default-glob-matching file (LICENSE) is present in the source tree.
    """
    src = tmp_path / "src"
    src.mkdir()
    src.joinpath("pyproject.toml").write_text(
        inspect.cleandoc(
            """
            [build-system]
            requires = ["scikit-build-core"]
            build-backend = "scikit_build_core.build"

            [project]
            name = "license_optout"
            version = "0.1.0"
            license = "MIT"
            license-files = []

            [tool.scikit-build]
            wheel.cmake = false
            """
        )
    )
    # A file that would otherwise be picked up by the default license globs.
    src.joinpath("LICENSE").write_text("Not actually shipped\n")
    monkeypatch.chdir(src)

    dist = tmp_path / "dist"
    build_wheel(str(dist), {})
    (wheel,) = dist.glob("license_optout-0.1.0-*.whl")

    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        with zf.open("license_optout-0.1.0.dist-info/METADATA") as f:
            metadata = f.read().decode("utf-8")

    assert not any("dist-info/licenses/" in n for n in names)
    assert "License-File:" not in metadata
