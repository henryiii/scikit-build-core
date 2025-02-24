# Comparison with empty strings okay for symmetry
# ruff: noqa: PLC1901

from __future__ import annotations

import re
import textwrap
from pathlib import Path

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

import scikit_build_core._logging
import scikit_build_core.settings.skbuild_read_settings
from scikit_build_core.settings.skbuild_model import GenerateSettings
from scikit_build_core.settings.skbuild_read_settings import SettingsReader


def test_skbuild_settings_default(tmp_path: Path):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text("", encoding="utf-8")

    config_settings: dict[str, list[str] | str] = {}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    settings = settings_reader.settings
    assert list(settings_reader.unrecognized_options()) == []

    assert settings.ninja.minimum_version is None
    assert settings.ninja.version == SpecifierSet(">=1.5")
    assert settings.ninja.make_fallback
    assert settings.cmake.minimum_version is None
    assert settings.cmake.version == SpecifierSet(">=3.15")
    assert settings.cmake.args == []
    assert settings.cmake.define == {}
    assert not settings.build.verbose
    assert settings.cmake.build_type == "Release"
    assert settings.cmake.source_dir == Path()
    assert settings.build.targets == []
    assert settings.logging.level == "WARNING"
    assert settings.sdist.include == []
    assert settings.sdist.exclude == []
    assert settings.sdist.reproducible
    assert not settings.sdist.cmake
    assert settings.wheel.packages is None
    assert settings.wheel.py_api == ""
    assert not settings.wheel.expand_macos_universal_tags
    assert settings.wheel.license_files is None
    assert settings.wheel.exclude == []
    assert settings.wheel.build_tag == ""
    assert settings.backport.find_python == Version("3.26.1")
    assert settings.strict_config
    assert not settings.experimental
    assert settings.minimum_version is None
    assert settings.build_dir == ""
    assert settings.metadata == {}
    assert settings.editable.mode == "redirect"
    assert not settings.editable.rebuild
    assert settings.editable.verbose
    assert settings.build.tool_args == []
    assert settings.install.components == []
    assert settings.install.strip
    assert settings.generate == []
    assert not settings.fail
    assert settings.messages.after_failure == ""
    assert settings.messages.after_success == ""


