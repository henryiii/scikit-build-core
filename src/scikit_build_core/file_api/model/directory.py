__lazy_modules__ = {"pathlib", f"{__spec__.parent}.common"}

import dataclasses
from pathlib import Path

from .common import APIVersion, Paths

__all__ = [
    "BacktraceGraph",
    "Directory",
    "InstallPath",
    "InstallRule",
    "Node",
    "Target",
]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class Target:
    id: str
    index: int


@dataclasses.dataclass(frozen=True)
class InstallPath:
    from_: Path
    to: Path


@dataclasses.dataclass(frozen=True)
class InstallRule:
    component: str
    type: str
    destination: Path | None = None
    paths: list[Path | InstallPath] = dataclasses.field(default_factory=list)
    isExcludeFromAll: bool = False
    isForAllComponents: bool = False
    isOptional: bool = False
    targetId: str | None = None
    targetIndex: int | None = None
    targetIsImportLibrary: bool = False
    targetInstallNamelink: str | None = None
    exportName: str | None = None
    exportTargets: list[Target] = dataclasses.field(default_factory=list)
    runtimeDependencySetName: str | None = None
    runtimeDependencySetType: str | None = None
    fileSetName: str | None = None
    fileSetType: str | None = None
    fileSetDirectories: list[Path] = dataclasses.field(default_factory=list)
    fileSetTarget: Target | None = None
    cxxModuleBmiTarget: Target | None = None
    scriptFile: Path | None = None
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class Node:
    file: int
    line: int | None = None
    command: int | None = None
    parent: int | None = None


@dataclasses.dataclass(frozen=True)
class BacktraceGraph:
    nodes: list[Node]
    commands: list[str]
    files: list[Path]


@dataclasses.dataclass(frozen=True)
class Directory:
    paths: Paths
    installers: list[InstallRule]
    backtraceGraph: BacktraceGraph
    codemodelVersion: APIVersion | None = None
