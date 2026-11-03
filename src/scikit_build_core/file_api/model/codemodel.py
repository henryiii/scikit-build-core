__lazy_modules__ = {
    "pathlib",
    f"{__spec__.parent}.common",
    f"{__spec__.parent}.directory",
}

import dataclasses
from pathlib import Path

from .common import APIVersion, Paths
from .directory import BacktraceGraph, InstallRule

__all__ = [
    "Archive",
    "Artifact",
    "CodeModel",
    "CommandFragment",
    "CompileCommandFragment",
    "CompileDependency",
    "CompileGroup",
    "Configuration",
    "Debugger",
    "Define",
    "Dependency",
    "Destination",
    "Directory",
    "FileSet",
    "Folder",
    "FromDependency",
    "Include",
    "Install",
    "LanguageStandard",
    "Launcher",
    "Link",
    "LinkLibrary",
    "PrecompileHeader",
    "Prefix",
    "Project",
    "Source",
    "SourceGroup",
    "StringCMakeVersion",
    "Sysroot",
    "Target",
]


def __dir__() -> list[str]:
    return __all__


@dataclasses.dataclass(frozen=True)
class StringCMakeVersion:
    string: str


@dataclasses.dataclass(frozen=True)
class Directory:
    source: Path
    build: Path
    projectIndex: int
    jsonFile: Path | None = None
    parentIndex: int | None = None
    childIndexes: list[int] = dataclasses.field(default_factory=list)
    targetIndexes: list[int] = dataclasses.field(default_factory=list)
    abstractTargetIndexes: list[int] = dataclasses.field(default_factory=list)
    minimumCMakeVersion: StringCMakeVersion | None = None
    hasInstallRule: bool = False
    # From the "directory" object loaded via jsonFile:
    installers: list[InstallRule] = dataclasses.field(default_factory=list)
    backtraceGraph: BacktraceGraph | None = None
    codemodelVersion: APIVersion | None = None


@dataclasses.dataclass(frozen=True)
class Project:
    name: str
    directoryIndexes: list[int]
    parentIndex: int | None = None
    childIndexes: list[int] = dataclasses.field(default_factory=list)
    targetIndexes: list[int] = dataclasses.field(default_factory=list)
    abstractTargetIndexes: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Artifact:
    path: Path


@dataclasses.dataclass(frozen=True)
class Prefix:
    path: Path


@dataclasses.dataclass(frozen=True)
class Destination:
    path: Path
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class Install:
    prefix: Prefix
    destinations: list[Destination]


@dataclasses.dataclass(frozen=True)
class CommandFragment:
    fragment: str
    role: str


@dataclasses.dataclass(frozen=True)
class Sysroot:
    path: Path


@dataclasses.dataclass(frozen=True)
class Link:
    language: str
    commandFragments: list[CommandFragment] | None = dataclasses.field(
        default_factory=list
    )
    lto: bool | None = None
    sysroot: Sysroot | None = None


@dataclasses.dataclass(frozen=True)
class Archive:
    commandFragments: list[CommandFragment] | None = dataclasses.field(
        default_factory=list
    )
    lto: bool | None = None


@dataclasses.dataclass(frozen=True)
class Dependency:
    id: str
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class FromDependency:
    id: str


@dataclasses.dataclass(frozen=True)
class LinkLibrary:
    # Exactly one of id or fragment is present
    id: str | None = None
    fragment: str | None = None
    backtrace: int | None = None
    fromDependency: FromDependency | None = None


@dataclasses.dataclass(frozen=True)
class CompileDependency:
    id: str
    backtrace: int | None = None
    fromDependency: FromDependency | None = None


@dataclasses.dataclass(frozen=True)
class Folder:
    name: str


@dataclasses.dataclass(frozen=True)
class Launcher:
    command: Path
    type: str
    arguments: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Debugger:
    workingDirectory: Path | None = None


@dataclasses.dataclass(frozen=True)
class FileSet:
    name: str
    type: str
    visibility: str
    baseDirectories: list[Path] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class SourceGroup:
    name: str
    sourceIndexes: list[int] = dataclasses.field(default_factory=list)
    interfaceSourceIndexes: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class LanguageStandard:
    standard: str
    backtraces: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class CompileCommandFragment:
    fragment: str
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class Include:
    path: Path
    isSystem: bool | None = None
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class PrecompileHeader:
    header: Path
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class Define:
    define: str
    backtrace: int | None = None


@dataclasses.dataclass(frozen=True)
class CompileGroup:
    sourceIndexes: list[int]
    language: str
    languageStandard: LanguageStandard | None = None
    compileCommandFragments: list[CompileCommandFragment] = dataclasses.field(
        default_factory=list
    )
    includes: list[Include] = dataclasses.field(default_factory=list)
    frameworks: list[Include] = dataclasses.field(default_factory=list)
    precompileHeaders: list[PrecompileHeader] = dataclasses.field(default_factory=list)
    defines: list[Define] = dataclasses.field(default_factory=list)
    sysroot: Sysroot | None = None


@dataclasses.dataclass(frozen=True)
class Source:
    path: Path
    compileGroupIndex: int | None = None
    sourceGroupIndex: int | None = None
    isGenerated: bool | None = None
    fileSetIndex: int | None = None
    fileSetIndexes: list[int] = dataclasses.field(default_factory=list)
    backtrace: int | None = None
    backtraces: list[int] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class Target:
    name: str
    id: str
    type: str
    paths: Paths
    sources: list[Source] = dataclasses.field(default_factory=list)
    nameOnDisk: Path | None = None
    artifacts: list[Artifact] = dataclasses.field(default_factory=list)
    isGeneratorProvided: bool | None = None
    install: Install | None = None
    link: Link | None = None
    archive: Archive | None = None
    dependencies: list[Dependency] = dataclasses.field(default_factory=list)
    backtrace: int | None = None
    folder: Folder | None = None
    launchers: list[Launcher] = dataclasses.field(default_factory=list)
    debugger: Debugger | None = None
    imported: bool | None = None
    local: bool | None = None
    abstract: bool | None = None
    symbolic: bool | None = None
    linkLibraries: list[LinkLibrary] = dataclasses.field(default_factory=list)
    interfaceLinkLibraries: list[LinkLibrary] = dataclasses.field(default_factory=list)
    compileDependencies: list[CompileDependency] = dataclasses.field(
        default_factory=list
    )
    interfaceCompileDependencies: list[CompileDependency] = dataclasses.field(
        default_factory=list
    )
    objectDependencies: list[Dependency] = dataclasses.field(default_factory=list)
    orderDependencies: list[Dependency] = dataclasses.field(default_factory=list)
    fileSets: list[FileSet] = dataclasses.field(default_factory=list)
    interfaceSources: list[Source] = dataclasses.field(default_factory=list)
    sourceGroups: list[SourceGroup] = dataclasses.field(default_factory=list)
    compileGroups: list[CompileGroup] = dataclasses.field(default_factory=list)
    backtraceGraph: BacktraceGraph | None = None
    codemodelVersion: APIVersion | None = None
    # From the codemodel reference to this target:
    directoryIndex: int | None = None
    projectIndex: int | None = None


@dataclasses.dataclass(frozen=True)
class Configuration:
    name: str
    projects: list[Project]
    targets: list[Target]
    directories: list[Directory]
    abstractTargets: list[Target] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(frozen=True)
class CodeModel:
    kind: str
    version: APIVersion
    paths: Paths
    configurations: list[Configuration]