def test_skbuild_settings_envvar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )

    monkeypatch.setenv("SKBUILD_NINJA_VERSION", ">=1.1")
    monkeypatch.setenv("SKBUILD_NINJA_MAKE_FALLBACK", "0")
    monkeypatch.setenv("SKBUILD_CMAKE_VERSION", ">=3.16")
    monkeypatch.setenv("SKBUILD_CMAKE_ARGS", "-DFOO=BAR;-DBAR=FOO")
    monkeypatch.setenv("SKBUILD_CMAKE_DEFINE", "a=1;b=2")
    monkeypatch.setenv("SKBUILD_CMAKE_BUILD_TYPE", "Debug")
    monkeypatch.setenv("SKBUILD_CMAKE_SOURCE_DIR", "a/b/c")
    monkeypatch.setenv("SKBUILD_LOGGING_LEVEL", "DEBUG")
    monkeypatch.setenv("SKBUILD_SDIST_INCLUDE", "a;b; c")
    monkeypatch.setenv("SKBUILD_SDIST_EXCLUDE", "d;e;f")
    monkeypatch.setenv("SKBUILD_SDIST_REPRODUCIBLE", "OFF")
    monkeypatch.setenv("SKBUILD_SDIST_CMAKE", "ON")
    monkeypatch.setenv("SKBUILD_WHEEL_PACKAGES", "j; k; l")
    monkeypatch.setenv("SKBUILD_WHEEL_PY_API", "cp39")
    monkeypatch.setenv("SKBUILD_WHEEL_EXPAND_MACOS_UNIVERSAL_TAGS", "True")
    monkeypatch.setenv("SKBUILD_WHEEL_LICENSE_FILES", "a;b;c")
    monkeypatch.setenv("SKBUILD_WHEEL_EXCLUDE", "b;y;e")
    monkeypatch.setenv("SKBUILD_WHEEL_BUILD_TAG", "1")
    monkeypatch.setenv("SKBUILD_BACKPORT_FIND_PYTHON", "0")
    monkeypatch.setenv("SKBUILD_STRICT_CONFIG", "0")
    monkeypatch.setenv("SKBUILD_EXPERIMENTAL", "1")
    monkeypatch.setenv("SKBUILD_MINIMUM_VERSION", "0.10")
    monkeypatch.setenv("SKBUILD_BUILD_DIR", "a/b/c")
    monkeypatch.setenv("SKBUILD_EDITABLE_REBUILD", "True")
    monkeypatch.setenv("SKBUILD_EDITABLE_VERBOSE", "False")
    monkeypatch.setenv("SKBUILD_BUILD_VERBOSE", "TRUE")
    monkeypatch.setenv("SKBUILD_BUILD_TARGETS", "a;b;c")
    monkeypatch.setenv("SKBUILD_BUILD_TOOL_ARGS", "a;b")
    monkeypatch.setenv("SKBUILD_INSTALL_COMPONENTS", "a;b;c")
    monkeypatch.setenv("SKBUILD_INSTALL_STRIP", "False")
    monkeypatch.setenv("SKBUILD_FAIL", "1")
    monkeypatch.setenv(
        "SKBUILD_MESSAGES_AFTER_FAILURE", "This is a test failure message"
    )
    monkeypatch.setenv(
        "SKBUILD_MESSAGES_AFTER_SUCCESS", "This is a test success message"
    )

    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text("", encoding="utf-8")

    config_settings: dict[str, list[str] | str] = {}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    settings = settings_reader.settings
    assert list(settings_reader.unrecognized_options()) == []

    assert settings.ninja.version == SpecifierSet(">=1.1")
    assert settings.cmake.version == SpecifierSet(">=3.16")
    assert settings.cmake.args == ["-DFOO=BAR", "-DBAR=FOO"]
    assert settings.cmake.define == {"a": "1", "b": "2"}
    assert settings.cmake.build_type == "Debug"
    assert settings.cmake.source_dir == Path("a/b/c")
    assert not settings.ninja.make_fallback
    assert settings.logging.level == "DEBUG"
    assert settings.sdist.include == ["a", "b", "c"]
    assert settings.sdist.exclude == ["d", "e", "f"]
    assert not settings.sdist.reproducible
    assert settings.sdist.cmake
    assert settings.wheel.packages == ["j", "k", "l"]
    assert settings.wheel.py_api == "cp39"
    assert settings.wheel.expand_macos_universal_tags
    assert settings.wheel.license_files == ["a", "b", "c"]
    assert settings.wheel.exclude == ["b", "y", "e"]
    assert settings.wheel.build_tag == "1"
    assert settings.backport.find_python == Version("0")
    assert not settings.strict_config
    assert settings.experimental
    assert settings.minimum_version == Version("0.10")
    assert settings.build_dir == "a/b/c"
    assert settings.metadata == {}
    assert settings.editable.mode == "redirect"
    assert settings.editable.rebuild
    assert not settings.editable.verbose
    assert settings.build.verbose
    assert settings.build.targets == ["a", "b", "c"]
    assert settings.build.tool_args == ["a", "b"]
    assert settings.install.components == ["a", "b", "c"]
    assert not settings.install.strip
    assert settings.fail
    assert settings.messages.after_failure == "This is a test failure message"
    assert settings.messages.after_success == "This is a test success message"


