import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .._compat.typing import Annotated, Self

__all__ = [
    "BackportSettings",
    "BuildSettings",
    "CMakeSettings",
    "CMakeSettingsDefine",
    "EditableSettings",
    "EnvValue",
    "GenerateSettings",
    "InstallSettings",
    "LoggingSettings",
    "MessagesSettings",
    "NinjaSettings",
    "SDistSettings",
    "ScikitBuildSettings",
    "SearchSettings",
    "SettingsFieldMetadata",
    "WheelSettings",
]


def __dir__() -> List[str]:
    return __all__


def normalize_build_types(build_type: Union[str, List[str]]) -> List[str]:
    """
    Normalize ``cmake.build-type`` into a non-empty list of build types.

    A plain string becomes a single-element list. An empty list is treated as
    a single empty build type, preserving the "no explicit build type" behavior.
    """
    if isinstance(build_type, str):
        return [build_type]
    return build_type or [""]


class SettingsFieldMetadata(TypedDict, total=False):
    display_default: Optional[str]
    deprecated: bool
    override_only: bool
    """Do not allow the field to be a top-level table."""


class CMakeSettingsDefine(str):
    """
    A str subtype for automatically normalizing bool and list values
    to the CMake representation in the `cmake.define` settings key.
    """

    __slots__ = ()

    json_schema = Union[str, bool, List[str]]

    def __new__(cls, raw: Union[str, bool, List[str]]) -> Self:
        def escape_semicolons(item: str) -> str:
            return item.replace(";", r"\;")

        if isinstance(raw, bool):
            value = "TRUE" if raw else "FALSE"
        elif isinstance(raw, list):
            value = ";".join(map(escape_semicolons, raw))
        else:
            value = raw

        return super().__new__(cls, value)


class EnvValue:
    """
    A single entry in the top-level ``env`` table.

    Accepts either a literal string or a table with ``env`` / ``default`` /
    ``force`` keys. Resolution against the build environment is deferred to
    :meth:`resolve` so that the ``force`` flag survives parsing (unlike the
    ``cmake.define`` ``EnvVar`` form, which resolves at parse time). A bare
    string is shorthand for ``{ default = "<string>" }``.
    """

    __slots__ = ("default", "env", "force")

    def __init__(self, raw: Union[str, Dict[str, Any]]) -> None:
        self.env: Optional[str] = None
        self.default: Optional[str] = None
        self.force: bool = False

        if isinstance(raw, str):
            self.default = raw
            return
        if not isinstance(raw, dict):
            msg = f"Expected str or table for an env value, got {type(raw).__name__}"
            raise TypeError(msg)

        extra = set(raw) - {"env", "default", "force"}
        if extra:
            msg = f"Unrecognized env table keys: {sorted(extra)}"
            raise TypeError(msg)

        env = raw.get("env")
        if env is not None and not isinstance(env, str):
            msg = f"env table 'env' must be a string, got {type(env).__name__}"
            raise TypeError(msg)
        default = raw.get("default")
        if default is not None and not isinstance(default, str):
            msg = f"env table 'default' must be a string, got {type(default).__name__}"
            raise TypeError(msg)
        # Note: bool is an int subclass, so this rejects 0/1 as well as strings;
        # the value must be a real TOML boolean (not coerced like ``bool("false")``).
        force = raw.get("force", False)
        if not isinstance(force, bool):
            msg = f"env table 'force' must be a boolean, got {type(force).__name__}"
            raise TypeError(msg)

        self.env = env
        self.default = default
        self.force = force

    def resolve(self, env: Dict[str, str]) -> Optional[str]:
        """
        Resolve to the final string value (or ``None`` if unset) against ``env``.

        ``env`` (if set) is looked up in the environment with ``default`` as the
        fallback. ``None`` means "leave the variable unset".
        """
        got = env.get(self.env, self.default) if self.env is not None else self.default
        return None if got is None else str(got)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EnvValue):
            return NotImplemented
        return (self.env, self.default, self.force) == (
            other.env,
            other.default,
            other.force,
        )

    def __hash__(self) -> int:
        return hash((self.env, self.default, self.force))

    def __repr__(self) -> str:
        return (
            f"EnvValue(env={self.env!r}, default={self.default!r}, "
            f"force={self.force!r})"
        )


