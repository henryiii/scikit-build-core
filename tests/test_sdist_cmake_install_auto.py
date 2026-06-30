"""Automatic from-sdist repackaging of an ``sdist.install-dir`` vendored tree.

Unlike ``test_sdist_cmake_install.py`` (which spells out the ``if.from-sdist``
+ ``wheel.force-include`` recipe), this package only sets ``sdist.install-dir``;
scikit-build-core disables CMake and restages the vendored trees on its own.
"""

from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path

import pytest

from scikit_build_core.build import build_sdist, build_wheel
from scikit_build_core.build.wheel import _restage_vendored_tree

DIR = Path(__file__).parent.resolve()
PKG = DIR / "packages" / "sdist_cmake_install_auto"

# The sdist build runs a real configure+build+install.
pytestmark = pytest.mark.configure


@pytest.fixture
def src(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "src"
    shutil.copytree(PKG, root)
    monkeypatch.chdir(root)
    return root


def _build_sdist(dist: Path) -> Path:
    name = build_sdist(str(dist), {})
    return dist / name


def _extract(sdist: Path, dest: Path) -> None:
    with tarfile.open(sdist) as tar:
        try:
            tar.extractall(dest, filter="data")
        except TypeError:
            tar.extractall(dest)  # noqa: S202


def test_auto_repackage_needs_no_recipe(
    src: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """With only sdist.install-dir set, the from-sdist wheel restages, no CMake."""
    dist = src / "dist"
    sdist = _build_sdist(dist)

    unpacked = tmp_path / "unpacked"
    _extract(sdist, unpacked)
    sdist_root = unpacked / "sdist_cmake_install_auto-0.2.0"
    assert (sdist_root / "PKG-INFO").is_file()  # triggers automatic repackaging
    monkeypatch.chdir(sdist_root)

    capfd.readouterr()  # drop the sdist-build output
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    wheel_name = build_wheel(str(wheel_dir), {})

    out, _ = capfd.readouterr()
    # CMake is auto-disabled: no configure banner, pure wheel.
    assert "Configuring CMake" not in out
    assert wheel_name.endswith("-py3-none-any.whl")

    with zipfile.ZipFile(wheel_dir / wheel_name) as zf:
        names = set(zf.namelist())
        config_text = zf.read(
            "sdist_cmake_install_auto/cmake/example-config.cmake"
        ).decode()

    assert "sdist_cmake_install_auto/include/example.h" in names
    assert "sdist_cmake_install_auto/cmake/example-config.cmake" in names
    # The headers tree (outside the install prefix) was restaged too.
    assert any(n.endswith(".data/headers/example.h") for n in names)
    # The version-stamped config proves CMake ran during the *sdist* build, not now.
    assert 'set(EXAMPLE_VERSION "0.2.0")' in config_text
    # The install pass ran as a "wheel" build.
    assert 'set(EXAMPLE_STATE "wheel")' in config_text


def test_auto_repackage_matches_direct_cmake_build(
    src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The auto-repackaged from-sdist wheel matches a direct CMake build."""
    # Direct build from the source tree (no PKG-INFO -> CMake runs).
    direct_dir = src / "direct"
    direct_dir.mkdir()
    direct_name = build_wheel(str(direct_dir), {})
    with zipfile.ZipFile(direct_dir / direct_name) as zf:
        direct_names = {n for n in zf.namelist() if not n.endswith("RECORD")}

    # Build from the unpacked sdist (PKG-INFO -> CMake disabled, restage).
    dist = src / "dist"
    sdist = _build_sdist(dist)
    unpacked = tmp_path / "unpacked"
    _extract(sdist, unpacked)
    monkeypatch.chdir(unpacked / "sdist_cmake_install_auto-0.2.0")
    fromsdist_dir = tmp_path / "fromsdist"
    fromsdist_dir.mkdir()
    fromsdist_name = build_wheel(str(fromsdist_dir), {})
    with zipfile.ZipFile(fromsdist_dir / fromsdist_name) as zf:
        fromsdist_names = {n for n in zf.namelist() if not n.endswith("RECORD")}

    assert direct_name == fromsdist_name
    assert direct_names == fromsdist_names


def test_restage_refuses_platlib_into_purelib(tmp_path: Path) -> None:
    """A compiled (platlib) vendored tree can't be restaged into a purelib wheel."""
    vendored = tmp_path / "vendored"
    (vendored / "platlib" / "pkg").mkdir(parents=True)
    (vendored / "platlib" / "pkg" / "_ext.so").write_bytes(b"\x00")

    wheel_root = tmp_path / "wheel"
    wheel_dirs = {
        "purelib": wheel_root / "purelib",
        "headers": wheel_root / "headers",
    }
    for d in wheel_dirs.values():
        d.mkdir(parents=True)

    with pytest.raises(AssertionError, match="platlib"):
        _restage_vendored_tree(vendored, wheel_dirs=wheel_dirs, targetlib="purelib")


def test_explicit_wheel_cmake_opts_out(
    src: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Setting wheel.cmake explicitly from-sdist disables automatic repackaging."""
    dist = src / "dist"
    sdist = _build_sdist(dist)
    unpacked = tmp_path / "unpacked"
    _extract(sdist, unpacked)
    monkeypatch.chdir(unpacked / "sdist_cmake_install_auto-0.2.0")

    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    # An explicit wheel.cmake = true is honored: CMake runs again instead.
    wheel_name = build_wheel(str(wheel_dir), {"wheel.cmake": "true"})

    with zipfile.ZipFile(wheel_dir / wheel_name) as zf:
        config_text = zf.read(
            "sdist_cmake_install_auto/cmake/example-config.cmake"
        ).decode()
    # CMake re-ran, so the config is freshly generated (still version-stamped).
    assert 'set(EXAMPLE_VERSION "0.2.0")' in config_text