@pytest.mark.parametrize("prefix", [True, False], ids=["skbuild", "noprefix"])
def test_skbuild_settings_config_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: bool
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )

    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text("", encoding="utf-8")

    config_settings: dict[str, str | list[str]] = {
        "ninja.version": ">=1.2",
        "ninja.make-fallback": "False",
        "cmake.version": ">=3.17",
        "cmake.args": ["-DFOO=BAR", "-DBAR=FOO"],
        "cmake.define.a": "1",
        "cmake.define.b": "2",
        "cmake.build-type": "Debug",
        "cmake.source-dir": "a/b/c",
        "logging.level": "INFO",
        "sdist.include": ["a", "b", "c"],
        "sdist.exclude": "d;e;f",
        "sdist.reproducible": "false",
        "sdist.cmake": "true",
        "wheel.packages": ["j", "k", "l"],
        "wheel.py-api": "cp39",
        "wheel.expand-macos-universal-tags": "True",
        "wheel.license-files": ["a", "b", "c"],
        "wheel.exclude": ["b", "y", "e"],
        "wheel.build-tag": "1foo",
        "backport.find-python": "0",
        "strict-config": "false",
        "experimental": "1",
        "minimum-version": "0.10",
        "build-dir": "a/b/c",
        "editable.mode": "redirect",
        "editable.rebuild": "True",
        "editable.verbose": "False",
        "build.verbose": "true",
        "build.targets": ["a", "b", "c"],
        "build.tool-args": ["a", "b"],
        "install.components": ["a", "b", "c"],
        "install.strip": "True",
        "fail": "1",
        "messages.after-failure": "This is a test failure message",
        "messages.after-success": "This is a test success message",
    }

    if prefix:
        config_settings = {f"skbuild.{k}": v for k, v in config_settings.items()}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    settings = settings_reader.settings
    assert list(settings_reader.unrecognized_options()) == []

    assert settings.ninja.version == SpecifierSet(">=1.2")
    assert not settings.ninja.make_fallback
    assert settings.cmake.version == SpecifierSet(">=3.17")
    assert settings.cmake.args == ["-DFOO=BAR", "-DBAR=FOO"]
    assert settings.cmake.define == {"a": "1", "b": "2"}
    assert settings.build.verbose
    assert settings.cmake.build_type == "Debug"
    assert settings.cmake.source_dir == Path("a/b/c")
    assert settings.logging.level == "INFO"
    assert settings.sdist.include == ["a", "b", "c"]
    assert settings.sdist.exclude == ["d", "e", "f"]
    assert not settings.sdist.reproducible
    assert settings.sdist.cmake
    assert settings.wheel.packages == ["j", "k", "l"]
    assert settings.wheel.py_api == "cp39"
    assert settings.wheel.expand_macos_universal_tags
    assert settings.wheel.license_files == ["a", "b", "c"]
    assert settings.wheel.exclude == ["b", "y", "e"]
    assert settings.wheel.build_tag == "1foo"
    assert settings.backport.find_python == Version("0")
    assert not settings.strict_config
    assert settings.experimental
    assert settings.minimum_version == Version("0.10")
    assert settings.build_dir == "a/b/c"
    assert settings.metadata == {}
    assert settings.editable.mode == "redirect"
    assert settings.editable.rebuild
    assert not settings.editable.verbose
    assert settings.build.targets == ["a", "b", "c"]
    assert settings.build.tool_args == ["a", "b"]
    assert settings.install.components == ["a", "b", "c"]
    assert settings.install.strip
    assert settings.fail
    assert settings.messages.after_failure == "This is a test failure message"
    assert settings.messages.after_success == "This is a test success message"


