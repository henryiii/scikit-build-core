# Config Reference

The following are the available configurations in `pyproject.toml` for the
`[tool.scikit-build]` table. These can be passed in one of the following ways:

````{tab} pyproject.toml

```toml
[tool.scikit-build]
build.verbose = true
```

````

`````{tab} config-settings

````{tab} pip

```console
$ pip install . --config-settings=build.verbose=true
```

````

````{tab} build

```console
$ pipx run build --wheel -Cbuild.verbose=true
```

````

````{tab} cibuildwheel

```toml
[tool.cibuildwheel.config-settings]
"build.verbose" = true
```

````

`````

````{tab} Environment

```console
$ export SKBUILD_BUILD_VERBOSE="true"
```

````

<!-- [[[cog
from scikit_build_core.settings.skbuild_docs_sphinx import mk_skbuild_docs

print()
print(mk_skbuild_docs())
]]] -->

## (top-level)

```{eval-rst}
.. confval:: build-dir

  :Type: ``str``
  :Config-settings: ``build-dir`` or ``skbuild.build-dir``
  :Environment variable: ``SKBUILD_BUILD_DIR``

  The CMake build directory. Defaults to a unique temporary directory.

  This can be set to reuse the build directory from previous runs.
```

```{eval-rst}
.. confval:: env

  :Type: ``dict[str,EnvValue]``
  :Config-settings: ``env`` or ``skbuild.env``
  :Environment variable: ``SKBUILD_ENV``

  A table of environment variables to set for the CMake subprocesses.

  Applied to the configure, build, and install steps. A variable is only set if
  not already present (like a ``setdefault``); pass ``force = true`` to
  overwrite. Each value is a literal string or a table with ``env`` (read from
  another environment variable), ``default``, and ``force``; an entry that
  resolves to nothing is skipped. Independent of the ``if.env`` override
  condition.
```

```{eval-rst}
.. confval:: experimental

  :Type: ``bool``
  :Default: false
  :Config-settings: ``experimental`` or ``skbuild.experimental``
  :Environment variable: ``SKBUILD_EXPERIMENTAL``

  Enable early previews of features not finalized yet.
```

```{eval-rst}
.. confval:: fail

  :Type: ``bool``
  :Config-settings: ``fail`` or ``skbuild.fail``
  :Environment variable: ``SKBUILD_FAIL``

  Immediately fail the build. This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
```

```{eval-rst}
.. confval:: metadata

  :Type: ``dict[str,dict[str,Any]]``

  List dynamic metadata fields and hook locations in this table.
```

```{eval-rst}
.. confval:: minimum-version

  :Type: ``Version``
  :Default: "0.12"  # current version
  :Config-settings: ``minimum-version`` or ``skbuild.minimum-version``
  :Environment variable: ``SKBUILD_MINIMUM_VERSION``

  If set, this will provide a method for backward compatibility.
```

```{eval-rst}
.. confval:: null-variant

  :Type: ``bool``
  :Default: false
  :Config-settings: ``null-variant`` or ``skbuild.null-variant``
  :Environment variable: ``SKBUILD_NULL_VARIANT``

  Experimental PEP 817 null-variant selector.

  This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
```

```{eval-rst}
.. confval:: strict-config

  :Type: ``bool``
  :Default: true
  :Config-settings: ``strict-config`` or ``skbuild.strict-config``
  :Environment variable: ``SKBUILD_STRICT_CONFIG``

  Strictly check all config options.

  If False, warnings will be printed for unknown options.

  If True, an error will be raised.
```

```{eval-rst}
.. confval:: variant

  :Type: ``list[str]``
  :Config-settings: ``variant`` or ``skbuild.variant``
  :Environment variable: ``SKBUILD_VARIANT``

  Experimental PEP 817 variant properties.

  This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
```

```{eval-rst}
.. confval:: variant-label

  :Type: ``str``
  :Config-settings: ``variant-label`` or ``skbuild.variant-label``
  :Environment variable: ``SKBUILD_VARIANT_LABEL``

  Experimental PEP 817 wheel variant label override.

  This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
```

