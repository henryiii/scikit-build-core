# scikit-build-core

[![Documentation Status][rtd-badge]][rtd-link]
[![GitHub Discussion][github-discussions-badge]][github-discussions-link]
[![Discord][discord-badge]][discord-link]

[![Actions Status][actions-badge]][actions-link]
[![codecov][codecov-badge]][codecov-link]

[![PyPI version][pypi-version]][pypi-link]
[![Conda-Forge][conda-badge]][conda-link]
[![PyPI platforms][pypi-platforms]][pypi-link]
[![Downloads][download-badge]][download-link]

> [!NOTE]
>
> We have a public Scikit-build community meeting every month!
> [Join us on Google Meet](https://meet.google.com/hzu-znrd-uef) on the third
> Friday of every month at 12:00 PM EST. We also have a developer's meeting on
> the first Friday of every month at the same time. Our past meeting minutes are
> [available here](https://github.com/orgs/scikit-build/discussions/categories/community-meeting-notes).

<!-- SPHINX-START -->

Scikit-build-core is a build backend for Python that uses CMake to build
extension modules. It has a simple yet powerful static configuration system in
pyproject.toml, and supports almost unlimited flexibility via CMake. It was
initially developed to support the demanding needs of scientific users, but can
build any sort of package that uses CMake.

Scikit-build-core is a ground-up rewrite of the classic Scikit-build. The key
features of scikit-build classic (which is setuptools based) are also present
here:

- Great support for or by most OSs, compilers, IDEs, and libraries
- Support for C++ features and other languages like Fortran
- Support for multithreaded builds
- Simple CMakeFiles.txt instead of up to thousands of lines of fragile
  setuptools/distutils code
- Cross-compile support for Apple Silicon and Windows ARM

Scikit-build-core was built using Python packaging standards developed after
scikit-build (classic) was written. Using it directly provides the following
features over classic Scikit-build:

- Better warnings, errors, and logging
- No warning about unused variables
- Automatically adds Ninja and/or CMake only as required
- No dependency on setuptools, distutils, or wheel
- Powerful config system, including config options support
- Automatic inclusion of site-packages in `CMAKE_PREFIX_PATH`
- FindPython is backported if running on CMake < 3.26.1 (configurable), supports
  PyPY SOABI & Limited API / Stable ABI
- Limited API / Stable ABI and pythonless tags supported via config option
- No slow generator search, ninja/make or MSVC used by default, respects
  `CMAKE_GENERATOR`
- SDists are reproducible by default (UNIX, Python 3.9+, uncompressed comparison
  recommended)
- Support for caching between builds (opt-in by setting `build-dir`)
- Support for writing out to extra wheel folders (scripts, headers, data)
- Support for selecting install components and build targets
- Dedicated entrypoints for module and prefix directories
- Several integrated dynamic metadata plugins (proposing standardized support
  soon)
- Experimental editable mode support, with optional experimental auto rebuilds
  on import and optional in-place mode
- Supports WebAssembly (Emscripten/[Pyodide](https://pyodide.org)).
- Supports [free-threaded Python 3.13](https://py-free-threading.github.io).

The following limitations are present compared to classic scikit-build:

- The minimum supported CMake is 3.15
- The minimum supported Python is 3.8 (3.7+ for 0.10.x and older)

Some known missing features that will be developed soon:

- Wheels are not fully reproducible yet (nor are they in most others systems,
  including setuptools)
- Several editable mode caveats (mentioned in the docs).

Other backends are also planned:

- Setuptools integration highly experimental
- Hatchling plugin highly experimental

The recommended interface is the native pyproject builder. There is also a WIP
setuptools-based interface that is being developed to provide a transition path
for classic scikit-build, and a WIP Hatchling plugin. Both might be moved to
standalone packages in the future.

> [!WARNING]
>
> Only the pyproject-based builder should be used; the setuptools backend is
> experimental and likely to move to a separate package before being declared
> stable, and internal API is still being solidified. A future version of this
> package will support creating new build extensions.

## Example

To use scikit-build-core, add it to your `build-system.requires`, and specify
the `scikit_build_core.build` builder as your `build-system.build-backend`. You
do _not_ need to specify `cmake` or `ninja`; scikit-build-core will require them
automatically if the system versions are not sufficient.

```toml
[build-system]
requires = ["scikit-build-core"]
build-backend = "scikit_build_core.build"

[project]
name = "scikit_build_simplest"
version = "0.0.1"
```

You can (and should) specify the rest of the entries in `project`, but these are
the minimum to get started.

An example `CMakeLists.txt`:

```cmake
cmake_minimum_required(VERSION 3.15...3.30)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)

Python_add_library(_module MODULE src/module.c WITH_SOABI)
install(TARGETS _module DESTINATION ${SKBUILD_PROJECT_NAME})
```

Scikit-build-core will backport FindPython from CMake 3.26.1 to older versions
of Python, and will handle PyPy for you if you are building from PyPy. You will
need to install everything you want into the full final path inside site-modules
(so you will usually prefix everything by the package name).

More examples are in the
[tests/packages](https://github.com/scikit-build/scikit-build-core/tree/main/tests/packages).

## Configuration

All configuration options can be placed in `pyproject.toml`, passed via
`-C`/`--config-setting` in build or `-C`/`--config-settings` in `pip` , or set
as environment variables. `tool.scikit-build` is used in toml, `skbuild.` for
`-C` options, or `SKBUILD_*` for environment variables. The defaults are listed
below:

<!-- [[[cog
from scikit_build_core.settings.skbuild_docs import mk_skbuild_docs

print("\n```toml\n[tool.scikit-build]")
print(mk_skbuild_docs())
print("```\n")
]]] -->

```toml
[tool.scikit-build]
# The versions of CMake to allow. If CMake is not present on the system or does
# not pass this specifier, it will be downloaded via PyPI if possible. An empty
# string will disable this check. The default on 0.10+ is "CMakeLists.txt",
# which will read it from the project's CMakeLists.txt file, or ">=3.15" if
# unreadable or <0.10.
cmake.version = ""

# A list of args to pass to CMake when configuring the project. Setting this in
# config or envvar will override toml. See also ``cmake.define``.
cmake.args = []

# A table of defines to pass to CMake when configuring the project. Additive.
cmake.define = {}

# DEPRECATED in 0.10, use build.verbose instead.
cmake.verbose = ""

# The build type to use when building the project. Valid options are: "Debug",
# "Release", "RelWithDebInfo", "MinSizeRel", "", etc.
cmake.build-type = "Release"

# The source directory to use when building the project. Currently only affects
# the native builder (not the setuptools plugin).
cmake.source-dir = "."

# DEPRECATED in 0.10; use build.targets instead.
cmake.targets = ""

# Configure preset to use. ``cmake.source-dir`` must still be appropriately
# defined and it must contain a ``CMake(User)Presets.json``. The preset's
# ``binaryDir`` is ignored and is always overwritten by the ``build-dir``
# defined by scikit-build-core. ``cmake.define``, generator values are still
# passed if defined and take precedence over preset's value according to CMake
# logic.
cmake.preset = ""

# The versions of Ninja to allow. If Ninja is not present on the system or does
# not pass this specifier, it will be downloaded via PyPI if possible. An empty
# string will disable this check.
ninja.version = ">=1.5"

# If Ninja is not present on the system or is older than required, it will be
# downloaded via PyPI if this is false.
ninja.make-fallback = true

# The logging level to display, "DEBUG", "INFO", "WARNING", and "ERROR" are
# possible options.
logging.level = "WARNING"

# Files to include in the SDist even if they are skipped by default. Supports
# gitignore syntax.
sdist.include = []

# Files to exclude from the SDist even if they are included by default. Supports
# gitignore syntax.
sdist.exclude = []

# If set to True, try to build a reproducible distribution (Unix and Python 3.9+
# recommended).  ``SOURCE_DATE_EPOCH`` will be used for timestamps, or a fixed
# value if not set.
sdist.reproducible = true

# If set to True, CMake will be run before building the SDist.
sdist.cmake = false

# A list of packages to auto-copy into the wheel. If this is not set, it will
# default to the first of ``src/<package>``, ``python/<package>``, or
# ``<package>`` if they exist.  The prefix(s) will be stripped from the package
# name inside the wheel. If a dict, provides a mapping of package name to source
# directory.
wheel.packages = ["src/<package>", "python/<package>", "<package>"]

# The Python tags. The default (empty string) will use the default Python
# version. You can also set this to "cp38" to enable the CPython 3.8+ Stable ABI
# / Limited API (only on CPython and if the version is sufficient, otherwise
# this has no effect). Or you can set it to "py3" or "py2.py3" to ignore Python
# ABI compatibility. The ABI tag is inferred from this tag.
wheel.py-api = ""

# Fill out extra tags that are not required. This adds "x86_64" and "arm64" to
# the list of platforms when "universal2" is used, which helps older Pip's
# (before 21.0.1) find the correct wheel.
wheel.expand-macos-universal-tags = false

# The install directory for the wheel. This is relative to the platlib root. You
# might set this to the package name. The original dir is still at
# SKBUILD_PLATLIB_DIR (also SKBUILD_DATA_DIR, etc. are available). EXPERIMENTAL:
# An absolute path will be one level higher than the platlib root, giving access
# to "/platlib", "/data", "/headers", and "/scripts".
wheel.install-dir = ""

# A list of license files to include in the wheel. Supports glob patterns. The
# default is ``["LICEN[CS]E*", "COPYING*", "NOTICE*", "AUTHORS*"]``. Must not be
# set if ``project.license-files`` is set.
wheel.license-files = ""

# If set to True (the default), CMake will be run before building the wheel.
wheel.cmake = true

# Target the platlib or the purelib. If not set, the default is to target the
# platlib if wheel.cmake is true, and the purelib otherwise.
wheel.platlib = ""

# A set of patterns to exclude from the wheel. This is additive to the SDist
# exclude patterns. This applies to the final paths in the wheel, and can
# exclude files from CMake output as well.  Editable installs may not respect
# this exclusion.
wheel.exclude = []

# The build tag to use for the wheel. If empty, no build tag is used.
wheel.build-tag = ""

# If CMake is less than this value, backport a copy of FindPython. Set to 0
# disable this, or the empty string.
backport.find-python = "3.26.1"

# Select the editable mode to use. Can be "redirect" (default) or "inplace".
editable.mode = "redirect"

# Turn on verbose output for the editable mode rebuilds.
editable.verbose = true

# Rebuild the project when the package is imported. The build-directory must be
# set.
editable.rebuild = false

# Extra args to pass directly to the builder in the build step.
build.tool-args = []

# The build targets to use when building the project. Empty builds the default
# target.
build.targets = []

# Verbose printout when building.
build.verbose = false

# Additional ``build-system.requires``. Intended to be used in combination with
# ``overrides``.
build.requires = []

# The components to install. If empty, all default components are installed.
install.components = []

# Whether to strip the binaries. True for release builds on scikit-build-core
# 0.5+ (0.5-0.10.5 also incorrectly set this for debug builds).
install.strip = true

# The path (relative to platlib) for the file to generate.
generate[].path = ""

# The template to use for the file. This includes string.Template style
# placeholders for all the metadata. If empty, a template-path must be set.
generate[].template = ""

# The path to the template file. If empty, a template must be set.
generate[].template-path = ""

# The place to put the generated file. The "build" directory is useful for CMake
# files, and the "install" directory is useful for Python files, usually. You
# can also write directly to the "source" directory, will overwrite existing
# files & remember to gitignore the file.
generate[].location = "install"

# A message to print after a build failure.
messages.after-failure = ""

# A message to print after a successful build.
messages.after-success = ""

# List dynamic metadata fields and hook locations in this table.
metadata = {}

# Strictly check all config options. If False, warnings will be printed for
# unknown options. If True, an error will be raised.
strict-config = true

# Enable early previews of features not finalized yet.
experimental = false

# If set, this will provide a method for backward compatibility.
minimum-version = "0.10"  # current version

# The build directory. Defaults to a temporary directory, but can be set.
build-dir = ""

# Immediately fail the build. This is only useful in overrides.
fail = false

```

<!-- [[[end]]] -->

Most CMake environment variables should be supported, and `CMAKE_ARGS` can be
used to set extra CMake args. `ARCHFLAGS` is used to specify macOS universal2 or
cross-compiles, just like setuptools.

You can also specify `[[tool.scikit-build.overrides]]` to customize values for
different systems. See the docs for details.

## Other projects for building

Scikit-build-core is a binary build backend. There are also other binary build
backends:

- [py-build-cmake][]: A different attempt at a standards compliant builder for
  CMake. Strong focus on cross-compilation. Uses Flit internals.
- [cmeel][]: A different attempt at a standards compliant builder for CMake.
  Focus on building an ecosystem around a special unimportable folder in
  site-packages (similar to scikit-build's usage of `cmake.*` entrypoints, but
  folder-based).
- [meson-python][]: A meson-based build backend; has some maintainer overlap
  with scikit-build-core.
- [maturin][]: A build backend for Rust projects, using Cargo.
- [enscons][]: A SCons based backend, not very actively developed (but it
  predates all the others in modern standard support!)

If you don't need a binary build, you don't need to use a binary build backend!
There are some very good Python build backends; we recommend [hatchling][] as a
good balance between good defaults for beginners and good support for advanced
use cases. This is the tool scikit-build-core itself uses.

## Acknowledgements

Support for this work was provided by NSF grant [OAC-2209877][]. Any opinions,
findings, and conclusions or recommendations expressed in this material are
those of the author(s) and do not necessarily reflect the views of the National
Science Foundation.

<!-- prettier-ignore-start -->
[OAC-2209877]:              https://www.nsf.gov/awardsearch/showAward?AWD_ID=2209877&HistoricalAwards=false
[actions-badge]:            https://github.com/scikit-build/scikit-build-core/workflows/CI/badge.svg
[actions-link]:             https://github.com/scikit-build/scikit-build-core/actions
[cmeel]:                    https://github.com/cmake-wheel/cmeel
[codecov-badge]:            https://codecov.io/gh/scikit-build/scikit-build-core/branch/main/graph/badge.svg?token=ZLbQzIvyG8
[codecov-link]:             https://codecov.io/gh/scikit-build/scikit-build-core
[conda-badge]:              https://img.shields.io/conda/vn/conda-forge/scikit-build-core
[conda-link]:               https://github.com/conda-forge/scikit-build-core-feedstock
[discord-badge]:            https://img.shields.io/discord/803025117553754132?label=Discord%20chat%20%23scikit-build
[discord-link]:             https://discord.gg/pypa
[download-badge]:           https://static.pepy.tech/badge/scikit-build-core/month
[download-link]:            https://pepy.tech/project/scikit-build-core
[enscons]:                  https://pypi.org/project/enscons
[github-discussions-badge]: https://img.shields.io/static/v1?label=Discussions&message=Ask&color=blue&logo=github
[github-discussions-link]:  https://github.com/orgs/scikit-build/discussions
[hatchling]:                https://hatch.pypa.io/latest
[maturin]:                  https://www.maturin.rs
[meson-python]:             https://meson-python.readthedocs.io
[py-build-cmake]:           https://tttapa.github.io/py-build-cmake
[pypi-link]:                https://pypi.org/project/scikit-build-core/
[pypi-platforms]:           https://img.shields.io/pypi/pyversions/scikit-build-core
[pypi-version]:             https://badge.fury.io/py/scikit-build-core.svg
[rtd-badge]:                https://readthedocs.org/projects/scikit-build-core/badge/?version=latest
[rtd-link]:                 https://scikit-build-core.readthedocs.io/en/latest/?badge=latest
<!-- prettier-ignore-end -->