def test_skbuild_settings_pyproject_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            ninja.version = ">=1.3"
            ninja.make-fallback = false
            cmake.version = ">=3.18"
            cmake.args = ["-DFOO=BAR", "-DBAR=FOO"]
            cmake.define = {a = "1", b = "2"}
            cmake.build-type = "Debug"
            cmake.source-dir = "a/b/c"
            logging.level = "ERROR"
            sdist.include = ["a", "b", "c"]
            sdist.exclude = ["d", "e", "f"]
            sdist.reproducible = false
            sdist.cmake = true
            wheel.packages = ["j", "k", "l"]
            wheel.py-api = "cp39"
            wheel.expand-macos-universal-tags = true
            wheel.license-files = ["a", "b", "c"]
            wheel.exclude = ["b", "y", "e"]
            wheel.build-tag = "1_bar"
            backport.find-python = "3.18"
            strict-config = false
            experimental = true
            minimum-version = "0.10"
            build-dir = "a/b/c"
            metadata.version.provider = "a"
            editable.mode = "redirect"
            editable.rebuild = true
            editable.verbose = false
            build.verbose = true
            build.targets = ["a", "b", "c"]
            build.tool-args = ["a", "b"]
            install.components = ["a", "b", "c"]
            install.strip = true
            fail = true
            messages.after-failure = "This is a test failure message"
            messages.after-success = "This is a test success message"
            [[tool.scikit-build.generate]]
            path = "a/b/c"
            template = "hello"
            [[tool.scikit-build.generate]]
            path = "d/e/f"
            template-path = "g/h/i"
            location = "build"
            """
        ),
        encoding="utf-8",
    )

    config_settings: dict[str, list[str] | str] = {}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    settings = settings_reader.settings
    assert list(settings_reader.unrecognized_options()) == []

    assert settings.ninja.version == SpecifierSet(">=1.3")
    assert not settings.ninja.make_fallback
    assert settings.cmake.version == SpecifierSet(">=3.18")
    assert settings.cmake.args == ["-DFOO=BAR", "-DBAR=FOO"]
    assert settings.cmake.define == {"a": "1", "b": "2"}
    assert settings.cmake.build_type == "Debug"
    assert settings.cmake.source_dir == Path("a/b/c")
    assert settings.logging.level == "ERROR"
    assert settings.sdist.include == ["a", "b", "c"]
    assert settings.sdist.exclude == ["d", "e", "f"]
    assert not settings.sdist.reproducible
    assert settings.sdist.cmake
    assert settings.wheel.packages == ["j", "k", "l"]
    assert settings.wheel.py_api == "cp39"
    assert settings.wheel.expand_macos_universal_tags
    assert settings.wheel.license_files == ["a", "b", "c"]
    assert settings.wheel.exclude == ["b", "y", "e"]
    assert settings.wheel.build_tag == "1_bar"
    assert settings.backport.find_python == Version("3.18")
    assert not settings.strict_config
    assert settings.experimental
    assert settings.minimum_version == Version("0.10")
    assert settings.build_dir == "a/b/c"
    assert settings.metadata == {"version": {"provider": "a"}}
    assert settings.editable.mode == "redirect"
    assert settings.editable.rebuild
    assert not settings.editable.verbose
    assert settings.build.verbose
    assert settings.build.targets == ["a", "b", "c"]
    assert settings.build.tool_args == ["a", "b"]
    assert settings.install.components == ["a", "b", "c"]
    assert settings.install.strip
    assert settings.generate == [
        GenerateSettings(path=Path("a/b/c"), template="hello", location="install"),
        GenerateSettings(
            path=Path("d/e/f"), template_path=Path("g/h/i"), location="build"
        ),
    ]
    assert settings.fail
    assert settings.messages.after_failure == "This is a test failure message"
    assert settings.messages.after_success == "This is a test success message"


def test_skbuild_settings_pyproject_toml_broken(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.9.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            minimum-version = "0.9"
            cmake.verison = ">=3.18"
            ninja.version = ">=1.3"
            ninja.make-fallback = false
            logger.level = "ERROR"
            """
        ),
        encoding="utf-8",
    )

    config_settings: dict[str, list[str] | str] = {}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    assert list(settings_reader.unrecognized_options()) == [
        "tool.scikit-build.cmake.verison",
        "tool.scikit-build.logger",
    ]

    with pytest.raises(SystemExit):
        settings_reader.validate_may_exit()

    ex = capsys.readouterr().out
    ex = re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", ex)
    assert (
        ex.split()
        == """\
      ERROR: Unrecognized options in pyproject.toml:
        tool.scikit-build.cmake.verison -> Did you mean: tool.scikit-build.cmake.version, tool.scikit-build.cmake.verbose, tool.scikit-build.cmake.define?
        tool.scikit-build.logger -> Did you mean: tool.scikit-build.logging, tool.scikit-build.generate, tool.scikit-build.fail?
      """.split()
    )


