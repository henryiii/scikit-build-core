__lazy_modules__ = {
    "pathlib",
    f"{__spec__.parent}.cache",
    f"{__spec__.parent}.cmakefiles",
    f"{__spec__.parent}.codemodel",
    f"{__spec__.parent}.common",
    f"{__spec__.parent}.toolchains",
}

import dataclasses
from pathlib import Path

from .cache import Cache
from .cmakefiles import CMakeFiles
from .codemodel import CodeModel
from .common import APIVersion
from .toolchains import Toolchains

__all__ = [
    "CMake",
    "CMakePaths",
    "CMakeVersion",
    "Generator",
    "Index",
    "Object",
    "Reply",
]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class CMakeVersion:
    major: int
    minor: int
    patch: int
    suffix: str
    string: str
    isDirty: bool


@dataclasses.dataclass(frozen=True)
class CMakePaths:
    cmake: Path
    ctest: Path
    cpack: Path
    root: Path


@dataclasses.dataclass(frozen=True)
class Generator:
    name: str
    multiConfig: bool | None = None
    platform: str | None = None


@dataclasses.dataclass(frozen=True)
class CMake:
    version: CMakeVersion
    paths: CMakePaths
    generator: Generator


@dataclasses.dataclass(frozen=True)
class Reply:
    codemodel_v2: CodeModel | None = None
    cache_v2: Cache | None = None
    cmakefiles_v1: CMakeFiles | None = None
    toolchains_v1: Toolchains | None = None


@dataclasses.dataclass(frozen=True)
class Object:
    kind: str
    version: APIVersion
    jsonFile: Path


@dataclasses.dataclass(frozen=True)
class Index:
    cmake: CMake
    objects: list[Object]
    reply: Reply
