from __future__ import annotations

import importlib.util
import sysconfig
from pathlib import Path

import pytest

from scikit_build_core._variants import VARIANTLIB_BUILD_REQUIREMENT
from scikit_build_core.build import (
    get_requires_for_build_editable,
    get_requires_for_build_sdist,
    get_requires_for_build_wheel,
)
from scikit_build_core.builder.get_requires import GetRequires

TYPE_CHECKING = False
if TYPE_CHECKING:
    from pytest_subprocess import FakeProcess

ninja = [] if sysconfig.get_platform().startswith("win") else ["ninja>=1.5"]

# Captured before the protect_get_requires fixture replaces it
REAL_FIND_SPEC = importlib.util.find_spec


@pytest.fixture(autouse=True)
def protect_get_requires_autouse(protect_get_requires: None):
    """
    Autouse this fixture in this test.
    """


def test_get_requires_parts(fp: FakeProcess):
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(GetRequires().cmake()) == {"cmake>=3.15"}
    assert set(GetRequires().ninja()) == {*ninja}


def test_get_requires_parts_unneeded(fp: FakeProcess):
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.18.0"}}',
    )
    assert set(GetRequires().cmake()) == set()
    assert set(GetRequires().ninja()) == {*ninja}


def test_get_requires_parts_settings(fp: FakeProcess):
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.18.0"}}',
    )
    config = {"cmake.version": ">=3.20"}
    assert set(GetRequires.from_config_settings(config).cmake()) == {"cmake>=3.20"}
    assert set(GetRequires.from_config_settings(config).ninja()) == {*ninja}


def test_get_requires_parts_pyproject(
    fp: FakeProcess, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text(
        """
        [tool.scikit-build.cmake]
        version = ">=3.21"
        """
    )
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.18.0"}}',
    )

    assert set(GetRequires().cmake()) == {"cmake>=3.21"}
    assert set(GetRequires().ninja()) == {*ninja}


def test_get_requires_parts_pyproject_old(
    fp: FakeProcess, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text(
        """

        [tool.scikit-build]
        minimum-version = "0.0"
        cmake.minimum-version = "3.21"
        """
    )
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.18.0"}}',
    )

    assert set(GetRequires().cmake()) == {"cmake>=3.21"}
    assert set(GetRequires().ninja()) == {*ninja}


def test_get_requires_for_build_sdist(fp: FakeProcess):
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(get_requires_for_build_sdist({})) == set()


def test_get_requires_for_build_sdist_cmake(fp: FakeProcess):
    expected = {"cmake>=3.15", *ninja}
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(get_requires_for_build_sdist({"sdist.cmake": "True"})) == expected


@pytest.mark.parametrize(
    ("hook", "config", "expected"),
    [
        (
            get_requires_for_build_sdist,
            {"experimental": "true", "variant": "cpu :: abi :: cp313"},
            False,
        ),
        (
            get_requires_for_build_wheel,
            {"experimental": "true", "variant": "cpu :: abi :: cp313"},
            True,
        ),
        (
            get_requires_for_build_editable,
            {"experimental": "true", "variant-name": "cpu :: abi :: cp313"},
            True,
        ),
    ],
)
def test_get_requires_for_build_with_variant(
    fp: FakeProcess,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    hook,
    config: dict[str, str],
    expected: bool,
):
    tmp_path.joinpath("pyproject.toml").write_text(
        '[variant.providers.cpu]\nrequires = ["cpu-variant-provider"]\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert (VARIANTLIB_BUILD_REQUIREMENT in hook(config)) is expected


def test_get_requires_for_build_wheel(fp: FakeProcess):
    expected = {"cmake>=3.15", *ninja}
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(get_requires_for_build_wheel({})) == expected


def test_get_requires_for_build_wheel_pure(fp: FakeProcess):
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(get_requires_for_build_wheel({"wheel.cmake": "False"})) == set()


def test_get_requires_for_build_editable(fp: FakeProcess):
    expected = {"cmake>=3.15", *ninja}
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(get_requires_for_build_editable({})) == expected


def test_get_requires_for_build_editable_pure(fp: FakeProcess):
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    assert set(get_requires_for_build_editable({"wheel.cmake": "False"})) == set()


def test_get_requires_state_override(
    fp: FakeProcess, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """
    Overrides gated on ``if.state`` must be resolved against the actual hook's
    state, so a ``state = "wheel"`` override only affects the wheel hook.
    """
    monkeypatch.chdir(tmp_path)
    tmp_path.joinpath("pyproject.toml").write_text(
        """
        [tool.scikit-build]
        wheel.cmake = false
        sdist.cmake = false

        [[tool.scikit-build.overrides]]
        if.state = "wheel"
        build.requires = ["wheel-only-dep"]

        [[tool.scikit-build.overrides]]
        if.state = "editable"
        build.requires = ["editable-only-dep"]
        """
    )
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )

    assert "wheel-only-dep" in get_requires_for_build_wheel({})
    assert "wheel-only-dep" not in get_requires_for_build_sdist({})
    assert "wheel-only-dep" not in get_requires_for_build_editable({})

    assert "editable-only-dep" in get_requires_for_build_editable({})
    assert "editable-only-dep" not in get_requires_for_build_sdist({})
    assert "editable-only-dep" not in get_requires_for_build_wheel({})


@pytest.mark.parametrize(
    ("args", "cmake_args", "expected"),
    [
        pytest.param(["-GNinja"], None, True, id="settings-joined"),
        pytest.param(["-G", "Ninja"], None, True, id="settings-two-token"),
        pytest.param(["-GUnix Makefiles"], None, False, id="settings-non-ninja"),
        pytest.param([], "-GNinja", True, id="env-joined"),
        pytest.param([], "-G Ninja", True, id="env-two-token"),
        pytest.param([], "-GUnix Makefiles", False, id="env-non-ninja"),
        pytest.param([], None, None, id="unset"),
    ],
)
def test_uses_ninja_generator(
    args: list[str],
    cmake_args: str | None,
    expected: bool | None,
    monkeypatch: pytest.MonkeyPatch,
):
    from scikit_build_core.builder.get_requires import _uses_ninja_generator
    from scikit_build_core.settings.skbuild_model import (
        CMakeSettings,
        ScikitBuildSettings,
    )

    monkeypatch.delenv("CMAKE_ARGS", raising=False)
    if cmake_args is not None:
        monkeypatch.setenv("CMAKE_ARGS", cmake_args)
    settings = ScikitBuildSettings(cmake=CMakeSettings(args=args))
    assert _uses_ninja_generator(settings) is expected


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        pytest.param(["-GNinja"], {"ninja>=1.5"}, id="forced-ninja"),
        pytest.param([], set(), id="unset"),
    ],
)
def test_ninja_make_fallback_respects_forced_generator(
    args: list[str],
    expected: set[str],
    monkeypatch: pytest.MonkeyPatch,
):
    """
    The make fallback must not suppress the ninja requirement when the Ninja
    generator is explicitly selected - make cannot substitute for it. See #953.
    """
    from scikit_build_core.builder import get_requires
    from scikit_build_core.settings.skbuild_model import (
        CMakeSettings,
        ScikitBuildSettings,
    )

    monkeypatch.delenv("CMAKE_ARGS", raising=False)
    # Force the make-fallback branch: unknown platform with make available.
    monkeypatch.setattr(get_requires, "is_known_platform", lambda _: False)
    monkeypatch.setattr(
        get_requires, "get_make_programs", lambda: iter([Path("make/path")])
    )
    settings = ScikitBuildSettings(cmake=CMakeSettings(args=args))
    assert set(GetRequires(settings).ninja()) == expected