def test_skbuild_settings_pyproject_conf_broken(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.9.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        "tool.scikit-build.minimum-version = '0.9'", encoding="utf-8"
    )

    config_settings: dict[str, str | list[str]] = {
        "cmake.verison": ">=3.17",
        "ninja.version": ">=1.2",
        "ninja.make-fallback": "False",
        "logger.level": "INFO",
    }

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    assert list(settings_reader.unrecognized_options()) == [
        "cmake.verison",
        "logger",
    ]

    with pytest.raises(SystemExit):
        settings_reader.validate_may_exit()

    ex = capsys.readouterr().out
    # Filter terminal color codes
    ex = re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", ex)
    assert (
        ex.split()
        == """\
      ERROR: Unrecognized options in config-settings:
        cmake.verison -> Did you mean: cmake.version, cmake.verbose, cmake.define?
        logger -> Did you mean: logging?
      """.split()
    )


def test_skbuild_settings_min_version_defaults_strip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.5.0"
    )

    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text("", encoding="utf-8")

    settings_reader = SettingsReader.from_file(
        pyproject_toml, {"minimum-version": "0.4"}
    )
    settings = settings_reader.settings
    assert not settings.install.strip

    settings_reader = SettingsReader.from_file(
        pyproject_toml, {"minimum-version": "0.5"}
    )
    settings = settings_reader.settings
    assert settings.install.strip


def test_skbuild_settings_min_version_versions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )

    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        "tool.scikit-build.cmake.minimum-version = '3.21'", encoding="utf-8"
    )
    cmakelists = tmp_path / "CMakeLists.txt"
    cmakelists.write_text("cmake_minimum_required(VERSION 3.20)", encoding="utf-8")

    settings_reader = SettingsReader.from_file(pyproject_toml, {})
    settings = settings_reader.settings
    assert settings.cmake.version == SpecifierSet(">=3.21")

    settings_reader = SettingsReader.from_file(
        pyproject_toml, {"minimum-version": "0.7"}
    )
    settings = settings_reader.settings
    assert settings.cmake.version == SpecifierSet(">=3.21")

    with pytest.raises(SystemExit):
        SettingsReader.from_file(pyproject_toml, {"minimum-version": "0.8"})


def test_skbuild_settings_version_too_old(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.8.0"
    )

    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        "tool.scikit-build.cmake.version = '>=3.21'", encoding="utf-8"
    )

    SettingsReader.from_file(pyproject_toml)

    with pytest.raises(SystemExit):
        SettingsReader.from_file(pyproject_toml, {"minimum-version": "0.7"})


def test_skbuild_settings_pyproject_toml_envvar_defines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build.cmake.define]
            a = "1"
            b = {env = "SIMPLE"}
            c = {env = "DEFAULT", default="empty"}
            d = false
            e = {env = "BOOL", default = false}
            f = {env = "NOTSET"}
            """
        ),
        encoding="utf-8",
    )

    config_settings: dict[str, list[str] | str] = {}

    monkeypatch.setenv("SIMPLE", "2")
    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    assert settings_reader.settings.cmake.define == {
        "a": "1",
        "b": "2",
        "c": "empty",
        "d": "FALSE",
        "e": "FALSE",
    }

    monkeypatch.setenv("DEFAULT", "3")
    monkeypatch.setenv("BOOL", "ON")
    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    assert settings_reader.settings.cmake.define == {
        "a": "1",
        "b": "2",
        "c": "3",
        "d": "FALSE",
        "e": "TRUE",
    }


def test_backcompat_cmake_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            minimum-version = "0.9"
            cmake.verbose = true
            cmake.targets = ["a", "b"]
            """
        ),
        encoding="utf-8",
    )

    settings_reader = SettingsReader.from_file(pyproject_toml, {})
    assert settings_reader.settings.build.verbose
    assert settings_reader.settings.build.targets == ["a", "b"]