```{eval-rst}
.. confval:: variant-name

  :Type: ``list[str]``
  :Config-settings: ``variant-name`` or ``skbuild.variant-name``
  :Environment variable: ``SKBUILD_VARIANT_NAME``

  Experimental PEP 817 variant properties used for wheel metadata selection.

  This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
```

## backport

```{eval-rst}
.. confval:: backport.find-python

  :Type: ``Version``
  :Default: "3.26.1"
  :Config-settings: ``backport.find-python`` or ``skbuild.backport.find-python``
  :Environment variable: ``SKBUILD_BACKPORT_FIND_PYTHON``

  If CMake is less than this value, backport a copy of FindPython.

  Set to ``0`` or an empty string to disable this.
```

## build

```{eval-rst}
.. confval:: build.requires

  :Type: ``list[str]``
  :Config-settings: ``build.requires`` or ``skbuild.build.requires``
  :Environment variable: ``SKBUILD_BUILD_REQUIRES``

  Additional ``build-system.requires``.

  Intended to be used in combination with ``overrides``.
```

```{eval-rst}
.. confval:: build.targets

  :Type: ``list[str]``
  :Config-settings: ``build.targets`` or ``skbuild.build.targets``
  :Environment variable: ``SKBUILD_BUILD_TARGETS``

  The build targets to use when building the project.

  If not specified or an empty list, the default target is used.
```

```{eval-rst}
.. confval:: build.tool-args

  :Type: ``list[str]``
  :Config-settings: ``build.tool-args`` or ``skbuild.build.tool-args``
  :Environment variable: ``SKBUILD_BUILD_TOOL_ARGS``

  Extra args to pass directly to the builder in the build step.
```

```{eval-rst}
.. confval:: build.verbose

  :Type: ``bool``
  :Default: false
  :Config-settings: ``build.verbose`` or ``skbuild.build.verbose``
  :Environment variable: ``SKBUILD_BUILD_VERBOSE``

  Verbose printout when building.

  Equivalent to ``CMAKE_VERBOSE_MAKEFILE``.
```

## cmake

```{eval-rst}
.. confval:: cmake.args

  :Type: ``list[str]``
  :Config-settings: ``cmake.args`` or ``skbuild.cmake.args``
  :Environment variable: ``SKBUILD_CMAKE_ARGS``

  A list of args to pass to CMake when configuring the project.

  Setting this in config or envvar will override toml.

  .. seealso::
     :confval:`cmake.define`
```

```{eval-rst}
.. confval:: cmake.build-type

  :Type: ``str | list[str]``
  :Default: "Release"
  :Config-settings: ``cmake.build-type`` or ``skbuild.cmake.build-type``
  :Environment variable: ``SKBUILD_CMAKE_BUILD_TYPE``

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
```

```{eval-rst}
.. confval:: cmake.define

  :Type: ``dict[str,CMakeSettingsDefine]``
  :Config-settings: ``cmake.define`` or ``skbuild.cmake.define``
  :Environment variable: ``SKBUILD_CMAKE_DEFINE``

  A table of defines to pass to CMake when configuring the project. Additive.
```

```{eval-rst}
.. confval:: cmake.minimum-version

  :Type: ``Version``
  :Config-settings: ``cmake.minimum-version`` or ``skbuild.cmake.minimum-version``
  :Environment variable: ``SKBUILD_CMAKE_MINIMUM_VERSION``

  DEPRECATED in 0.8; use version instead.
```

```{eval-rst}
.. confval:: cmake.python-hints

  :Type: ``bool``
  :Default: true
  :Config-settings: ``cmake.python-hints`` or ``skbuild.cmake.python-hints``
  :Environment variable: ``SKBUILD_CMAKE_PYTHON_HINTS``

  Do not pass the current environment's python hints such as ``Python_EXECUTABLE``.
  Primarily used for cross-compilation where the CMAKE_TOOLCHAIN_FILE should handle it
  instead.
```

```{eval-rst}
.. confval:: cmake.source-dir

  :Type: ``Path``
  :Default: "."
  :Config-settings: ``cmake.source-dir`` or ``skbuild.cmake.source-dir``
  :Environment variable: ``SKBUILD_CMAKE_SOURCE_DIR``

  The source directory to use when building the project.

  Currently only affects the native builder (not the setuptools plugin).
```