@dataclasses.dataclass
class CMakeSettings:
    minimum_version: Optional[Version] = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.8; use version instead.
    """

    version: Optional[SpecifierSet] = None
    """
    The versions of CMake to allow as a python-compatible specifier.

    If CMake is not present on the system or does not pass this specifier, it will
    be downloaded via PyPI if possible with the equivalent specifier used.

    An empty string will disable this check.

    Special cases:
      - On scikit-build-core 0.10+ ``CMakeLists.txt`` is the default value otherwise it's
        ``>=3.15``.
      - If ``CMakeLists.txt`` is passed, the ``cmake_minimum_required`` is read from the
        CMakeLists.txt file, using that as the minimum specifier. If the file fails to read,
        ``>=3.15`` is used instead.

    .. seealso::
       :confval:`ninja.version`
    """

    args: List[str] = dataclasses.field(default_factory=list)
    """
    A list of args to pass to CMake when configuring the project.

    Setting this in config or envvar will override toml.

    .. seealso::
       :confval:`cmake.define`
    """

    define: Annotated[Dict[str, CMakeSettingsDefine], "EnvVar"] = dataclasses.field(
        default_factory=dict
    )
    """
    A table of defines to pass to CMake when configuring the project. Additive.
    """

    verbose: Optional[bool] = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.10, use build.verbose instead.
    """

    build_type: Union[str, List[str]] = "Release"
    """
    The build type to use when building the project.

    Pre-defined CMake options are: ``Debug``, ``Release``, ``RelWithDebInfo``, ``MinSizeRel``

    Custom values can also be used.

    A list of build types can be given to build and install more than one
    configuration into the same wheel: ``["Release", "Debug"]`` in TOML, a
    repeated ``-Ccmake.build-type=...`` config-setting, or ``Release;Debug`` as
    an environment variable.
    Single-config generators (Ninja, Makefiles) are reconfigured in place for
    each extra build type; multi-config generators (Visual Studio, Xcode,
    Ninja Multi-Config) build each ``--config``. Every build type is installed
    to the same prefix, so use ``CMAKE_<CONFIG>_POSTFIX`` to avoid clobbering
    files between configurations.
    """

    source_dir: Path = Path()
    """
    The source directory to use when building the project.

    Currently only affects the native builder (not the setuptools plugin).
    """

    targets: Optional[List[str]] = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.10; use build.targets instead.
    """

    toolchain_file: Optional[Path] = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(override_only=True)
    )
    """
    The CMAKE_TOOLCHAIN_FILE / --toolchain used for cross-compilation.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """

    python_hints: bool = True
    """
    Do not pass the current environment's python hints such as ``Python_EXECUTABLE``.
    Primarily used for cross-compilation where the CMAKE_TOOLCHAIN_FILE should handle it
    instead.
    """


@dataclasses.dataclass
class SearchSettings:
    site_packages: bool = True
    """
    Add the python build environment site_packages folder to the CMake prefix paths.
    """


@dataclasses.dataclass
class NinjaSettings:
    minimum_version: Optional[Version] = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.8; use version instead.
    """

    version: SpecifierSet = SpecifierSet(">=1.5")
    """
    The versions of Ninja to allow.

    If Ninja is not present on the system or does not pass this specifier, it will
    be downloaded via PyPI if possible with the equivalent specifier used.

    An empty string will disable this check.

    .. seealso::
       - :confval:`cmake.version`
       - :confval:`ninja.make-fallback`
    """

    make_fallback: bool = True
    """
    Use Make as a fallback if a suitable Ninja executable is not found.

    If Make is also not available on the system, a ninja dependency is added to the
    ``build-system.requires`` according to :confval:`ninja.version`.

    .. seealso::
       :confval:`ninja.version`
    """


@dataclasses.dataclass
class LoggingSettings:
    level: Literal["NOTSET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = (
        "WARNING"
    )
    """
    The logging level to display.
    """


