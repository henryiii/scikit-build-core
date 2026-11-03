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
> [Join us on Google Meet](https://meet.google.com/tgz-umhu-onf) on the third
> Friday of every month at [12:00 PM ET][]. Some of our past meeting minutes are
> [available here](https://github.com/orgs/scikit-build/discussions/categories/community-meeting-notes).

<!-- prettier-ignore-start -->
[12:00 PM ET]: https://howlonghowmany.com/my-time/eastern-time/12-pm
<!-- prettier-ignore-end -->

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
- Simple CMakeLists.txt files instead of up to thousands of lines of fragile
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
  PyPy SOABI & Limited API / Stable ABI
- Limited API / Stable ABI and pythonless tags supported via config option
- No slow generator search, ninja/make or MSVC used by default, respects
  `CMAKE_GENERATOR`
- SDists are reproducible by default (UNIX, Python 3.10+, uncompressed
  comparison recommended), and wheels can be made reproducible too (opt-in)
- Support for caching between builds (opt-in by setting `build-dir`)
- Support for writing out to extra wheel folders (scripts, headers, data)
- Support for selecting install components and build targets
- Dedicated entrypoints for module and prefix directories
- Several integrated dynamic metadata plugins, supporting the cross-backend
  `[[tool.dynamic-metadata]]` standard
- Editable mode support, with optional experimental auto rebuilds on import and
  optional in-place mode
- Supports WebAssembly (Emscripten/[Pyodide](https://pyodide.org)).
- Supports [free-threaded Python 3.13+](https://py-free-threading.github.io),
  including the free-threaded stable ABI (PEP 803).
- A `scikit-build` CLI, including `scikit-build init` to scaffold a new project.

Current requirements:

- The minimum supported CMake is 3.15
- The minimum supported Python is 3.10 (3.9+ for 1.1.x, 3.8+ for 1.0.x and
  older)

The recommended interface is the native pyproject builder. Other backends are
also available:

- Setuptools integration (use the `[setuptools]` extra)
- Hatchling plugin (use the `[hatchling]` extra)

> [!WARNING]
>
> The setuptools and hatchling backends might move to standalone packages in the
> future, so depend on them via the `scikit-build-core[setuptools]` and
> `scikit-build-core[hatchling]` extras to stay protected if they do.

## Example

The fastest way to start a new project is `scikit-build init` (available via
`uvx scikit-build-core init` as well), which generates a minimal CMake +
scikit-build-core starter project. The pieces are described below.

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
cmake_minimum_required(VERSION 3.15...4.4)
project(scikit_build_simplest LANGUAGES C)

find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)

Python_add_library(_module MODULE src/module.c WITH_SOABI)
install(TARGETS _module DESTINATION scikit_build_simplest)
```

The `install(DESTINATION ...)` is relative to site-packages, so the `_module`
extension above lands at `scikit_build_simplest/_module.*` when the package is
`pip install`ed. Scikit-build-core will backport FindPython from CMake 3.26.1 to
older versions of Python, and will handle PyPy for you if you are building from
PyPy. You will need to install everything you want into the full final path
inside site-packages (so you will usually prefix everything by the package name)
-- including any `__init__.py`, which CMake can place alongside the extension
with `install(FILES src/__init__.py DESTINATION scikit_build_simplest)`.

The most important optional configuration is this:

```toml
[build-system]
requires = ["scikit-build-core>=1.0"]
build-backend = "scikit_build_core.build"

[tool.scikit-build]
minimum-version = "build-system.requires"
```

This will enable scikit-build-core to read your minimum requirement on itself
and stay in compatibility mode for that version; if we make changes to defaults
in the future, your package will continue to build exactly the same.

The [Getting started guide][getting-started] walks through a complete package
step by step. More examples are in the
[tests/packages](https://github.com/scikit-build/scikit-build-core/tree/main/tests/packages).

## Configuration

All configuration options can be placed in `pyproject.toml`, passed via `-C` in
pip, uv, and build, or set as environment variables. `tool.scikit-build` is used
in toml, `skbuild.` for `-C` options, or `SKBUILD_*` for environment variables.

For a full reference and explanation of the variables see the [online
documentation][conf-ref]

A quick summary and some defaults are listed below:

<!-- prettier-ignore-start -->
<!-- [[[cog
from scikit_build_core.settings.skbuild_docs_readme import mk_skbuild_docs

print()
print(mk_skbuild_docs())
print()
]]] -->

### Top-level

| Option | Default | Description |
| - | - | - |
| `metadata` | `{}` | List dynamic metadata fields and hook locations in this table. |
| `env` | `{}` | A table of environment variables to set for the CMake subprocesses. |
| `strict-config` | `true` | Strictly check all config options. |
| `experimental` | `false` | Enable early previews of features not finalized yet. |
| `minimum-version` | `"1.1"` (current version) | If set, this will provide a method for backward compatibility. |
| `build-dir` | `""` | The CMake build directory. Defaults to a unique temporary directory. |

### `cmake`

| Option | Default | Description |
| - | - | - |
| `cmake.version` | `""` | The versions of CMake to allow as a python-compatible specifier. |
| `cmake.args` | `[]` | A list of args to pass to CMake when configuring the project. |
| `cmake.define` | `{}` | A table of defines to pass to CMake when configuring the project. Additive. |
| `cmake.build-type` | `"Release"` | The build type to use when building the project. |
| `cmake.source-dir` | `"."` | The source directory to use when building the project. |
| `cmake.fresh` | `false` | Discard any cached CMake configuration and configure from scratch, like ``cmake --fresh``. |
| `cmake.python-hints` | `true` | Do not pass the current environment's python hints such as ``Python_EXECUTABLE``. |

### `ninja`

| Option | Default | Description |
| - | - | - |
| `ninja.version` | `">=1.5"` | The versions of Ninja to allow. |
| `ninja.make-fallback` | `true` | Use Make as a fallback if a suitable Ninja executable is not found. |

### `logging`

| Option | Default | Description |
| - | - | - |
| `logging.level` | `"WARNING"` | The logging level to display. (choices: `NOTSET`, `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`) |

### `sdist`

| Option | Default | Description |
| - | - | - |
| `sdist.include` | `[]` | Files to include in the SDist even if they are skipped by default. Supports gitignore syntax. |
| `sdist.exclude` | `[]` | Files to exclude from the SDist even if they are included by default. Supports gitignore syntax. |
| `sdist.inclusion-mode` | `"default"` ("classic") | Method to use to compute the files to include and exclude. (choices: `classic`, `default`, `manual`, `explicit`) |
| `sdist.reproducible` | `true` | Try to build a reproducible distribution. |
| `sdist.cmake` | `false` | If set to True, CMake will be run before building the SDist. |
| `sdist.force-include` | `{}` | Force-include files into the SDist. |
| `sdist.resolve-symlinks` | `"all"` | Which symlinks to resolve in the SDist, storing the target's contents instead. (choices: `all`, `external`, `none`, `classic`, `error`) |

### `wheel`

| Option | Default | Description |
| - | - | - |
| `wheel.packages` | `["src/<package>", "python/<package>", "<package>"]` | A list of packages to auto-copy into the wheel. |
| `wheel.py-api` | `""` | The Python version tag used in the wheel file. |
| `wheel.expand-macos-universal-tags` | `false` | Fill out extra tags that are not required. |
| `wheel.install-dir` | `""` | The CMake install prefix relative to the platlib wheel path. |
| `wheel.license-files` | `""` | A list of license files to include in the wheel. Supports glob patterns. |
| `wheel.cmake` | `true` | Run CMake as part of building the wheel. |
| `wheel.platlib` | `""` | Target the platlib or the purelib. |
| `wheel.exclude` | `[]` | A set of patterns to exclude from the wheel. |
| `wheel.build-tag` | `""` | The build tag to use for the wheel. If empty, no build tag is used. |
| `wheel.force-include` | `{}` | Force-include files into the wheel. |
| `wheel.reproducible` | `false` | Try to build a reproducible wheel. |

### `backport`

| Option | Default | Description |
| - | - | - |
| `backport.find-python` | `"3.26.1"` | If CMake is less than this value, backport a copy of FindPython. |

### `editable`

| Option | Default | Description |
| - | - | - |
| `editable.mode` | `"redirect"` | Select the editable mode to use. (choices: `redirect`, `inplace`) |
| `editable.verbose` | `true` | Turn on verbose output for the editable mode rebuilds. |
| `editable.rebuild` | `false` | Rebuild the project when the package is imported. |
| `editable.rebuild-dir` | `""` | Install editables into this persistent tree instead of the wheel. |

### `build`

| Option | Default | Description |
| - | - | - |
| `build.tool-args` | `[]` | Extra args to pass directly to the builder in the build step. |
| `build.targets` | `[]` | The build targets to use when building the project. |
| `build.verbose` | `false` | Verbose printout when building. |
| `build.requires` | `[]` | Additional ``build-system.requires``. |

### `install`

| Option | Default | Description |
| - | - | - |
| `install.components` | `[]` | The components to install. |
| `install.targets` | `[]` | Build targets to run during the install step via ``cmake --build --target``. |
| `install.strip` | `true` | Whether to strip the binaries. |

### `generate[]`

| Option | Default | Description |
| - | - | - |
| `generate[].path` | `""` | The path (relative to platlib) for the file to generate. |
| `generate[].template` | `""` | The template string to use for the file. |
| `generate[].template-path` | `""` | The path to the template file. If empty, a template must be set. |
| `generate[].location` | `"install"` | The place to put the generated file. (choices: `install`, `build`, `source`) |

### `messages`

| Option | Default | Description |
| - | - | - |
| `messages.after-failure` | `""` | A message to print after a build failure. |
| `messages.after-success` | `""` | A message to print after a successful build. |

### `search`

| Option | Default | Description |
| - | - | - |
| `search.site-packages` | `true` | Add the python build environment site_packages folder to the CMake prefix paths. |

<!-- [[[end]]] -->
<!-- prettier-ignore-end -->

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
[OAC-2209877]:              https://www.nsf.gov/awardsearch/show-award/?AWD_ID=2209877&HistoricalAwards=false
[actions-badge]:            https://github.com/scikit-build/scikit-build-core/actions/workflows/ci.yml/badge.svg
[actions-link]:             https://github.com/scikit-build/scikit-build-core/actions
[cmeel]:                    https://github.com/cmake-wheel/cmeel
[codecov-badge]:            https://codecov.io/gh/scikit-build/scikit-build-core/branch/main/graph/badge.svg?token=ZLbQzIvyG8
[codecov-link]:             https://codecov.io/gh/scikit-build/scikit-build-core
[conda-badge]:              https://img.shields.io/conda/vn/conda-forge/scikit-build-core
[conda-link]:               https://github.com/conda-forge/scikit-build-core-feedstock
[conf-ref]:                 https://scikit-build-core.readthedocs.io/en/latest/reference/configs.html
[discord-badge]:            https://img.shields.io/discord/803025117553754132?label=Discord%20chat%20%23scikit-build
[discord-link]:             https://discord.gg/pypa
[download-badge]:           https://static.pepy.tech/badge/scikit-build-core/month
[download-link]:            https://pepy.tech/project/scikit-build-core
[enscons]:                  https://pypi.org/project/enscons
[getting-started]:          https://scikit-build-core.readthedocs.io/en/latest/guide/getting_started.html
[github-discussions-badge]: https://img.shields.io/static/v1?label=Discussions&message=Ask&color=blue&logo=github
[github-discussions-link]:  https://github.com/orgs/scikit-build/discussions
[hatchling]:                https://hatch.pypa.io/latest
[maturin]:                  https://www.maturin.rs
[meson-python]:             https://mesonbuild.com/meson-python
[py-build-cmake]:           https://tttapa.github.io/py-build-cmake
[pypi-link]:                https://pypi.org/project/scikit-build-core/
[pypi-platforms]:           https://img.shields.io/pypi/pyversions/scikit-build-core
[pypi-version]:             https://badge.fury.io/py/scikit-build-core.svg
[rtd-badge]:                https://readthedocs.org/projects/scikit-build-core/badge/?version=latest
[rtd-link]:                 https://scikit-build-core.readthedocs.io/en/latest/?badge=latest
<!-- prettier-ignore-end -->