```{eval-rst}
.. confval:: cmake.targets

  :Type: ``list[str]``
  :Config-settings: ``cmake.targets`` or ``skbuild.cmake.targets``
  :Environment variable: ``SKBUILD_CMAKE_TARGETS``

  DEPRECATED in 0.10; use build.targets instead.
```

```{eval-rst}
.. confval:: cmake.toolchain-file

  :Type: ``Path``
  :Config-settings: ``cmake.toolchain-file`` or ``skbuild.cmake.toolchain-file``
  :Environment variable: ``SKBUILD_CMAKE_TOOLCHAIN_FILE``

  The CMAKE_TOOLCHAIN_FILE / --toolchain used for cross-compilation.

  This cannot be set in the static ``[tool.scikit-build]`` table; use it in an override, config-settings, or an environment variable.
```

```{eval-rst}
.. confval:: cmake.verbose

  :Type: ``bool``
  :Config-settings: ``cmake.verbose`` or ``skbuild.cmake.verbose``
  :Environment variable: ``SKBUILD_CMAKE_VERBOSE``

  DEPRECATED in 0.10, use build.verbose instead.
```

```{eval-rst}
.. confval:: cmake.version

  :Type: ``SpecifierSet``
  :Config-settings: ``cmake.version`` or ``skbuild.cmake.version``
  :Environment variable: ``SKBUILD_CMAKE_VERSION``

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
```

## editable

```{eval-rst}
.. confval:: editable.mode

  :Type: ``"redirect" | "inplace"``
  :Default: "redirect"
  :Config-settings: ``editable.mode`` or ``skbuild.editable.mode``
  :Environment variable: ``SKBUILD_EDITABLE_MODE``

  Select the editable mode to use. Can be "redirect" (default) or "inplace".
```

```{eval-rst}
.. confval:: editable.rebuild

  :Type: ``bool``
  :Default: false
  :Config-settings: ``editable.rebuild`` or ``skbuild.editable.rebuild``
  :Environment variable: ``SKBUILD_EDITABLE_REBUILD``

  Rebuild the project when the package is imported.

  :confval:`build-dir` must be set.
```

```{eval-rst}
.. confval:: editable.verbose

  :Type: ``bool``
  :Default: true
  :Config-settings: ``editable.verbose`` or ``skbuild.editable.verbose``
  :Environment variable: ``SKBUILD_EDITABLE_VERBOSE``

  Turn on verbose output for the editable mode rebuilds.
```

## generate[]

```{eval-rst}
.. confval:: generate[].location

  :Type: ``"install" | "build" | "source"``
  :Default: "install"

  The place to put the generated file.

  The ``build`` directory is useful for CMake files, and the ``install`` directory is
  useful for Python files, usually. You can also write directly to the ``source``
  directory, will overwrite existing files & remember to gitignore the file.
```

```{eval-rst}
.. confval:: generate[].path

  :Type: ``Path``

  The path (relative to platlib) for the file to generate.
```

```{eval-rst}
.. confval:: generate[].template

  :Type: ``str``

  The template string to use for the file.

  Template style placeholders are available for all the metadata.

  Either this or :confval:`generate[].template-path` must be set.

  .. seealso::
     :confval:`generate[].template-path`
```

```{eval-rst}
.. confval:: generate[].template-path

  :Type: ``Path``

  The path to the template file. If empty, a template must be set.

  Either this or :confval:`generate[].template` must be set.

  .. seealso::
     :confval:`generate[].template`
```

## install

```{eval-rst}
.. confval:: install.components

  :Type: ``list[str]``
  :Config-settings: ``install.components`` or ``skbuild.install.components``
  :Environment variable: ``SKBUILD_INSTALL_COMPONENTS``

  The components to install.

  If not specified or an empty list, all default components are installed.
```

```{eval-rst}
.. confval:: install.strip

  :Type: ``bool``
  :Default: true
  :Config-settings: ``install.strip`` or ``skbuild.install.strip``
  :Environment variable: ``SKBUILD_INSTALL_STRIP``

  Whether to strip the binaries.

  Equivalent to ``--strip`` in ``cmake install``.

  True for release builds (`Release` or `MinSizeRel`) on scikit-build-core 0.5+.

  .. note::
     0.5-0.10.5 also incorrectly set this for debug builds.
```

