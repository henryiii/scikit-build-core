# Testing a project with a branch / main

If you are testing a downstream project, you can use a branch of
scikit-build-core like this:

```toml
[build-system]
requires = ["scikit-build-core @ git+https://github.com/scikit-build/scikit-build-core@main"]
build-backend = "scikit_build_core.build"
```

Or you can build your project from the scikit-build-core source with nox:

```bash
nox -s downstream -- https://github.com/...
```

# Setting up for development

See the [Scientific-Python Development Guide][skdev] for a detailed description
of best practices for developing packages.

[skdev]: https://learn.scientific-python.org/development

## Quick development

The fastest way to start with development is to use nox. If you don't have nox,
you can use `pipx run nox` to run it without installing, or `pipx install nox`.
If you don't have pipx (pip for applications), then you can install with with
`pip install pipx` (the only case were installing an application with regular
pip is reasonable). If you use macOS, then pipx and nox are both in brew, use
`brew install pipx nox`.

To use, run `nox`. This will lint and test using every installed version of
Python on your system, skipping ones that are not installed. You can also run
specific jobs:

```console
$ nox -s lint  # Lint only
$ nox -s tests-3.10  # Python 3.10 tests only
$ nox -s docs -- serve  # Build and serve the docs
$ nox -s build  # Make an SDist and wheel
```

Nox handles everything for you, including setting up an temporary virtual
environment for each run.

## Setting up a development environment manually

You can set up a development environment by running:

```bash
python3 -m venv .venv
source ./.venv/bin/activate
pip install -v -e .[dev]
```

