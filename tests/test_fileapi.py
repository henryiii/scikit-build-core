from __future__ import annotations

from pathlib import Path

import pytest
from packaging.version import Version

from scikit_build_core.cmake import CMake, CMakeConfig
from scikit_build_core.file_api._cattrs_converter import (
    load_reply_dir as load_reply_dir_cattrs,
)
from scikit_build_core.file_api.query import stateless_query
from scikit_build_core.file_api.reply import load_reply_dir

DIR = Path(__file__).parent.absolute()


@pytest.mark.configure
def test_cattrs_comparison(tmp_path):

    build_dir = tmp_path / "build"

    cmake = CMake.default_search(minimum_version=Version("3.15"))
    config = CMakeConfig(
        cmake,
        source_dir=DIR / "simple_pure",
        build_dir=build_dir,
    )

    reply_dir = stateless_query(config.build_dir)

    config.configure()

    cattrs_index = load_reply_dir_cattrs(reply_dir)
    index = load_reply_dir(reply_dir)
    assert index == cattrs_index


# TODO: Why is this an IndexError?
def test_no_index(tmp_path):
    with pytest.raises(IndexError):
        load_reply_dir(tmp_path)

    with pytest.raises(IndexError):
        load_reply_dir_cattrs(tmp_path)


@pytest.mark.configure
def test_simple_pure(tmp_path):
    build_dir = tmp_path / "build"

    cmake = CMake.default_search(minimum_version=Version("3.15"))
    config = CMakeConfig(
        cmake,
        source_dir=DIR / "simple_pure",
        build_dir=build_dir,
    )

    reply_dir = stateless_query(config.build_dir)
    config.configure()
    index = load_reply_dir(reply_dir)

    codemodel = index.reply.codemodel_v2
    assert codemodel is not None

    cache = index.reply.cache_v2
    assert cache is not None

    cmakefiles = index.reply.cmakefiles_v1
    assert cmakefiles is not None

    toolchains = index.reply.toolchains_v1
    assert toolchains is not None


def test_included_dir():
    reply_dir = DIR / "api/simple_pure/.cmake/api/v1/reply"

    index = load_reply_dir(reply_dir)

    assert index.cmake.version.string == "3.24.1"
    assert index.cmake.generator.name == "Ninja"
    assert len(index.objects) == 4

    codemodel = index.reply.codemodel_v2
    assert codemodel is not None
    assert codemodel.kind == "codemodel"
    assert codemodel.version.major == 2
    assert codemodel.version.minor == 4
    assert codemodel.configurations[0].name == ""

    cache = index.reply.cache_v2
    assert cache is not None

    cmakefiles = index.reply.cmakefiles_v1
    assert cmakefiles is not None

    toolchains = index.reply.toolchains_v1
    assert toolchains is not None