```{eval-rst}
.. confval:: install.targets

  :Type: ``list[str]``
  :Config-settings: ``install.targets`` or ``skbuild.install.targets``
  :Environment variable: ``SKBUILD_INSTALL_TARGETS``

  Build targets to run during the install step via ``cmake --build --target``.

  This is intended for projects that group their install rules under an
  umbrella "distribution" build target (such as LLVM's ``install-distribution``)
  rather than using CMake install ``COMPONENT``\ s. Each listed target is built,
  which triggers its install rules into the staging prefix.

  This relies on the configure-time ``CMAKE_INSTALL_PREFIX`` (set automatically
  by scikit-build-core to the wheel staging directory); the ``--strip`` and
  ``--component`` options of ``cmake --install`` do not apply to these targets.
  ``components`` and ``targets`` may be combined; both will run.
```

## logging

```{eval-rst}
.. confval:: logging.level

  :Type: ``"NOTSET" | "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"``
  :Default: "WARNING"
  :Config-settings: ``logging.level`` or ``skbuild.logging.level``
  :Environment variable: ``SKBUILD_LOGGING_LEVEL``

  The logging level to display.
```

## messages

```{eval-rst}
.. confval:: messages.after-failure

  :Type: ``str``
  :Config-settings: ``messages.after-failure`` or ``skbuild.messages.after-failure``
  :Environment variable: ``SKBUILD_MESSAGES_AFTER_FAILURE``

  A message to print after a build failure.
```

```{eval-rst}
.. confval:: messages.after-success

  :Type: ``str``
  :Config-settings: ``messages.after-success`` or ``skbuild.messages.after-success``
  :Environment variable: ``SKBUILD_MESSAGES_AFTER_SUCCESS``

  A message to print after a successful build.
```

## ninja

```{eval-rst}
.. confval:: ninja.make-fallback

  :Type: ``bool``
  :Default: true
  :Config-settings: ``ninja.make-fallback`` or ``skbuild.ninja.make-fallback``
  :Environment variable: ``SKBUILD_NINJA_MAKE_FALLBACK``

  Use Make as a fallback if a suitable Ninja executable is not found.

  If Make is also not available on the system, a ninja dependency is added to the
  ``build-system.requires`` according to :confval:`ninja.version`.

  .. seealso::
     :confval:`ninja.version`
```

```{eval-rst}
.. confval:: ninja.minimum-version

  :Type: ``Version``
  :Config-settings: ``ninja.minimum-version`` or ``skbuild.ninja.minimum-version``
  :Environment variable: ``SKBUILD_NINJA_MINIMUM_VERSION``

  DEPRECATED in 0.8; use version instead.
```

```{eval-rst}
.. confval:: ninja.version

  :Type: ``SpecifierSet``
  :Default: ">=1.5"
  :Config-settings: ``ninja.version`` or ``skbuild.ninja.version``
  :Environment variable: ``SKBUILD_NINJA_VERSION``

  The versions of Ninja to allow.

  If Ninja is not present on the system or does not pass this specifier, it will
  be downloaded via PyPI if possible with the equivalent specifier used.

  An empty string will disable this check.

  .. seealso::
     - :confval:`cmake.version`
     - :confval:`ninja.make-fallback`
```

## sdist

```{eval-rst}
.. confval:: sdist.cmake

  :Type: ``bool``
  :Default: false
  :Config-settings: ``sdist.cmake`` or ``skbuild.sdist.cmake``
  :Environment variable: ``SKBUILD_SDIST_CMAKE``

  Run CMake before building the SDist.

  By default this is a configure-only run, for projects that need a configure
  artifact (e.g. a FetchContent-populated source tree) vendored into the SDist.
  Set :confval:`sdist.install-dir` as well to instead run a full configure +
  build + install and vendor the install tree, so a build from the unpacked
  SDist can repackage it with ``wheel.cmake = false`` and no CMake.
```

