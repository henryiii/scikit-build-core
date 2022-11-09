# scikit-build-core

[![Actions Status][actions-badge]][actions-link]
[![Documentation Status][rtd-badge]][rtd-link]
[![Code style: black][black-badge]][black-link]
[![codecov][codecov-badge]][codecov-link]

<!-- Not implemented yet
[![PyPI version][pypi-version]][pypi-link]
[![Conda-Forge][conda-badge]][conda-link]
[![PyPI platforms][pypi-platforms]][pypi-link]

[![GitHub Discussion][github-discussions-badge]][github-discussions-link]
[![Gitter][gitter-badge]][gitter-link]
-->

**WARNING**: Experimental. All configuration subject to change. Only
`scikit_build_core.build` should be used (setuptools backend is experimental and
likely to move to a separate package).

The following limitations are present compared to classic scikit-build:

- The minimum supported CMake is 3.15
- The minimum supported Python is 3.7

Some of these limitations might be adjusted over time, based on user
requirements & effort / maintainability.

This is very much a WIP, some missing features:

- The extensionlib integration is missing
- No hatchling plugin yet
- The docs are not written
- The logging system isn't ideal yet
- Dedicated entrypoints are planned for projects wanting to support discovery
- No support for other targets besides install
- C++17 is required for the test suite because it's more fun than C++11/14
- No support for caching between builds
- No editable mode support
- No extra wheel directories (like headers) supported yet
- Windows ARM support missing

Features over classic Scikit-build:

- Better warnings and errors
- No warning about unused variables
- Automatically adds Ninja and/or CMake only as required
- No dependency on setuptools, distutils, or wheel in build mode.
- Closer to vanilla setuptools in setuptools mode, doesn't interfere with
  config.
- Powerful config system, including config options support in build mode.
- Automatic inclusion of site-packages in `CMAKE_PREFIX_PATH`
- FindPython is backported if running on CMake < 3.24 (included via hatchling in
  a submodule)
- Limited API / Stable ABI and pythonless tags supported via config option
- No slow generator search, ninja/make or MSVC used by default, respects
  `CMAKE_GENERATOR`

Currently, the recommended interface is the PEP 517 interface. There is also a
setuptools-based interface that is being developed to provide a transition path
for classic scikit-build.

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
cmake_minimum_required(VERSION 3.15...3.24)

project(${SKBUILD_PROJECT_NAME} LANGUAGES C VERSION ${SKBUILD_PROJECT_VERSION})

find_package(Python COMPONENTS Interpreter Development.Module)

Python_add_library(_module MODULE src/module.c WITH_SOABI)
set(Python_SOABI ${SKBUILD_SOABI})  # Required for PyPy support

install(TARGETS _module DESTINATION ${SKBUILD_PROJECT_NAME})
```

Scikit-build-core will backport FindPython from CMake 3.24 to older versions of
Python, and will handle PyPy for you if you are building from PyPy. You will
need to install everything you want into the full final path inside site-modules
(so you will usually prefix everything by the package name).

More examples are in the
[tests/packages](https://github.com/scikit-build/scikit-build-core/tree/main/tests/packages).

## Configuration

Warning: still being developed, some things may change.

All configuration options can be placed in `pyproject.toml`, passed via `-C`
options in `pip` or `build` (warning: pip doesn't support list options), or set
as environment variables. `tool.scikit-build` is used in toml, `skbuild.` for
`-C` options, or `SKBUILD_*` for environment variables. The defaults are listed
below:

```toml
[tool.scikit-build]
# The PEP 517 build hooks will add ninja and/or cmake if the versions on the
# system are not at least these versions.
cmake.minimum-version = "3.15"
ninja.minimum-version = "1.5"

# Fallback on gmake/make if available and ninja is missing (Unix)
ninja.make-fallback = true

# Display logs at or above this level.
logging.level = "WARNING"

# Setting the py_abi to "cp37-abi3" would build ABI3 wheels for Python 3.7+.
# Setting the py_abi to "py3-none" would build wheels that don't depend on
# Python (ctypes, etc).
tags.py-abi = ""

# Setting this to true will expand extra tags (universal2 will add Intel and
# Apple Silicon tags, for pip <21.0.1 compatibility).
tags.extra = false

# Include and exclude patterns, in gitignore syntax. Include overrides exclude.
# Wheels include packages included in the sdist; CMake has the final say.
sdist.include = []
sdist.exclude = []

# Make reproducible SDists (at least with Python 3.9+ and UNIX). Respects
# SOURCE_DATE_EPOCH when true (the default).
sdist.reproducible = true

# The root-level packages to include. Special default: if not given, the package
# is auto-discovered if it's name matches the main name.
wheel.packages = ["src/<package>", "<package>"]
```

Most CMake environment variables should be supported, and `CMAKE_ARGS` can be
used to set extra CMake args. `ARCHFLAGS` is used to specify macOS universal2 or
cross-compiles, just like setuptools.

## Acknowledgements

Support for this work was provided by NSF cooperative agreement [OAC-2209877][].

<!-- prettier-ignore-start -->
[actions-badge]:            https://github.com/scikit-build/scikit-build-core/workflows/CI/badge.svg
[actions-link]:             https://github.com/scikit-build/scikit-build-core/actions
[black-badge]:              https://img.shields.io/badge/code%20style-black-000000.svg
[black-link]:               https://github.com/psf/black
[conda-badge]:              https://img.shields.io/conda/vn/conda-forge/scikit-build-core
[conda-link]:               https://github.com/conda-forge/scikit-build-core-feedstock
[github-discussions-badge]: https://img.shields.io/static/v1?label=Discussions&message=Ask&color=blue&logo=github
[github-discussions-link]:  https://github.com/scikit-build/scikit-build-core/discussions
[gitter-badge]:             https://badges.gitter.im/https://github.com/scikit-build/scikit-build-core/community.svg
[gitter-link]:              https://gitter.im/https://github.com/scikit-build/scikit-build-core/community?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge
[codecov-badge]:            https://codecov.io/gh/scikit-build/scikit-build-core/branch/main/graph/badge.svg?token=ZLbQzIvyG8
[codecov-link]:             https://codecov.io/gh/scikit-build/scikit-build-core
[pypi-link]:                https://pypi.org/project/scikit-build-core/
[pypi-platforms]:           https://img.shields.io/pypi/pyversions/scikit-build-core
[pypi-version]:             https://badge.fury.io/py/scikit-build-core.svg
[rtd-badge]:                https://readthedocs.org/projects/scikit-build-core/badge/?version=latest
[rtd-link]:                 https://scikit-build-core.readthedocs.io/en/latest/?badge=latest
[sk-badge]:                 https://scikit-hep.org/assets/images/Scikit--HEP-Project-blue.svg
[OAC-2209877]:              https://www.nsf.gov/awardsearch/showAward?AWD_ID=2209877&HistoricalAwards=false
<!-- prettier-ignore-end -->