If you have the
[Python Launcher for Unix](https://github.com/brettcannon/python-launcher), you
can instead do:

```bash
py -m venv .venv
py -m install -v -e .[dev]
```

## Post setup

You should prepare pre-commit, which will help you by checking that commits pass
required checks:

```bash
pip install pre-commit # or brew install pre-commit on macOS
pre-commit install # Will install a pre-commit hook into the git repo
```

You can also/alternatively run `pre-commit run` (changes only) or
`pre-commit run --all-files` to check even without installing the hook.

## Testing

Use pytest to run the unit checks:

```bash
pytest
```

## Quick local running

You can use this to build and use this with an isolated environment:

```bash
pipx run build --wheel
PIP_FIND_LINKS="dist" pipx run build --wheel tests/packages/simple_pyproject_ext -o dist
```

## Building docs

You can build the docs using:

```bash
nox -s docs
```

You can see a preview with:

```bash
nox -s docs -- serve
```

## Pre-commit

This project uses pre-commit for all style checking. While you can run it with
nox, this is such an important tool that it deserves to be installed on its own.
Install pre-commit and run:

```bash
pre-commit run -a
```

to check all files.

# Design info

This section covers the design of scikit-build-core.

Included modules:

- `.cmake`: `CMake`/`CMaker` general interface for building code
- `.fileapi`: Interface for reading the CMake File API
- `.builder`: Generalized backend builder and related helpers
- `.settings`: The configuration system, reading from pyproject.toml, PEP 517

The build backend and plugins:

- `.build`: PEP 517 builder
- `.setuptools`: The setuptools Extension interface (and PEP 517 hooks) (will
  likely be split out)
- `.setuptools.build_api`: Wrapper injecting build requirements
- `.hatch`: The hatchling extension (will likely be split out) config, and
  envvars

## Basic CMake usage

```python
from packaging.specifiers import SpecifierSet
from scikit_build_core.cmake import CMake, CMaker

cmake = CMake.default_search(version=SpecifierSet(">=3.15"))
config = CMaker(
    cmake,
    source_dir=source_dir,
    build_dir=build_dir,
    build_type="Release",
)
config.configure()
config.build()
config.install(prefix)
```

## File API

If you want to access the File API, use:

```python
from scikit_build_core.fileapi.query import stateless_query
from scikit_build_core.fileapi.reply import load_reply_dir

reply_dir = stateless_query(config.build_dir)
config.configure()
index = load_reply_dir(reply_dir)
```

This mostly wraps the FileAPI in classes. It autoloads some jsonFiles. This
throws an `ExceptionGroup` if parsing files. It is currently experimental.

## Configuration

Configuration support uses plain dataclasses:

```python
@dataclasses.dataclass
class NestedSettings:
    one: str


@dataclasses.dataclass
class SettingChecker:
    nested: NestedSettings
```

You can use different sources, currently environment variables:

```yaml
PREFIX_NESTED_ONE: "envvar"
```

PEP 517 config dictionaries:

```python
{"nested.one": "PEP 517 config"}
```

And TOML:

```toml
[tool.scikit-build]
nested.one = "TOML config"
```

The CMake config is pre-configured and available in `.settings.cmake_model`,
usable as:

```python
from scikit_build_core.settings.skbuild_settings import SettingsReader

settings_reader = SettingsReader.from_file("pyproject.toml", config_settings)
setting = settings_reader.settings
assert str(settings.cmake.version) == ">=3.15"
assert str(settings.ninja.version) == ">=1.5"
```

## Builders

The tools in `builder` are designed to make writing a builder easy. The
`Builder` class is used in the various builder implementations.

### PEP 517 builder

This is highly experimental, and currently only uses `.gitignore` to filter the
SDist, and the wheel only contains the install directory - control using CMake.

```toml
[build-system]
requires = [
    "scikit_build_core",
    "pybind11",
]
build-backend = "scikit_build_core.build"

[project]
name = "cmake_example"
version = "0.0.1"
requires-python = ">=3.10"

[project.optional-dependencies]
test = ["pytest>=6.0"]
```

```cmake
cmake_minimum_required(VERSION 3.15...4.4)
project("${SKBUILD_PROJECT_NAME}" LANGUAGES CXX VERSION "${SKBUILD_PROJECT_VERSION}")

find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(cmake_example src/main.cpp)

target_compile_definitions(cmake_example
                           PRIVATE VERSION_INFO=${PROJECT_VERSION})

install(TARGETS cmake_example DESTINATION .)
```

### Setuptools builder

Experimental. Supports only a single module, may not support extra Python files.

`setup.py`:

```python
from setuptools import setup

setup(
    name="cmake_example",
    version="0.0.1",
    cmake_source_dir=".",
    zip_safe=False,
    extras_require={"test": ["pytest>=6.0"]},
    python_requires=">=3.10",
)
```

`pyproject.toml`:

```toml
[build-system]
requires = [
    "scikit_build_core",
    "pybind11",
]
build-backend = "scikit_build_core.setuptools.build_meta"
```

```cmake
cmake_minimum_required(VERSION 3.15...4.4)
project("${SKBUILD_PROJECT_NAME}" LANGUAGES CXX VERSION "${SKBUILD_PROJECT_VERSION}")

find_package(pybind11 CONFIG REQUIRED)
pybind11_add_module(cmake_example src/main.cpp)

target_compile_definitions(cmake_example
                           PRIVATE VERSION_INFO=${PROJECT_VERSION})

install(TARGETS cmake_example DESTINATION .)
```

## Patterns

### Backports

All backported standard library code is in `scikit_build_core._compat`, in a
module with the stdlib name. Ruff will ensure you use the backport instead of
the original module.

### Detecting the platform

Here are some common platforms and the reported values:

| OS      | Compiler   | `sys.platform` | `sysconfig.get_platform()`   |
| ------- | ---------- | -------------- | ---------------------------- |
| Windows | MSVC       | `win32`        | `win-amd64`                  |
| Windows | MinGW      | `win32`        | `mingw_x86_64`               |
| Windows | MinGW URCT | `win32`        | `mingw_x86_64_ucrt`          |
| Windows | Cygwin     | `cygwin`       | `cygwin-3.4.6-x86_64`        |
| macOS   | Clang      | `darwin`       | `macosx-10.15-x86_64`        |
| Linux   | GCC        | `linux`        | `linux-x86_64`               |
| Pyodide | Clang      | `emscripten`   | `emscripten-3.1.32-wasm32`   |
| FreeBSD | GCC        | `freebsd13`    | `freebsd-13.2-RELEASE-amd64` |

# Downstream packaging

## Fedora packaging

We are using [`packit`](https://packit.dev/) to keep maintain the
[Fedora package](https://src.fedoraproject.org/rpms/python-scikit-build-core/).
There are two `packit` jobs one needs to keep in mind here:

- `copr_build`: Submits copr builds to:
  - `@scikit-build/nightly` if there is a commit to `main`. This is intended for
    users to test the current development build
  - `@scikit-build/scikit-build-core` if there is a PR request. This is for CI
    purposes to confirm that the build is successful
  - `@scikit-build/release` whenever a new release is published on GitHub. Users
    can use this to get the latest release before they land on Fedora. This is
    also used for other copr projects to check the future release
- `propose_downstream`: Submits a PR to `src.fedoraproject.org` once a release
  is published

To interact with `packit`, you can use
[`/packit command`](https://packit.dev/docs/guide/#how-to-re-trigger-packit-actions-in-your-pull-request)
in PRs and commit messages or [`packit` CLI](https://packit.dev/docs/cli/).
These interactions are primarily intended for controlling the CI managed on
`scikit-build`.

To debug and build locally or on your own copr project you may use
`packit build` commands, e.g. to build locally using `mock` for fedora rawhide:

```console
$ packit build in-mock -r /etc/mock/fedora-rawhide-x86_64.cfg
```

or for copr project `copr_user/scikit-build-core`:

```console
$ copr-cli edit-permissions --builder=packit copr_user/scikit-build-core
$ packit build in-copr --owner copr_user --project scikit-build-core
```

(Here we are making sure `packit` has the appropriate permission for
`copr_user/scikit-build-core` via the `copr-cli` command. You may need to
configure [`~/.config/copr`](https://packit.dev/docs/cli/build/copr/)) first

Both of these methods automatically edit the `Version` in the
[spec file](../.dist/scikit-build-core.spec), therefore it is intentionally
marked as `0.0.0` there to avoid manually updating. Make sure to not push these
changes in a PR.