```{eval-rst}
.. confval:: sdist.exclude

  :Type: ``list[str]``
  :Config-settings: ``sdist.exclude`` or ``skbuild.sdist.exclude``
  :Environment variable: ``SKBUILD_SDIST_EXCLUDE``

  Files to exclude from the SDist even if they are included by default. Supports gitignore syntax.

  .. seealso::
     :confval:`sdist.include`
```

```{eval-rst}
.. confval:: sdist.force-include

  :Type: ``dict[str,str]``
  :Config-settings: ``sdist.force-include`` or ``skbuild.sdist.force-include``
  :Environment variable: ``SKBUILD_SDIST_FORCE_INCLUDE``

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
```

```{eval-rst}
.. confval:: sdist.include

  :Type: ``list[str]``
  :Config-settings: ``sdist.include`` or ``skbuild.sdist.include``
  :Environment variable: ``SKBUILD_SDIST_INCLUDE``

  Files to include in the SDist even if they are skipped by default. Supports gitignore syntax.

  Always takes precedence over :confval:`sdist.exclude`

  .. seealso::
     :confval:`sdist.exclude`
```

```{eval-rst}
.. confval:: sdist.inclusion-mode

  :Type: ``"classic" | "default" | "manual" | "explicit"``
  :Default: "default"  # "classic"
  :Config-settings: ``sdist.inclusion-mode`` or ``skbuild.sdist.inclusion-mode``
  :Environment variable: ``SKBUILD_SDIST_INCLUSION_MODE``

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
```

```{eval-rst}
.. confval:: sdist.install-dir

  :Type: ``str``
  :Config-settings: ``sdist.install-dir`` or ``skbuild.sdist.install-dir``
  :Environment variable: ``SKBUILD_SDIST_INSTALL_DIR``

  SDist-relative directory to vendor the CMake install tree into.

  When set (and :confval:`sdist.cmake` is true), the SDist build runs a full
  configure + build + install and writes the staged wheel trees here, one
  subdirectory per tree (``platlib``/``purelib``, ``data``, ``headers``,
  ``scripts``, ``metadata``). A wheel built from the unpacked SDist then
  restages those trees automatically with no CMake (pure/``purelib`` wheels
  only); set ``wheel.cmake`` explicitly to opt out. See the docs for the
  compiled-wheel ``wheel.force-include`` recipe.
```

```{eval-rst}
.. confval:: sdist.reproducible

  :Type: ``bool``
  :Default: true
  :Config-settings: ``sdist.reproducible`` or ``skbuild.sdist.reproducible``
  :Environment variable: ``SKBUILD_SDIST_REPRODUCIBLE``

  Try to build a reproducible distribution.

  Unix and Python 3.9+ recommended.

  ``SOURCE_DATE_EPOCH`` will be used for timestamps, or a fixed value if not set.
```

```{eval-rst}
.. confval:: sdist.resolve-symlinks

  :Type: ``"all" | "none"``
  :Default: "all"
  :Config-settings: ``sdist.resolve-symlinks`` or ``skbuild.sdist.resolve-symlinks``
  :Environment variable: ``SKBUILD_SDIST_RESOLVE_SYMLINKS``

  Which symlinks to resolve in the SDist, storing the target's contents instead.

  The modes are:

  * "all": Resolve every symlink, copying its target's contents.
  * "none": Store symlinks as-is.

  If you don't set this, it will be "all" unless you set the minimum version
  below 1.0, in which case it will be "none" to preserve backward compatibility.

  .. versionadded: 1.0
```

## search

```{eval-rst}
.. confval:: search.site-packages

  :Type: ``bool``
  :Default: true
  :Config-settings: ``search.site-packages`` or ``skbuild.search.site-packages``
  :Environment variable: ``SKBUILD_SEARCH_SITE_PACKAGES``

  Add the python build environment site_packages folder to the CMake prefix paths.
```

## wheel

```{eval-rst}
.. confval:: wheel.build-tag

  :Type: ``str``
  :Config-settings: ``wheel.build-tag`` or ``skbuild.wheel.build-tag``
  :Environment variable: ``SKBUILD_WHEEL_BUILD_TAG``

  The build tag to use for the wheel. If empty, no build tag is used.
```