def test_cmake_namespace_dir_is_not_a_module(
    fp: FakeProcess, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A bare ``cmake/`` directory on sys.path is not the PyPI cmake package."""
    fp.register(
        [Path("cmake/path"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.18.0"}}',
    )
    (tmp_path / "cmake").mkdir()
    monkeypatch.setattr(importlib.util, "find_spec", REAL_FIND_SPEC)
    monkeypatch.syspath_prepend(tmp_path)

    assert set(GetRequires().cmake()) == set()


@pytest.mark.parametrize(
    ("define", "expected"),
    [
        pytest.param("Ninja", True, id="define-ninja"),
        pytest.param("Unix Makefiles", False, id="define-non-ninja"),
        pytest.param("Visual Studio 17 2022", False, id="define-vs"),
    ],
)
def test_uses_ninja_generator_define(
    define: str,
    expected: bool,
    monkeypatch: pytest.MonkeyPatch,
):
    """
    ``cmake.define.CMAKE_GENERATOR`` selects the generator for the build, so it
    must select it for the requirements too. See #1541.
    """
    from scikit_build_core.builder.get_requires import _uses_ninja_generator
    from scikit_build_core.settings.skbuild_model import (
        CMakeSettings,
        CMakeSettingsDefine,
        ScikitBuildSettings,
    )

    monkeypatch.delenv("CMAKE_ARGS", raising=False)
    settings = ScikitBuildSettings(
        cmake=CMakeSettings(define={"CMAKE_GENERATOR": CMakeSettingsDefine(define)})
    )
    assert _uses_ninja_generator(settings) is expected


def test_uses_ninja_generator_define_precedence(monkeypatch: pytest.MonkeyPatch):
    """``-G`` wins over the define, which wins over the environment."""
    from scikit_build_core.builder.get_requires import _uses_ninja_generator
    from scikit_build_core.settings.skbuild_model import (
        CMakeSettings,
        CMakeSettingsDefine,
        ScikitBuildSettings,
    )

    monkeypatch.delenv("CMAKE_ARGS", raising=False)
    monkeypatch.setenv("CMAKE_GENERATOR", "Unix Makefiles")
    settings = ScikitBuildSettings(
        cmake=CMakeSettings(define={"CMAKE_GENERATOR": CMakeSettingsDefine("Ninja")})
    )
    assert _uses_ninja_generator(settings) is True

    settings = ScikitBuildSettings(
        cmake=CMakeSettings(
            args=["-GUnix Makefiles"],
            define={"CMAKE_GENERATOR": CMakeSettingsDefine("Ninja")},
        )
    )
    assert _uses_ninja_generator(settings) is False


@pytest.mark.parametrize(
    ("define", "expected"),
    [
        pytest.param("Ninja", {"ninja>=1.5"}, id="define-ninja"),
        pytest.param("Unix Makefiles", set(), id="define-non-ninja"),
        pytest.param("Visual Studio 17 2022", set(), id="define-vs"),
    ],
)
def test_get_requires_ninja_define_generator(
    define: str,
    expected: set[str],
    monkeypatch: pytest.MonkeyPatch,
):
    """Ninja set with a define must add the ninja requirement (#1541)."""
    from scikit_build_core.settings.skbuild_model import (
        CMakeSettings,
        CMakeSettingsDefine,
        ScikitBuildSettings,
    )

    monkeypatch.delenv("CMAKE_ARGS", raising=False)
    settings = ScikitBuildSettings(
        cmake=CMakeSettings(define={"CMAKE_GENERATOR": CMakeSettingsDefine(define)})
    )
    assert set(GetRequires(settings).ninja()) == expected
