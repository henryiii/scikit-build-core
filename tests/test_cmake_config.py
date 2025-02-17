from __future__ import annotations

import os
import shutil
import sysconfig
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING

import pytest
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from scikit_build_core.builder.builder import Builder
from scikit_build_core.cmake import CMake, CMaker
from scikit_build_core.errors import CMakeNotFoundError
from scikit_build_core.program_search import best_program, get_cmake_programs
from scikit_build_core.settings.skbuild_read_settings import SettingsReader

if TYPE_CHECKING:
    from collections.abc import Generator

DIR = Path(__file__).parent.resolve()
cmake_preset_info = best_program(get_cmake_programs(), version=SpecifierSet(">=3.19"))


def single_config(param: None | str) -> bool:
    if param is None:
        return not sysconfig.get_platform().startswith("win")

    return param in {"Ninja", "Makefiles"}


@pytest.fixture(
    params=[
        pytest.param(None, id="default"),
        pytest.param("Ninja", id="ninja"),
        pytest.param(
            "Makefiles",
            id="makefiles",
            marks=pytest.mark.skipif(
                sysconfig.get_platform().startswith("win"), reason="run on Windows only"
            ),
        ),
        pytest.param(
            "Others",
            id="others",
            marks=pytest.mark.skipif(
                sysconfig.get_platform().startswith("win"), reason="run on Windows only"
            ),
        ),
    ]
)
def generator(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> str | None:
    if request.param is None:
        monkeypatch.delenv("CMAKE_GENERATOR", raising=False)
    else:
        monkeypatch.setenv("CMAKE_GENERATOR", request.param)

    return request.param  # type: ignore[no-any-return]


def configure_args(
    config: CMaker, *, init: bool = False, single_config: bool = False
) -> Generator[str, None, None]:
    yield f"-S{config.source_dir}"
    yield f"-B{config.build_dir}"

    if single_config:
        yield f"-DCMAKE_BUILD_TYPE:STRING={config.build_type}"

    if init:
        cmake_init = config.build_dir / "CMakeInit.txt"
        yield f"-C{cmake_init}"


@pytest.mark.configure
def test_init_cache(
    generator: str,
    tmp_path: Path,
    fp,
):
    fp.register(
        [fp.program("cmake"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    fp.register(
        [fp.program("cmake3"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )

    config = CMaker(
        CMake.default_search(),
        source_dir=DIR / "packages/simple_pure",
        build_dir=tmp_path / "build",
        build_type="Release",
    )
    config.init_cache(
        {"SKBUILD": True, "SKBUILD_VERSION": "1.0.0", "SKBUILD_PATH": config.source_dir}
    )

    cmd = list(
        configure_args(config, init=True, single_config=single_config(generator))
    )
    print("Registering: cmake", *cmd)
    fp.register([fp.program("cmake"), *cmd])
    fp.register([fp.program("cmake3"), *cmd])
    config.configure()

    cmake_init = config.build_dir / "CMakeInit.txt"
    source_dir_str = str(config.source_dir).replace("\\", "/")
    assert (
        cmake_init.read_text(encoding="utf-8")
        == f"""\
set(SKBUILD ON CACHE BOOL "" FORCE)
set(SKBUILD_VERSION [===[1.0.0]===] CACHE STRING "" FORCE)
set(SKBUILD_PATH [===[{source_dir_str}]===] CACHE PATH "" FORCE)
"""
    )


@pytest.mark.configure
def test_too_old(fp, monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    fp.register(
        [fp.program("cmake"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )
    fp.register(
        [fp.program("cmake3"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.14.0"}}',
    )

    with pytest.raises(CMakeNotFoundError) as excinfo:
        CMake.default_search(version=SpecifierSet(">=3.15"))
    assert "Could not find CMake with version >=3.15" in excinfo.value.args[0]


@pytest.mark.configure
def test_cmake_args(
    generator: str,
    tmp_path: Path,
    fp,
):
    fp.register(
        [fp.program("cmake"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.15.0"}}',
    )
    fp.register(
        [fp.program("cmake3"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.15.0"}}',
    )

    config = CMaker(
        CMake.default_search(),
        source_dir=DIR / "packages" / "simple_pure",
        build_dir=tmp_path / "build",
        build_type="Release",
    )

    cmd = list(configure_args(config, single_config=single_config(generator)))
    cmd.append("-DSOMETHING=one")
    print("Registering: cmake", *cmd)
    fp.register([fp.program("cmake"), *cmd])
    fp.register([fp.program("cmake3"), *cmd])

    config.configure(cmake_args=["-DSOMETHING=one"])
    # config.configure might mutate config.single_config
    assert config.single_config == single_config(generator)
    assert len(fp.calls) == 2


@pytest.mark.configure
def test_cmake_paths(
    generator: str,
    tmp_path: Path,
    fp,
):
    fp.register(
        [fp.program("cmake"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.15.0"}}',
    )
    fp.register(
        [fp.program("cmake3"), "-E", "capabilities"],
        stdout='{"version":{"string":"3.15.0"}}',
    )

    config = CMaker(
        CMake.default_search(),
        source_dir=DIR / "packages/simple_pure",
        build_dir=tmp_path / "build",
        build_type="Release",
        prefix_dirs=[tmp_path / "prefix"],
        module_dirs=[tmp_path / "module"],
    )

    cmd = list(configure_args(config, single_config=single_config(generator)))
    print("Registering: cmake", *cmd)
    fp.register([fp.program("cmake"), *cmd])
    fp.register([fp.program("cmake3"), *cmd])

    config.configure()

    assert len(fp.calls) == 2


@pytest.mark.parametrize(
    "with_preset",
    [
        pytest.param(
            True,
            marks=pytest.mark.skipif(
                cmake_preset_info is None,
                reason="CMake version does not support presets.",
            ),
        ),
        False,
    ],
)
@pytest.mark.configure
def test_cmake_defines(
    monkeypatch,
    tmp_path: Path,
    with_preset: bool,
):
    monkeypatch.setenv("WITH_PRESET", f"{with_preset}")
    source_dir = DIR / "packages" / "cmake_defines"
    binary_dir = tmp_path / "build"

    config = CMaker(
        CMake.default_search(),
        source_dir=source_dir,
        build_dir=binary_dir,
        build_type="Release",
    )

    reader = SettingsReader.from_file(source_dir / "pyproject.toml")

    builder = Builder(reader.settings, config)
    builder.configure(defines={})

    configure_log = Path.read_text(binary_dir / "log.txt")

    # This var is always overwritten
    overwritten_var = "overwritten"
    preset_only_var = "defined" if with_preset else ""
    assert configure_log == dedent(
        f"""\
        PRESET_ONLY_VAR={preset_only_var}
        OVERWRITTEN_VAR={overwritten_var}
        ONE_LEVEL_LIST.LENGTH = 4
        Foo
        Bar
        ExceptionallyLargeListEntryThatWouldOverflowTheLine
        Baz
        NESTED_LIST.LENGTH = 3
        Apple
        Lemon;Lime
        Banana
        """
    )


def test_get_cmake_via_envvar(monkeypatch: pytest.MonkeyPatch, fp):
    monkeypatch.setattr("shutil.which", lambda x: x)
    cmake_path = Path("some-prog")
    fp.register(
        [cmake_path, "-E", "capabilities"], stdout='{"version":{"string":"3.20.0"}}'
    )
    monkeypatch.setenv("CMAKE_EXECUTABLE", str(cmake_path))
    result = CMake.default_search(env=os.environ)
    assert result.cmake_path == cmake_path
    assert result.version == Version("3.20.0")