@dataclasses.dataclass
class SDistSettings:
    include: List[str] = dataclasses.field(default_factory=list)
    """
    Files to include in the SDist even if they are skipped by default. Supports gitignore syntax.

    Always takes precedence over :confval:`sdist.exclude`

    .. seealso::
       :confval:`sdist.exclude`
    """

    exclude: List[str] = dataclasses.field(default_factory=list)
    """
    Files to exclude from the SDist even if they are included by default. Supports gitignore syntax.

    .. seealso::
       :confval:`sdist.include`
    """

    inclusion_mode: Optional[Literal["classic", "default", "manual", "explicit"]] = (
        dataclasses.field(
            default=None,
            metadata=SettingsFieldMetadata(display_default='"default"  # "classic"'),
        )
    )
    """
    Method to use to compute the files to include and exclude.

    The methods are:

    * "default": Process the git ignore files. Shortcuts on ignored directories.
    * "classic": The behavior before 0.12, like "default" but does not shortcut directories.
    * "manual": No extra logic, based on include/exclude only.
    * "explicit": Opt-in only. Nothing is included unless it matches an ``include``
      pattern, and ``exclude`` is applied after, so it can trim included files back
      out. Like "manual", git ignore files are not read. (1.0+)

    If you don't set this, it will be "default" unless you set the minimum
    version below 0.12, in which case it will be "classic".

    .. versionadded: 0.12
    """

    reproducible: bool = True
    """
    Try to build a reproducible distribution.

    Unix and Python 3.9+ recommended.

    ``SOURCE_DATE_EPOCH`` will be used for timestamps, or a fixed value if not set.
    """

    cmake: bool = False
    """
    Run CMake before building the SDist.

    By default this is a configure-only run, for projects that need a configure
    artifact (e.g. a FetchContent-populated source tree) vendored into the SDist.
    Set :confval:`sdist.install-dir` as well to instead run a full configure +
    build + install and vendor the install tree, so a build from the unpacked
    SDist can repackage it with ``wheel.cmake = false`` and no CMake.
    """

    install_dir: str = ""
    """
    SDist-relative directory to vendor the CMake install tree into.

    When set (and :confval:`sdist.cmake` is true), the SDist build runs a full
    configure + build + install and writes the staged wheel trees here, one
    subdirectory per tree (``platlib``/``purelib``, ``data``, ``headers``,
    ``scripts``, ``metadata``). A wheel built from the unpacked SDist then
    restages those trees automatically with no CMake (pure/``purelib`` wheels
    only); set ``wheel.cmake`` explicitly to opt out. See the docs for the
    compiled-wheel ``wheel.force-include`` recipe.
    """

    force_include: Dict[str, str] = dataclasses.field(default_factory=dict)
    """
    Force-include files into the SDist.

    Maps source paths to destinations relative to the SDist root. Keys are
    relative to the project root; they may point outside it (e.g. ``../shared``)
    or be absolute, and ``~`` is expanded. A source may be a file or a directory;
    directories are copied recursively, skipping VCS and ``__pycache__`` junk.

    Force-included files override files at the same destination. A missing source
    is an error.

    A force-included *file* is forced in even if :confval:`sdist.exclude` matches
    its destination, since naming an exact source is an explicit request. A
    force-included *directory* stays subject to :confval:`sdist.exclude`, so a
    bulk copy can still be trimmed by an exclude pattern.
    """

    resolve_symlinks: Optional[Literal["all", "none"]] = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(display_default='"all"'),
    )
    """
    Which symlinks to resolve in the SDist, storing the target's contents instead.

    The modes are:

    * "all": Resolve every symlink, copying its target's contents.
    * "none": Store symlinks as-is.

    If you don't set this, it will be "all" unless you set the minimum version
    below 1.0, in which case it will be "none" to preserve backward compatibility.

    .. versionadded: 1.0
    """