```{eval-rst}
.. confval:: wheel.cmake

  :Type: ``bool``
  :Default: true
  :Config-settings: ``wheel.cmake`` or ``skbuild.wheel.cmake``
  :Environment variable: ``SKBUILD_WHEEL_CMAKE``

  Run CMake as part of building the wheel.
```

```{eval-rst}
.. confval:: wheel.exclude

  :Type: ``list[str]``
  :Config-settings: ``wheel.exclude`` or ``skbuild.wheel.exclude``
  :Environment variable: ``SKBUILD_WHEEL_EXCLUDE``

  A set of patterns to exclude from the wheel.

  This is additive to the SDist exclude patterns. This applies to the final paths
  in the wheel, and can exclude files from CMake output as well.  Editable installs
  may not respect this exclusion.
```

```{eval-rst}
.. confval:: wheel.expand-macos-universal-tags

  :Type: ``bool``
  :Default: false
  :Config-settings: ``wheel.expand-macos-universal-tags`` or ``skbuild.wheel.expand-macos-universal-tags``
  :Environment variable: ``SKBUILD_WHEEL_EXPAND_MACOS_UNIVERSAL_TAGS``

  Fill out extra tags that are not required.

  This adds "x86_64" and "arm64" to the list of platforms when "universal2" is used,
  which helps older Pip's (before 21.0.1) find the correct wheel.
```

```{eval-rst}
.. confval:: wheel.force-include

  :Type: ``dict[str,str]``
  :Config-settings: ``wheel.force-include`` or ``skbuild.wheel.force-include``
  :Environment variable: ``SKBUILD_WHEEL_FORCE_INCLUDE``

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
```

```{eval-rst}
.. confval:: wheel.install-dir

  :Type: ``str``
  :Config-settings: ``wheel.install-dir`` or ``skbuild.wheel.install-dir``
  :Environment variable: ``SKBUILD_WHEEL_INSTALL_DIR``

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
```

```{eval-rst}
.. confval:: wheel.license-files

  :Type: ``list[str]``
  :Config-settings: ``wheel.license-files`` or ``skbuild.wheel.license-files``
  :Environment variable: ``SKBUILD_WHEEL_LICENSE_FILES``

  A list of license files to include in the wheel. Supports glob patterns.

  The default is ``["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]``.

  .. warning::
     Must not be set if ``project.license-files`` is set.
```

```{eval-rst}
.. confval:: wheel.packages

  :Type: ``list[str]``
  :Default: ["src/<package>", "python/<package>", "<package>"]
  :Config-settings: ``wheel.packages`` or ``skbuild.wheel.packages``
  :Environment variable: ``SKBUILD_WHEEL_PACKAGES``

  A list of packages to auto-copy into the wheel.

  If this is not set, it will default to the first of ``src/<package>``, ``python/<package>``, or
  ``<package>`` if they exist.  The prefix(s) will be stripped from the
  package name inside the wheel.

  If a dict, provides a mapping of package name to source directory.
```

```{eval-rst}
.. confval:: wheel.platlib

  :Type: ``bool``
  :Config-settings: ``wheel.platlib`` or ``skbuild.wheel.platlib``
  :Environment variable: ``SKBUILD_WHEEL_PLATLIB``

  Target the platlib or the purelib.

  If not set, the default is to target the platlib if :confval:`wheel.cmake` is ``true``,
  and the purelib otherwise.
```

```{eval-rst}
.. confval:: wheel.py-api

  :Type: ``str``
  :Config-settings: ``wheel.py-api`` or ``skbuild.wheel.py-api``
  :Environment variable: ``SKBUILD_WHEEL_PY_API``

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
```

```{eval-rst}
.. confval:: wheel.tags

  :Type: ``list[str]``
  :Config-settings: ``wheel.tags`` or ``skbuild.wheel.tags``
  :Environment variable: ``SKBUILD_WHEEL_TAGS``

  Wheel tags to manually force, {interpreter}-{abi}-{platform} format.

  Manually specify the wheel tags to use, ignoring other inputs such as
  ``wheel.py-api``. Each tag must be of the format
  {interpreter}-{abi}-{platform}.  If not specified, these tags are
  automatically calculated. This cannot be set in the static
  ``[tool.scikit-build]`` table; use it in an override, config-settings, or an
  environment variable.
```

<!-- [[[end]]] -->
