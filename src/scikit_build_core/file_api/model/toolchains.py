__lazy_modules__ = {"pathlib"}

import dataclasses
from pathlib import Path

from .common import APIVersion

__all__ = ["Compiler", "Implicit", "Toolchain", "Toolchains"]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class Implicit:
    includeDirectories: list[Path] = dataclasses.field(default_factory=list)
    linkDirectories: list[Path] = dataclasses.field(default_factory=list)
    linkFrameworkDirectories: list[Path] = dataclasses.field(default_factory=list)
    linkLibraries: list[Path] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Compiler:
    implicit: Implicit
    path: Path | None = None
    commandFragment: str | None = None
    id: str | None = None
    version: str | None = None
    target: str | None = None


@dataclasses.dataclass(frozen=True)
class Toolchain:
    language: str  # Unique, since CMake supports one toolchain per language
    compiler: Compiler
    sourceFileExtensions: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Toolchains:
    kind: str = "toolchains"
    version: APIVersion = APIVersion(1, 0)  # noqa: RUF009
    toolchains: list[Toolchain] = dataclasses.field(default_factory=list)