@dataclasses.dataclass
class WheelSettings:
    packages: Optional[Union[List[str], Dict[str, str]]] = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(
            display_default='["src/<package>", "python/<package>", "<package>"]'
        ),
    )
    """
    A list of packages to auto-copy into the wheel.

    If this is not set, it will default to the first of ``src/<package>``, ``python/<package>``, or
    ``<package>`` if they exist.  The prefix(s) will be stripped from the
    package name inside the wheel.

    If a dict, provides a mapping of package name to source directory.
    """

    py_api: str = ""
    """
    The Python version tag used in the wheel file.

    The default (empty string) will use the default Python version.

    You can also set this to "cp38" to enable the CPython 3.8+ Stable
    ABI / Limited API (only on CPython and if the version is sufficient,
    otherwise this has no effect). For free-threaded Python, you can use
    "cp315t" to enable the free-threaded stable ABI (only on CPython
    free-threaded builds and if the version is sufficient). Or you can set
    it to "py3" or "py2.py3" to ignore Python ABI compatibility. The ABI
    tag is inferred from this tag.

    This value is used to construct ``SKBUILD_SABI_COMPONENT`` CMake variable.
    """

    expand_macos_universal_tags: bool = False
    """
    Fill out extra tags that are not required.

    This adds "x86_64" and "arm64" to the list of platforms when "universal2" is used,
    which helps older Pip's (before 21.0.1) find the correct wheel.
    """

    install_dir: str = ""
    """
    The CMake install prefix relative to the platlib wheel path.

    You might set this to the package name to install everything under the package namespace
    in a pythonic design.

    The original dir is still at ``SKBUILD_PLATLIB_DIR`` (also ``SKBUILD_DATA_DIR``, etc.
    are available).

    A ``${SKBUILD_<TREE>_DIR}`` prefix (e.g. ``${SKBUILD_DATA_DIR}/foo``) targets that
    wheel tree instead of the platlib, matching the ``SKBUILD_*_DIR`` CMake cache
    variables. Available trees: ``PLATLIB``/``PURELIB``, ``DATA``, ``HEADERS``,
    ``SCRIPTS``, ``METADATA``, ``NULL``.

    .. warning::
       EXPERIMENTAL A leading-slash absolute path (``/platlib``, ``/data``,
       ``/headers``, ``/scripts``, ...) is the deprecated spelling of the
       ``${SKBUILD_<TREE>_DIR}`` form and is one level higher than the platlib root.
    """

    license_files: Optional[List[str]] = None
    """
    A list of license files to include in the wheel. Supports glob patterns.

    The default is ``["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]``.

    .. warning::
       Must not be set if ``project.license-files`` is set.
    """

    cmake: bool = True
    """
    Run CMake as part of building the wheel.
    """

    platlib: Optional[bool] = None
    """
    Target the platlib or the purelib.

    If not set, the default is to target the platlib if :confval:`wheel.cmake` is ``true``,
    and the purelib otherwise.
    """

    exclude: List[str] = dataclasses.field(default_factory=list)
    """
    A set of patterns to exclude from the wheel.

    This is additive to the SDist exclude patterns. This applies to the final paths
    in the wheel, and can exclude files from CMake output as well.  Editable installs
    may not respect this exclusion.
    """

    build_tag: str = ""
    """
    The build tag to use for the wheel. If empty, no build tag is used.
    """

    tags: Optional[List[str]] = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Wheel tags to manually force, {interpreter}-{abi}-{platform} format.

    Manually specify the wheel tags to use, ignoring other inputs such as
    ``wheel.py-api``. Each tag must be of the format
    {interpreter}-{abi}-{platform}.  If not specified, these tags are
    automatically calculated. This cannot be set in the static
    ``[tool.scikit-build]`` table; use it in an override, config-settings, or an
    environment variable.
    """

    force_include: Dict[str, str] = dataclasses.field(default_factory=dict)
    """
    Force-include files into the wheel.

    Maps source paths to destinations relative to the platlib (the package
    area). Keys are relative to the project root; they may point outside it
    (e.g. ``../shared``) or be absolute, and ``~`` is expanded. A source may be a
    file or a directory; directories are copied recursively, skipping VCS and
    ``__pycache__`` junk.

    A ``${SKBUILD_<TREE>_DIR}`` prefix (e.g. ``${SKBUILD_DATA_DIR}/foo``) targets
    that wheel tree instead of the platlib, matching the ``SKBUILD_*_DIR`` CMake
    cache variables (``DATA``, ``SCRIPTS``, ``HEADERS``, ``PLATLIB``,
    ``METADATA``, ...). The deprecated leading-slash form (``/data``, ``/scripts``,
    ...) selects the same trees but requires :confval:`experimental`.

    Force-included files are placed last, so they override discovered package
    files and CMake output at the same destination. A missing source is an error.

    A force-included *file* also overrides :confval:`wheel.exclude`, since naming
    an exact source is an explicit request for that file. A force-included
    *directory* stays subject to :confval:`wheel.exclude`, so a bulk copy can
    still be trimmed by an exclude pattern.

    If a source is missing on disk, it is looked up through
    :confval:`sdist.force-include` (by exact destination or under a force-included
    directory) and read from that original source instead. This lets a source
    that names an sdist output (vendored via :confval:`sdist.force-include`) build
    from both a source tree and an unpacked sdist.
    """


@dataclasses.dataclass
class BackportSettings:
    find_python: Version = Version("3.26.1")
    """
    If CMake is less than this value, backport a copy of FindPython.

    Set to ``0`` or an empty string to disable this.
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
    Rebuild the project when the package is imported.

    :confval:`build-dir` must be set.
    """


@dataclasses.dataclass
class BuildSettings:
    tool_args: List[str] = dataclasses.field(default_factory=list)
    """
    Extra args to pass directly to the builder in the build step.
    """

    targets: List[str] = dataclasses.field(default_factory=list)
    """
    The build targets to use when building the project.

    If not specified or an empty list, the default target is used.
    """

    verbose: bool = False
    """
    Verbose printout when building.

    Equivalent to ``CMAKE_VERBOSE_MAKEFILE``.
    """

    requires: List[str] = dataclasses.field(default_factory=list)
    """
    Additional ``build-system.requires``.

    Intended to be used in combination with ``overrides``.
    """


@dataclasses.dataclass
class InstallSettings:
    components: List[str] = dataclasses.field(default_factory=list)
    """
    The components to install.

    If not specified or an empty list, all default components are installed.
    """

    targets: List[str] = dataclasses.field(default_factory=list)
    """
    Build targets to run during the install step via ``cmake --build --target``.

    This is intended for projects that group their install rules under an
    umbrella "distribution" build target (such as LLVM's ``install-distribution``)
    rather than using CMake install ``COMPONENT``\\ s. Each listed target is built,
    which triggers its install rules into the staging prefix.

    This relies on the configure-time ``CMAKE_INSTALL_PREFIX`` (set automatically
    by scikit-build-core to the wheel staging directory); the ``--strip`` and
    ``--component`` options of ``cmake --install`` do not apply to these targets.
    ``components`` and ``targets`` may be combined; both will run.
    """

    strip: Optional[bool] = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(display_default="true")
    )
    """
    Whether to strip the binaries.

    Equivalent to ``--strip`` in ``cmake install``.

    True for release builds (`Release` or `MinSizeRel`) on scikit-build-core 0.5+.

    .. note::
       0.5-0.10.5 also incorrectly set this for debug builds.
    """


@dataclasses.dataclass
class GenerateSettings:
    path: Path
    """
    The path (relative to platlib) for the file to generate.
    """

    template: str = ""
    """
    The template string to use for the file.

    Template style placeholders are available for all the metadata.

    Either this or :confval:`generate[].template-path` must be set.

    .. seealso::
       :confval:`generate[].template-path`
    """

    template_path: Optional[Path] = None
    """
    The path to the template file. If empty, a template must be set.

    Either this or :confval:`generate[].template` must be set.

    .. seealso::
       :confval:`generate[].template`
    """

    location: Literal["install", "build", "source"] = "install"
    """
    The place to put the generated file.

    The ``build`` directory is useful for CMake files, and the ``install`` directory is
    useful for Python files, usually. You can also write directly to the ``source``
    directory, will overwrite existing files & remember to gitignore the file.
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
    search: SearchSettings = dataclasses.field(default_factory=SearchSettings)

    metadata: Dict[str, Dict[str, Any]] = dataclasses.field(default_factory=dict)
    """
    List dynamic metadata fields and hook locations in this table.
    """

    env: Annotated[Dict[str, EnvValue], "EnvTable"] = dataclasses.field(
        default_factory=dict
    )
    """
    A table of environment variables to set for the CMake subprocesses.

    Applied to the configure, build, and install steps. A variable is only set if
    not already present (like a ``setdefault``); pass ``force = true`` to
    overwrite. Each value is a literal string or a table with ``env`` (read from
    another environment variable), ``default``, and ``force``; an entry that
    resolves to nothing is skipped. Independent of the ``if.env`` override
    condition.
    """

    strict_config: bool = True
    """
    Strictly check all config options.

    If False, warnings will be printed for unknown options.

    If True, an error will be raised.
    """

    experimental: bool = False
    """
    Enable early previews of features not finalized yet.
    """

    variant: List[str] = dataclasses.field(
        default_factory=list,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 variant properties.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """

    variant_name: List[str] = dataclasses.field(
        default_factory=list,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 variant properties used for wheel metadata selection.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """

    variant_label: Optional[str] = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 wheel variant label override.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """

    null_variant: bool = dataclasses.field(
        default=False,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 null-variant selector.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """

    minimum_version: Optional[Version] = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(
            display_default='"{version}"  # current version'
        ),
    )
    """
    If set, this will provide a method for backward compatibility.
    """

    build_dir: str = ""
    """
    The CMake build directory. Defaults to a unique temporary directory.

    This can be set to reuse the build directory from previous runs.
    """

    fail: Optional[bool] = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Immediately fail the build. This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """
