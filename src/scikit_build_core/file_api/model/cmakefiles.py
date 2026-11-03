__lazy_modules__ = {"pathlib", f"{__spec__.parent}.common"}

import dataclasses
from pathlib import Path

from .common import APIVersion, Paths

__all__ = ["CMakeFiles", "GlobDependent", "Input"]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class Input:
    path: Path
    isGenerated: bool = False
    isExternal: bool = False
    isCMake: bool = False


@dataclasses.dataclass(frozen=True)
class GlobDependent:
    expression: str
    recurse: bool = False
    listDirectories: bool = False
    followSymlinks: bool = False
    relative: str | None = None
    paths: list[Path] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class CMakeFiles:
    kind: str
    version: APIVersion
    paths: Paths
    inputs: list[Input]
    globsDependent: list[GlobDependent] = dataclasses.field(default_factory=list)
