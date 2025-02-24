import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .._compat.typing import Annotated

__all__ = [
    "BackportSettings",
    "BuildSettings",
    "CMakeSettings",
    "CMakeSettingsDefine",
    "EditableSettings",
    "GenerateSettings",
    "InstallSettings",
    "LoggingSettings",
    "MessagesSettings",
    "NinjaSettings",
    "SDistSettings",
    "ScikitBuildSettings",
    "WheelSettings",
]


def __dir__() -> List[str]:
    return __all__


class CMakeSettingsDefine(str):
    """
    A str subtype for automatically normalizing bool and list values
    to the CMake representation in the `cmake.define` settings key.
    """

    json_schema = Union[str, bool, List[str]]

    def __new__(cls, raw: Union[str, bool, List[str]]) -> "CMakeSettingsDefine":
        def escape_semicolons(item: str) -> str:
            return item.replace(";", r"\;")

        if isinstance(raw, bool):
            value = "TRUE" if raw else "FALSE"
        elif isinstance(raw, list):
            value = ";".join(map(escape_semicolons, raw))
        else:
            value = raw

        return super().__new__(cls, value)


@dataclasses.dataclass
class CMakeSettings:
    minimum_version: Optional[Version] = None
    """
    DEPRECATED in 0.8; use version instead.
    """

    version: Optional[SpecifierSet] = None
    """
    The versions of CMake to allow. If CMake is not present on the system or
    does not pass this specifier, it will be downloaded via PyPI if possible. An
    empty string will disable this check. The default on 0.10+ is
    "CMakeLists.txt", which will read it from the project's CMakeLists.txt file,
    or ">=3.15" if unreadable or <0.10.
    """

    args: List[str] = dataclasses.field(default_factory=list)
    """
    A list of args to pass to CMake when configuring the project. Setting this
    in config or envvar will override toml. See also ``cmake.define``.
    """

    define: Annotated[Dict[str, CMakeSettingsDefine], "EnvVar"] = dataclasses.field(
        default_factory=dict
    )
    """
    A table of defines to pass to CMake when configuring the project. Additive.
    """

    verbose: Optional[bool] = None
    """
    DEPRECATED in 0.10, use build.verbose instead.
    """

    build_type: str = "Release"
    """
    The build type to use when building the project.
    Valid options are: "Debug", "Release", "RelWithDebInfo", "MinSizeRel",
    "", etc.
    """

    source_dir: Path = Path()
    """
    The source directory to use when building the project. Currently only
    affects the native builder (not the setuptools plugin).
    """

    targets: Optional[List[str]] = None
    """
    DEPRECATED in 0.10; use build.targets instead.
    """

    preset: Optional[str] = None
    """
    Configure preset to use. ``cmake.source-dir`` must still be appropriately defined
    and it must contain a ``CMake(User)Presets.json``. The preset's ``binaryDir`` is
    ignored and is always overwritten by the ``build-dir`` defined by scikit-build-core.
    ``cmake.define``, generator values are still passed if defined and take precedence
    over preset's value according to CMake logic.
    """


@dataclasses.dataclass
class NinjaSettings:
    minimum_version: Optional[Version] = None
    """
    DEPRECATED in 0.8; use version instead.
    """

    version: SpecifierSet = SpecifierSet(">=1.5")
    """
    The versions of Ninja to allow. If Ninja is not present on the system or does
    not pass this specifier, it will be downloaded via PyPI if possible. An empty
    string will disable this check.
    """

    make_fallback: bool = True
    """
    If Ninja is not present on the system or is older than required,
    it will be downloaded via PyPI if this is false.
    """


@dataclasses.dataclass
class LoggingSettings:
    level: Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        "WARNING"
    )
    """
    The logging level to display, "DEBUG", "INFO", "WARNING", and "ERROR" are
    possible options.
    """


@dataclasses.dataclass
class SDistSettings:
    include: List[str] = dataclasses.field(default_factory=list)
    """
    Files to include in the SDist even if they are skipped by default.
    Supports gitignore syntax.

    """

    exclude: List[str] = dataclasses.field(default_factory=list)
    """
    Files to exclude from the SDist even if they are included by default.
    Supports gitignore syntax.
    """

    reproducible: bool = True
    """
    If set to True, try to build a reproducible distribution (Unix and Python
    3.9+ recommended).  ``SOURCE_DATE_EPOCH`` will be used for timestamps, or a
    fixed value if not set.
    """

    cmake: bool = False
    """
    If set to True, CMake will be run before building the SDist.
    """