def test_backcompat_cmake_build_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.9.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            minimum-version = "0.9"
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKBUILD_CMAKE_VERBOSE", "ON")
    monkeypatch.setenv("SKBUILD_CMAKE_TARGETS", "a;b")

    settings_reader = SettingsReader.from_file(pyproject_toml, {})
    assert settings_reader.settings.build.verbose
    assert settings_reader.settings.build.targets == ["a", "b"]


def test_backcompat_cmake_build_both_specified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            cmake.verbose = true
            """
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit):
        SettingsReader.from_file(pyproject_toml, {"build.verbose": "1"})


def test_auto_minimum_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["scikit-build-core>=0.8"]

            [tool.scikit-build]
            minimum-version = "build-system.requires"
            """
        ),
        encoding="utf-8",
    )

    reader = SettingsReader.from_file(pyproject_toml, {})
    assert reader.settings.minimum_version == Version("0.8")


def test_auto_cmake_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["scikit-build-core>=0.8"]

            [tool.scikit-build]
            cmake.version = "CMakeLists.txt"
            """
        ),
        encoding="utf-8",
    )
    cmakelists_txt = tmp_path / "CMakeLists.txt"
    cmakelists_txt.write_text(
        textwrap.dedent(
            """\
            cmake_minimum_required(VERSION 3.21)
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    reader = SettingsReader.from_file(pyproject_toml, {})
    assert reader.settings.cmake.version == SpecifierSet(">=3.21")


@pytest.mark.parametrize("version", ["0.9", "0.10"])
def test_default_auto_cmake_version(
    version: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            f"""\
            [build-system]
            requires = ["scikit-build-core>={version}"]

            [tool.scikit-build]
            minimum-version = "build-system.requires"
            """
        ),
        encoding="utf-8",
    )
    cmakelists_txt = tmp_path / "CMakeLists.txt"
    cmakelists_txt.write_text(
        textwrap.dedent(
            """\
            cmake_minimum_required(VERSION 3.21)
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    reader = SettingsReader.from_file(pyproject_toml, {})
    assert reader.settings.cmake.version == SpecifierSet(
        ">=3.21" if version == "0.10" else ">=3.15"
    )


def test_skbuild_settings_auto_cmake_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        scikit_build_core.settings.skbuild_read_settings, "__version__", "0.10.0"
    )
    scikit_build_core._logging.rich_warning.cache_clear()
    pyproject_toml = tmp_path / "pyproject.toml"
    pyproject_toml.write_text(
        textwrap.dedent(
            """\
            [tool.scikit-build]
            minimum-version = "0.10"
            """
        ),
        encoding="utf-8",
    )

    cmakelists_txt = tmp_path / "CMakeLists.txt"
    cmakelists_txt.write_text(
        textwrap.dedent(
            """\
            cmake_minimum_required(VERSION 3.14)
            """
        ),
        encoding="utf-8",
    )

    config_settings: dict[str, list[str] | str] = {}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)

    assert settings_reader.settings.cmake.version == SpecifierSet(">=3.15")

    ex = capsys.readouterr().out
    ex = re.sub(r"\x1b(\[.*?[@-~]|\].*?(\x07|\x1b\\))", "", ex)
    print(ex)
    assert (
        ex.split()
        == """\
            WARNING: CMakeLists.txt not found when looking for minimum CMake version.
            Report this or (and) set manually to avoid this warning. Using 3.15 as a fall-back.
      """.split()
    )


def test_skbuild_settings_cmake_define_list():
    pyproject_toml = (
        Path(__file__).parent / "packages" / "cmake_defines" / "pyproject.toml"
    )

    config_settings: dict[str, list[str] | str] = {}

    settings_reader = SettingsReader.from_file(pyproject_toml, config_settings)
    settings = settings_reader.settings

    assert settings.cmake.define == {
        "NESTED_LIST": r"Apple;Lemon\;Lime;Banana",
        "ONE_LEVEL_LIST": "Foo;Bar;ExceptionallyLargeListEntryThatWouldOverflowTheLine;Baz",
        "OVERWRITTEN_VAR": "overwritten",
    }
