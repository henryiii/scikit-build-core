__lazy_modules__ = {f"{(__spec__.parent or '').rsplit('.', 1)[0]}._compat.typing"}

import dataclasses
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .._compat.typing import Self

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


def __dir__() -> list[str]:
    return __all__


def normalize_build_types(build_type: str | list[str]) -> list[str]:
    """
    Normalize ``cmake.build-type`` into a non-empty list of build types.

    A plain string becomes a single-element list. An empty list is treated as
    a single empty build type, preserving the "no explicit build type" behavior.
    """
    if isinstance(build_type, str):
        return [build_type]
    return build_type or [""]


class SettingsFieldMetadata(TypedDict, total=False):
    display_default: str | None
    deprecated: bool
    override_only: bool
    """Do not allow the field to be a top-level table."""


class CMakeSettingsDefine(str):
    """
    A str subtype for automatically normalizing bool and list values
    to the CMake representation in the `cmake.define` settings key.
    """

    __slots__ = ()

    json_schema = str | bool | list[str]

    def __new__(cls, raw: str | bool | list[str]) -> Self:
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

    def __init__(self, raw: str | dict[str, Any]) -> None:
        self.env: str | None = None
        self.default: str | None = None
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

    def resolve(self, env: dict[str, str]) -> str | None:
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
    minimum_version: Version | None = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.8; use version instead.
    """

    version: SpecifierSet | None = None
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

    args: list[str] = dataclasses.field(default_factory=list)
    """
    A list of args to pass to CMake when configuring the project.

    Setting this in config or envvar will override toml.

    .. seealso::
       :confval:`cmake.define`
    """

    define: Annotated[dict[str, CMakeSettingsDefine], "EnvVar"] = dataclasses.field(
        default_factory=dict
    )
    """
    A table of defines to pass to CMake when configuring the project. Additive.
    """

    verbose: bool | None = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.10, use build.verbose instead.
    """

    build_type: str | list[str] = "Release"
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

    .. versionchanged:: 1.0
       A list of build types can now be given.
    """

    source_dir: Path = Path()
    """
    The source directory to use when building the project.

    Currently only affects the native builder (not the setuptools plugin).
    """

    targets: list[str] | None = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(deprecated=True)
    )
    """
    DEPRECATED in 0.10; use build.targets instead.
    """

    toolchain_file: Path | None = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(override_only=True)
    )
    """
    The CMAKE_TOOLCHAIN_FILE / --toolchain used for cross-compilation.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """

    fresh: bool = False
    """
    Discard any cached CMake configuration and configure from scratch, like ``cmake --fresh``.

    Only affects a persistent :confval:`build-dir`. Most useful as a
    config-setting, an environment variable, or in an override.

    .. versionadded:: 1.1
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
    minimum_version: Version | None = dataclasses.field(
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
    include: list[str] = dataclasses.field(default_factory=list)
    """
    Files to include in the SDist even if they are skipped by default. Supports gitignore syntax.

    Always takes precedence over :confval:`sdist.exclude`

    .. seealso::
       :confval:`sdist.exclude`
    """

    exclude: list[str] = dataclasses.field(default_factory=list)
    """
    Files to exclude from the SDist even if they are included by default. Supports gitignore syntax.

    .. seealso::
       :confval:`sdist.include`
    """

    inclusion_mode: Literal["classic", "default", "manual", "explicit"] | None = (
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
      out. Like "manual", git ignore files are not read.

    If you don't set this, it will be "default" unless you set the minimum
    version below 0.12, in which case it will be "classic".

    .. versionadded:: 0.12
    .. versionchanged:: 1.0
       Added the "explicit" mode.
    """

    reproducible: bool = True
    """
    Try to build a reproducible distribution.

    Unix and Python 3.10+ recommended.

    ``SOURCE_DATE_EPOCH`` will be used for timestamps, or a fixed value if not set.
    """

    cmake: bool = False
    """
    If set to True, CMake will be run before building the SDist.
    """

    force_include: dict[str, str] = dataclasses.field(default_factory=dict)
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

    .. versionadded:: 1.0
    """

    resolve_symlinks: Literal["all", "external", "none", "classic", "error"] | None = (
        dataclasses.field(
            default=None,
            metadata=SettingsFieldMetadata(display_default='"all"'),
        )
    )
    """
    Which symlinks to resolve in the SDist, storing the target's contents instead.

    The modes are:

    * "all": Resolve every symlink, copying its target's contents.
    * "external": Resolve only symlinks that point outside the project (those
      would be broken once the SDist is extracted); store symlinks that stay
      inside the project as-is.
    * "none": Store every symlink as-is, including directory symlinks.
    * "classic": Store file symlinks as-is, but follow directory symlinks,
      copying their contents (scikit-build-core 0.x behavior).
    * "error": Fail the build if any included file or directory is a symlink,
      and list each one with its target. This includes force-include sources
      and the files under them. Exclude a link to allow the build.

    A symlink that can't be resolved (dangling, or a directory symlink loop)
    is stored as a symlink in every mode, with a warning if it was supposed to
    be resolved.

    If you don't set this, it will be "all" unless you set the minimum version
    below 1.0, in which case it will be "classic" to preserve backward
    compatibility.

    .. versionadded:: 1.0
    .. versionchanged:: 1.1
       Added "error".
    """


@dataclasses.dataclass
class WheelSettings:
    packages: list[str] | dict[str, str] | None = dataclasses.field(
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

    An entry may also point at a single module file (e.g. ``hello.py``), which is
    copied in as a top-level module rather than a package directory.

    If a dict, provides a mapping of package name to source directory.

    .. versionchanged:: 1.0
       An entry may point at a single module file.
    """

    py_api: str = ""
    """
    The Python version tag used in the wheel file.

    The default (empty string) will use the default Python version.

    You can also set this to "cp310" to enable the CPython 3.10+ Stable
    ABI / Limited API (only on CPython and if the version is sufficient,
    otherwise this has no effect). For free-threaded Python, you can use
    "cp315t" to enable the free-threaded stable ABI (only on CPython
    free-threaded builds and if the version is sufficient). You can request
    both with "cp315.cp315t". On a free-threaded build this emits a combined
    "cp315-abi3.abi3t" tag: abi3t is a subset of abi3 (PEP 803), so the single
    free-threaded binary also loads under a GIL-enabled CPython 3.15+. On a
    GIL build only abi3 can be produced, so it falls back to "cp315-abi3". The
    combined tag shares one minor version, so the classic abi3 minor must not be
    newer than the free-threaded one (e.g. "cp316.cp315t" is rejected). Or
    you can set it to "py3" or "py2.py3" to ignore Python ABI compatibility.
    The ABI tag is inferred from this tag.

    This value is used to construct ``SKBUILD_SABI_COMPONENT`` CMake variable.

    .. versionchanged:: 1.0
       Added the free-threaded stable ABI ("cp315t") and the combined
       abi3.abi3t tag ("cp315.cp315t").
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

    .. versionchanged:: 1.0
       Added the ``${SKBUILD_<TREE>_DIR}`` prefix for targeting wheel trees.

    .. warning::
       EXPERIMENTAL A leading-slash absolute path (``/platlib``, ``/data``,
       ``/headers``, ``/scripts``, ...) is the deprecated spelling of the
       ``${SKBUILD_<TREE>_DIR}`` form and is one level higher than the platlib root.
    """

    license_files: list[str] | None = None
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

    platlib: bool | None = None
    """
    Target the platlib or the purelib.

    If not set, the default is to target the platlib if :confval:`wheel.cmake` is ``true``,
    and the purelib otherwise.
    """

    exclude: list[str] = dataclasses.field(default_factory=list)
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

    tags: list[str] | None = dataclasses.field(
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

    force_include: dict[str, str] = dataclasses.field(default_factory=dict)
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

    In a redirect-mode editable install, platlib entries are served live from
    their sources through the import redirect instead of being copied:
    importable modules always, data files when they keep their filename and
    sit directly inside a top-level package. Anything else (other wheel trees;
    renamed, top-level, or nested data files) is still copied at install time.

    .. versionadded:: 1.0
    """

    reproducible: bool = False
    """
    Try to build a reproducible wheel.

    Unix and Python 3.10+ recommended.

    When enabled, archive timestamps and file permissions are normalized, and
    ``SOURCE_DATE_EPOCH`` is exported to the CMake build (if not already set) so
    compilers that honor it can produce deterministic output. ``SOURCE_DATE_EPOCH``
    is used for timestamps if set, or a fixed value if not.

    .. versionadded:: 1.0

    .. seealso::
       :confval:`sdist.reproducible`
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
    Select the editable mode to use.
    """

    verbose: bool = True
    """
    Turn on verbose output for the editable mode rebuilds.
    """

    rebuild: bool | None = dataclasses.field(
        default=None, metadata=SettingsFieldMetadata(display_default="false")
    )
    """
    Rebuild the project when the package is imported.

    :confval:`build-dir` must be set, except in ``inplace`` mode (where the source
    directory is the build directory). Defaults to true if
    :confval:`editable.rebuild-dir` is set.

    .. versionchanged:: 1.1
       An explicit false is honored when :confval:`editable.rebuild-dir` is set.
    """

    rebuild_dir: str = ""
    """
    Install editables into this persistent tree instead of the wheel.

    The compiled artifacts are installed here at first build and re-installed
    in place on every rebuild, and the redirect references them by absolute
    path. Setting this turns on rebuild-on-import unless :confval:`editable.rebuild`
    is explicitly false; then use ``module.__loader__.rebuild()`` to refresh the
    tree. Must be an absolute (or source-relative) path that is stable between
    build and run time, and supports the same template substitutions as
    :confval:`build-dir`, plus ``{build_dir}`` for the resolved build directory.
    This relocates only
    the install tree; :confval:`build-dir` is still required and still hosts the
    CMake build that the rebuild re-runs.

    The tree is wiped and recreated on each build, so it must be a fresh or
    scikit-build-core-managed directory -- pointing it at a populated directory
    such as your source tree is refused to avoid deleting those files. A managed
    tree gets a ``CACHEDIR.TAG`` and a ``.gitignore`` so its compiled artifacts
    stay out of backups and version control.

    .. versionadded:: 1.0

    .. versionchanged:: 1.2
       Added the ``{build_dir}`` template key.
    """

    @property
    def rebuild_on_import(self) -> bool:
        """
        True when the finder rebuilds on first import.
        """
        return bool(self.rebuild_dir) if self.rebuild is None else self.rebuild

    @property
    def persistent_install(self) -> bool:
        """
        True when CMake installs into a persistent tree outside the wheel.
        """
        return bool(self.rebuild) or bool(self.rebuild_dir)


@dataclasses.dataclass
class BuildSettings:
    tool_args: list[str] = dataclasses.field(default_factory=list)
    """
    Extra args to pass directly to the builder in the build step.
    """

    targets: list[str] = dataclasses.field(default_factory=list)
    """
    The build targets to use when building the project.

    If not specified or an empty list, the default target is used.
    """

    verbose: bool = False
    """
    Verbose printout when building.

    Equivalent to ``CMAKE_VERBOSE_MAKEFILE``.
    """

    requires: list[str] = dataclasses.field(default_factory=list)
    """
    Additional ``build-system.requires``.

    Intended to be used in combination with ``overrides``.
    """


@dataclasses.dataclass
class InstallSettings:
    components: list[str] = dataclasses.field(default_factory=list)
    """
    The components to install.

    If not specified or an empty list, all default components are installed.
    """

    targets: list[str] = dataclasses.field(default_factory=list)
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

    .. versionadded:: 1.0
    """

    strip: bool | None = dataclasses.field(
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

    template_path: Path | None = None
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
    generate: list[GenerateSettings] = dataclasses.field(default_factory=list)
    messages: MessagesSettings = dataclasses.field(default_factory=MessagesSettings)
    search: SearchSettings = dataclasses.field(default_factory=SearchSettings)

    metadata: dict[str, dict[str, Any]] = dataclasses.field(default_factory=dict)
    """
    List dynamic metadata fields and hook locations in this table.
    """

    env: Annotated[dict[str, EnvValue], "EnvTable"] = dataclasses.field(
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

    .. versionadded:: 1.0
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

    variant: list[str] = dataclasses.field(
        default_factory=list,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 variant properties.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.

    .. versionadded:: 1.0
    """

    variant_name: list[str] = dataclasses.field(
        default_factory=list,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 variant properties used for wheel metadata selection.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.

    .. versionadded:: 1.0
    """

    variant_label: str | None = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 wheel variant label override.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.

    .. versionadded:: 1.0
    """

    null_variant: bool = dataclasses.field(
        default=False,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Experimental PEP 817 null-variant selector.

    This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.

    .. versionadded:: 1.0
    """

    minimum_version: Version | None = dataclasses.field(
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

    fail: bool | None = dataclasses.field(
        default=None,
        metadata=SettingsFieldMetadata(override_only=True),
    )
    """
    Immediately fail the build. This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
    """
