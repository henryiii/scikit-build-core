from __future__ import annotations

import os
import shutil
from pathlib import Path

from scikit_build_core.get_requires import get_requires_for_build_wheel


def which_mock(name: str) -> str | None:
    if name == "ninja":
        return None
    if name == "cmake":
        return "cmake/path"
    return None


def test_get_requires_for_build_wheel(fp, monkeypatch):
    cmake = Path("cmake/path").resolve()
    monkeypatch.setattr(shutil, "which", which_mock)
    fp.register([os.fspath(cmake), "--version"], stdout="3.14.0")
    assert get_requires_for_build_wheel() == ["cmake>=3.15", "ninja"]


def test_get_requires_for_build_wheel_uneeded(fp, monkeypatch):
    cmake = Path("cmake/path").resolve()
    monkeypatch.setattr(shutil, "which", which_mock)
    fp.register([os.fspath(cmake), "--version"], stdout="3.18.0")
    assert get_requires_for_build_wheel() == ["ninja"]


def test_get_requires_for_build_wheel_settings(fp, monkeypatch):
    cmake = Path("cmake/path").resolve()
    monkeypatch.setattr(shutil, "which", which_mock)
    fp.register([os.fspath(cmake), "--version"], stdout="3.18.0")
    assert get_requires_for_build_wheel({"cmake.min-version": "3.20"}) == [
        "cmake>=3.20",
        "ninja",
    ]


def test_get_requires_for_build_wheel_pyproject(fp, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text(
        """
        [tool.cmake]
        min-version = "3.21"
        """
    )
    cmake = Path("cmake/path").resolve()
    monkeypatch.setattr(shutil, "which", which_mock)
    fp.register([os.fspath(cmake), "--version"], stdout="3.18.0")
    assert get_requires_for_build_wheel() == ["cmake>=3.21", "ninja"]