@dataclasses.dataclass
class WheelSettings:
    packages: Optional[Union[List[str], Dict[str, str]]] = None
    """
    A list of packages to auto-copy into the wheel. If this is not set, it will
    default to the first of ``src/<package>``, ``python/<package>``, or
    ``<package>`` if they exist.  The prefix(s) will be stripped from the
    package name inside the wheel. If a dict, provides a mapping of package
    name to source directory.
    """

    py_api: str = ""
    """
    The Python tags. The default (empty string) will use the default Python
    version. You can also set this to "cp38" to enable the CPython 3.8+ Stable
    ABI / Limited API (only on CPython and if the version is sufficient,
    otherwise this has no effect). Or you can set it to "py3" or "py2.py3" to
    ignore Python ABI compatibility. The ABI tag is inferred from this tag.
    """

    expand_macos_universal_tags: bool = False
    """
    Fill out extra tags that are not required. This adds "x86_64" and "arm64"
    to the list of platforms when "universal2" is used, which helps older
    Pip's (before 21.0.1) find the correct wheel.
    """

    install_dir: str = ""
    """
    The install directory for the wheel. This is relative to the platlib root.
    You might set this to the package name. The original dir is still at
    SKBUILD_PLATLIB_DIR (also SKBUILD_DATA_DIR, etc. are available).
    EXPERIMENTAL: An absolute path will be one level higher than the platlib
    root, giving access to "/platlib", "/data", "/headers", and "/scripts".
    """

    license_files: Optional[List[str]] = None
    """
    A list of license files to include in the wheel. Supports glob patterns.
    The default is ``["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]``.
    Must not be set if ``project.license-files`` is set.
    """

    cmake: bool = True
    """
    If set to True (the default), CMake will be run before building the wheel.
    """

    platlib: Optional[bool] = None
    """
    Target the platlib or the purelib. If not set, the default is to target the
    platlib if wheel.cmake is true, and the purelib otherwise.
    """

    exclude: List[str] = dataclasses.field(default_factory=list)
    """
    A set of patterns to exclude from the wheel. This is additive to the SDist
    exclude patterns. This applies to the final paths in the wheel, and can
    exclude files from CMake output as well.  Editable installs may not respect
    this exclusion.
    """

    build_tag: str = ""
    """
    The build tag to use for the wheel. If empty, no build tag is used.
    """


@dataclasses.dataclass
class BackportSettings:
    find_python: Version = Version("3.26.1")
    """
    If CMake is less than this value, backport a copy of FindPython. Set to 0
    disable this, or the empty string.
    """


@dataclasses.dataclass
class EditableSettings:
    mode: Literal["redirect", "inplace"] = "redirect"
    """
    Select the editable mode to use. Can be "redirect" (default) or "inplace".
    """

    verbose: bool = True
    """
    Turn on verbose output for the editable mode rebuilds.
    """

    rebuild: bool = False
    """
    Rebuild the project when the package is imported. The build-directory must
    be set.
    """


@dataclasses.dataclass
class BuildSettings:
    tool_args: List[str] = dataclasses.field(default_factory=list)
    """
    Extra args to pass directly to the builder in the build step.
    """

    targets: List[str] = dataclasses.field(default_factory=list)
    """
    The build targets to use when building the project. Empty builds the
    default target.
    """

    verbose: bool = False
    """
    Verbose printout when building.
    """

    requires: List[str] = dataclasses.field(default_factory=list)
    """
    Additional ``build-system.requires``. Intended to be used in combination
    with ``overrides``.
    """


@dataclasses.dataclass
class InstallSettings:
    components: List[str] = dataclasses.field(default_factory=list)
    """
    The components to install. If empty, all default components are installed.
    """

    strip: Optional[bool] = None
    """
    Whether to strip the binaries. True for release builds on scikit-build-core
    0.5+ (0.5-0.10.5 also incorrectly set this for debug builds).
    """


@dataclasses.dataclass
class GenerateSettings:
    path: Path
    """
    The path (relative to platlib) for the file to generate.
    """

    template: str = ""
    """
    The template to use for the file. This includes string.Template style
    placeholders for all the metadata. If empty, a template-path must be set.
    """

    template_path: Optional[Path] = None
    """
    The path to the template file. If empty, a template must be set.
    """

    location: Literal["install", "build", "source"] = "install"
    """
    The place to put the generated file. The "build" directory is useful for
    CMake files, and the "install" directory is useful for Python files,
    usually. You can also write directly to the "source" directory, will
    overwrite existing files & remember to gitignore the file.
    """


@dataclasses.dataclass
class MessagesSettings:
    """
    Settings for messages.
    """

    after_failure: str = ""
    """
    A message to print after a build failure.
    """

    after_success: str = ""
    """
    A message to print after a successful build.
    """


@dataclasses.dataclass
class ScikitBuildSettings:
    cmake: CMakeSettings = dataclasses.field(default_factory=CMakeSettings)
    ninja: NinjaSettings = dataclasses.field(default_factory=NinjaSettings)
    logging: LoggingSettings = dataclasses.field(default_factory=LoggingSettings)
    sdist: SDistSettings = dataclasses.field(default_factory=SDistSettings)
    wheel: WheelSettings = dataclasses.field(default_factory=WheelSettings)
    backport: BackportSettings = dataclasses.field(default_factory=BackportSettings)
    editable: EditableSettings = dataclasses.field(default_factory=EditableSettings)
    build: BuildSettings = dataclasses.field(default_factory=BuildSettings)
    install: InstallSettings = dataclasses.field(default_factory=InstallSettings)
    generate: List[GenerateSettings] = dataclasses.field(default_factory=list)
    messages: MessagesSettings = dataclasses.field(default_factory=MessagesSettings)

    metadata: Dict[str, Dict[str, Any]] = dataclasses.field(default_factory=dict)
    """
    List dynamic metadata fields and hook locations in this table.
    """

    strict_config: bool = True
    """
    Strictly check all config options. If False, warnings will be
    printed for unknown options. If True, an error will be raised.
    """

    experimental: bool = False
    """
    Enable early previews of features not finalized yet.
    """

    minimum_version: Optional[Version] = None
    """
    If set, this will provide a method for backward compatibility.
    """

    build_dir: str = ""
    """
    The build directory. Defaults to a temporary directory, but can be set.
    """

    fail: bool = False
    """
    Immediately fail the build. This is only useful in overrides.
    """
