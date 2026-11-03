# Configuration

Scikit-build-core supports a powerful unified configuration system. Every option
in scikit-build-core can be specified in one of three ways: as a
`pyproject.toml` option (preferred if static), as a config-settings options
(preferred if dynamic), or as an environment variable. Note that config-settings
options can optionally be prefixed with `skbuild.`, for example
`-C skbuild.logging.level=INFO`.

(verbosity)=

## Verbosity

By default, the CMake configuration output is always shown, but it may be hidden
behind the build frontend setting, e.g. `pip` requires including `-v` argument
in order to display any output.

You can increase the verbosity of the build with two settings - `build.verbose`
is a shortcut for verbose build output (i.e. `cmake --build ... -v`), and
`logging.level` controls scikit-build-core's internal logging. An example (with
all configuration styles) of setting both is:

````{tab} pyproject.toml

```toml
[tool.scikit-build]
build.verbose = true
logging.level = "INFO"
```

````

`````{tab} config-settings


````{tab} uv

```console
$ uv pip install . -v -Cbuild.verbose=true -Clogging.level=INFO
```

````

````{tab} pip

```console
$ pip install . -v -Cbuild.verbose=true -Clogging.level=INFO
```

````

````{tab} build

```console
$ pipx run build --wheel -Cbuild.verbose=true -Clogging.level=INFO
```

````

````{tab} cibuildwheel

```toml
[tool.cibuildwheel.config-settings]
"build.verbose" = true
"logging.level" = "INFO"
```

````

`````

````{tab} Environment


```yaml
SKBUILD_BUILD_VERBOSE: true
SKBUILD_LOGGING_LEVEL: "INFO"
```


````

:::{warning}

In general, the environment variable method is intended as an emergency
workaround for legacy tooling.

:::

:::{versionchanged} 0.10

`cmake.verbose` was renamed to `build.verbose`.

:::

## Minimum version & defaults

Scikit-build-core, like CMake, has a special minimum required version setting.
If you set this, you get two benefits. First, if the version is less than this
version, you get a nice error message. But, more importantly, if
scikit-build-core is a newer version than the version set here, it will select
older defaults to help ensure your package can continue to build, even if a
default value changes in the future. This should help reduce the chance of ever
needed an upper cap on the scikit-build-core version, as upper caps are
discouraged.

It is recommended you set this value as high as you feel comfortable with, and
probably keep in sync with your build-system requirements.

```toml
[tool.scikit-build]
minimum-version = "0.12"
```

In your `pyproject.toml`, you can specify the special string
`"build-system.requires"`, which will read the minimum version from your
build-system requirements directly; you must specify a minimum there to use this
automatic feature.

```toml
[build-system]
requires = ["scikit-build-core>=0.12"]

[tool.scikit-build]
minimum-version = "build-system.requires"
```

:::{versionchanged} 0.10

The `"build-system.requires"` option was added.

:::

:::{warning}

The following behaviors are affected by `minimum-version`:

- `minimum-version` 0.5+ (or unset) strips binaries by default.
- `minimum-version` 0.8+ (or unset) `cmake.minimum-version` and
  `ninja.minimum-version` are replaced with `cmake.version` and `ninja.version`.
- `minimum-version` 0.10+ (or unset) `cmake.targets` and `cmake.verbose` are
  replaced with `build.targets` and `build.verbose`. The CMake minimum version
  will be detected if not given.
- `minimum-version` 0.12+ (or unset) uses `"default"` instead of `"classic"` as
  the default for `sdist.inclusion-mode`.
- `minimum-version` 1.0+ (or unset) deprecates the `tool.scikit-build.metadata`
  table in favor of the standard top-level `[[tool.dynamic-metadata]]`; see
  [](./dynamic.md).

:::

:::{versionchanged} 0.12.2

Non-normalized SDist names used to be enabled when set to below 0.5. This is no
longer supported on PyPI, so this back-compat feature was removed.

:::

## CMake and Ninja minimum versions

You can select a different minimum version for CMake and Ninja.
Scikit-build-core will automatically decide to download a wheel for these (if
possible) when the system version is less than this value.

For example, to require a recent CMake and Ninja:

```toml
[tool.scikit-build]
cmake.version = ">=3.26.1"
ninja.version = ">=1.11"
```

You can try to read the version from your CMakeLists.txt with the special string
`"CMakeLists.txt"`. This is an error if the minimum version was not statically
detectable in the file. If your `minimum-version` setting is unset or set to
"0.10" or higher, scikit-build-core will still try to read this if possible, and
will fall back on ">=3.15" if it can't read it.

You can also enforce ninja to be required even if make is present on Unix:

```toml
[tool.scikit-build]
ninja.make-fallback = false
```

You can also control the FindPython backport; by default, a backport of CMake
3.26.1's FindPython will be used if the CMake version is less than 3.26.1; you
can turn this down if you'd like ("3.15", scikit-build-core's minimum supported
CMake version, would turn it off).

```toml
[tool.scikit-build]
backport.find-python = "3.15"
```

```{versionadded} 0.8
These used to be called `cmake.minimum-version` and `ninja.minimum-version`, and
only took a single value. Now they are full specifier sets, allowing for more
complex version requirements, like `>=3.15,!=3.18.0`.
```

## Configuring source file inclusion

Scikit-build-core defaults to using your `.gitignore` to select what to exclude
from the source distribution. Like git, ignore rules stop at a submodule: a
directory with a `.git` entry, or a path listed in a `.gitmodules` file, reads
only its own ignore files. You can list files to explicitly include and exclude
if you want:

```toml
[tool.scikit-build]
sdist.include = ["src/some_generated_file.txt"]
sdist.exclude = [".github"]
```

You can select a couple of alternative modes, as well. If you want to manually
control this, without reading `.gitignore`, use:

```toml
[tool.scikit-build]
sdist.inclusion-mode = "manual"
```

There's also a `"classic"` mode, which fully traverses all directories to check
rules (this was the default before scikit-build-core 0.12).

By default, scikit-build-core will respect `SOURCE_DATE_EPOCH`, and will lock
the modification time to a reproducible value if it's not set. You can disable
reproducible builds if you prefer, however:

```toml
[tool.scikit-build]
sdist.reproducible = false
```

You can also request CMake to run during this step:

```toml
[tool.scikit-build]
sdist.cmake = true
```

:::{note}

If you do this, you'll want to have some artifact from the configure in your
source directory; for example:

```cmake
include(FetchContent)

set(PYBIND11_FINDPYTHON ON)

if(NOT SKBUILD_STATE STREQUAL "sdist"
   AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/pybind11/CMakeLists.txt")
  message(STATUS "Using integrated pybind11")
  add_subdirectory(pybind11)
else()
  FetchContent_Declare(
    pybind11
    GIT_REPOSITORY https://github.com/pybind/pybind11.git
    GIT_TAG v2.12.0
    SOURCE_DIR ${CMAKE_CURRENT_SOURCE_DIR}/pybind11)
  FetchContent_MakeAvailable(pybind11)
endif()
```

The `/pybind11` directory is in the `.gitignore` and important parts are in
`sdist.include`:

```toml
[tool.scikit-build]
sdist.cmake = true
sdist.include = [
  "pybind11/tools",
  "pybind11/include",
  "pybind11/CMakeLists.txt",
]
```

:::

## Customizing the built wheel

The wheel will automatically look for Python packages at `src/<package_name>`,
`python/<package_name>`, and `<package_name>`, in that order, where
`<package_name>` is your project's name. If you want to list packages
explicitly, you can. The final path element is the package.

```toml
[tool.scikit-build]
wheel.packages = ["python/src/mypackage"]
```

Each entry names a single top-level package directory, and the final path
element becomes the importable package name. This is **not** a search directory
like setuptools' `tool.setuptools.packages.find.where`: subpackages and data
files inside a listed package are copied in automatically (recursively), so you
never list subpackages. To ship two separate top-level packages, list both:

```toml
[tool.scikit-build]
wheel.packages = ["src/pkg_a", "src/pkg_b"]
```

Auto-detection only looks for a package matching your project name at the three
locations above; if you have multiple top-level packages, or your package lives
elsewhere, you must list them explicitly.

This can also be a table, allowing full customization of where a source package
maps to a wheel directory. The final components of both paths must match due to
the way editable installs work. The equivalent of the above is:

```toml
[tool.scikit-build.wheel.packages]
mypackage = "python/src/mypackage"
```

But you can also do more complex moves:

```toml
[tool.scikit-build.wheel.packages]
"mypackage/subpackage" = "python/src/subpackage"
```

:::{versionadded} 0.10

Support for the table form.

:::

You can disable Python file inclusion entirely, and rely only on CMake's install
mechanism:

```toml
[tool.scikit-build]
wheel.packages = []
```

The install directory is normally site-packages; however, you can manually set
that to a different directory if you'd like to avoid changing your CMake files.
For example, to mimic scikit-build classic:

```toml
[tool.scikit-build]
wheel.install-dir = "mypackage"
```

You can target a different wheel tree by prefixing the install dir with the
matching `SKBUILD_*_DIR` CMake variable name:

```toml
[tool.scikit-build]
wheel.install-dir = "${SKBUILD_DATA_DIR}/mypackage"
```

The available trees match the `SKBUILD_*_DIR` cache variables available from
within CMake, described in
[install directories](../guide/cmakelists.md#install-directories).

:::{versionadded} 1.0

Targeting other wheel trees with the `${SKBUILD_<TREE>_DIR}` prefix.

:::

:::{warning}

When passing this through PEP 517 `config-settings` on a command line, quote it
so the shell does not expand `${SKBUILD_DATA_DIR}` as an environment variable
(e.g. `-C 'wheel.install-dir=${SKBUILD_DATA_DIR}/mypackage'`).

The older leading-slash spelling (`/data`, `/scripts`, ...) selects the same
trees but is gated behind `experimental = true`, and deprecated.

:::

By default, any `LICEN[CS]E*`, `COPYING*`, `NOTICE*`, or `AUTHORS*` file in the
root of the build directory will be picked up. You can specify an exact list of
files if you prefer, or if your license file is in a different directory.
Globbing patterns are supported.

```toml
[tool.scikit-build]
wheel.license-files = ["LICENSE"]
```

You can exclude files from the built wheel (on top of the `sdist.exclude` list)
as well (not guaranteed to be respected by editable installs):

```toml
[tool.scikit-build]
wheel.exclude = ["**.pyx"]
```

:::{versionchanged} 0.9

Previously these were matched on the source path, rather than the wheel path,
and didn't apply to CMake output.

:::

:::{note}

There are two more settings that are primarily intended for `overrides` (see
below). `wheel.cmake` defaults to `true`, and this enables/disables building
with CMake. It also changes the default of `wheel.platlib` unless it's set
explicitly; CMake builds assume `wheel.platlib = true`, and CMake-less builds
assume `wheel.platlib = false` (purelib targeted instead).

:::

## Customizing the output wheel

The python API tags for your wheel will be correct assuming you are building a
normal CPython extension. For anything else, set `wheel.py-api` to the tag you
support:

```toml
[tool.scikit-build]
wheel.py-api = "cp310"
```

| `wheel.py-api`   | Use for                                            | Resulting tags     |
| ---------------- | -------------------------------------------------- | ------------------ |
| `"cp310"`        | Limited API / Stable ABI extension (CPython 3.10+) | `cp310-abi3`       |
| `"py3"`          | Extension not using the Python API                 | `py3-none`         |
| `"py2.py3"`      | Same, but installable on Python 2 as well          | `py2.py3-none`     |
| `"cp315t"`       | Free-threaded stable ABI ([PEP 803][])             | `cp315-abi3t`      |
| `"cp315.cp315t"` | Both stable ABIs from one free-threaded build      | `cp315-abi3.abi3t` |

Scikit-build-core will only target ABI3 if the version of Python is equal to or
newer than the one you set. `cp315t` also sets `Py_TARGET_ABI3T` (if using CMake
4.4+). For `py3`/`py2.py3`, you still need a version of Python scikit-build-core
supports to build the initial wheel. The `${SKBUILD_SABI_COMPONENT}` variable
and the `USE_SABI` idiom on the CMake side is covered in
[Limited API / Stable ABI](#limited-api).

With `cp315.cp315t`, a free-threaded build emits the combined `cp315-abi3.abi3t`
tag: `abi3t` is a subset of `abi3` (PEP 803), so the single free-threaded binary
also loads under a GIL-enabled CPython 3.15+, and the one wheel is installable
on every CPython 3.15+. On a GIL build only `abi3` can be produced, so it falls
back to `cp315-abi3`.

:::{versionadded} 1.0

The free-threaded stable ABI (`cp315t`, [PEP 803][]) and the combined
`cp315.cp315t` tag.

:::

Some older versions of pip are unable to load standard universal tags;
scikit-build-core can expand the macOS universal tags for you for maximum
historic compatibility if you'd like:

```toml
[tool.scikit-build]
wheel.expand-macos-universal-tags = true
```

You can also specify a build tag:

```{conftabs} wheel.build-tag 1

```

You can select only specific components to install:

```toml
[tool.scikit-build]
install.components = ["python"]
```

And you can turn off binary stripping:

```{conftabs} install.strip False

```

You can opt in to reproducible wheels (unlike SDists, this is off by default).
When enabled, archive timestamps and file permissions are normalized, and
`SOURCE_DATE_EPOCH` is exported to the CMake build (if not already set) so
compilers that honor it can produce deterministic output. This cannot make the
compiled binaries themselves reproducible on its own; that also depends on a
recent compiler and flags like `-ffile-prefix-map`.

```toml
[tool.scikit-build]
wheel.reproducible = true
```

:::{versionadded} 1.0

:::

## Force-including files

:::{versionadded} 1.0

:::

Sometimes you need to place a specific file (or directory) at a specific path in
a distribution, even if it lives outside your package tree or is produced
elsewhere. Each distribution has its own `force-include` table mapping source
paths to destinations:

```toml
[tool.scikit-build.sdist.force-include]
"../shared/data.json" = "mypackage/data.json"

[tool.scikit-build.wheel.force-include]
"vendor/lib.so" = "mypackage/_lib.so"
"tools/run.sh"  = "${SKBUILD_SCRIPTS_DIR}/run.sh"
```

The keys are source paths relative to the project root; they may point outside
it (e.g. `../shared`) or be absolute, and `~` is expanded. A source may be a
file or a directory, and directories are copied recursively (skipping VCS and
`__pycache__` junk). A missing source is an error.

`sdist.force-include` destinations are relative to the SDist root.
`wheel.force-include` destinations are relative to the platlib (the package
area), and also accept a `${SKBUILD_<TREE>_DIR}` prefix to target a different
wheel tree, exactly as with [`wheel.install-dir`](#customizing-the-built-wheel)
above. Force-included wheel files are placed last, so they override discovered
package files and CMake output at the same destination.

A force-included _file_ also overrides the matching exclude list
(`wheel.exclude` for wheels, `sdist.exclude` for SDists): naming an exact source
is an explicit request, so it wins even if an exclude pattern matches its
destination. A force-included _directory_ stays subject to that exclude, so a
bulk tree copy can still be trimmed by an exclude pattern (e.g. force-include a
directory and exclude `**/*.bzl` to drop the Bazel files from it).

In an editable install using redirect mode (the default), platlib entries are
served live from their sources through the import redirect instead of being
copied, so edits to a force-included file take effect without reinstalling. This
covers importable modules (even renamed ones) and data files that keep their
filename and sit directly inside a top-level package. Anything the redirect
cannot express, like other wheel trees like `${SKBUILD_SCRIPTS_DIR}`, renamed or
top-level data files, and data files nested below a package subdirectory (kept
as real files so package-root resource lookups keep the wheel layout), are still
copied at install time, so those snapshots only refresh on reinstall.

### Building a wheel from an SDist

A common pattern vendors an external (`../`) source into the SDist and then
ships that output in the wheel. Reference the SDist destination as the wheel
source and it works in both build modes:

```toml
[tool.scikit-build.sdist.force-include]
"../shared/data.json" = "mypackage/data.json"   # vendor it into the SDist

[tool.scikit-build.wheel.force-include]
"mypackage/data.json" = "mypackage/data.json"    # ship the SDist output
```

When the wheel is built from the unpacked SDist, `mypackage/data.json` exists
and is used directly. When it is built from the source tree (or an editable
install) the file was never materialized; a `wheel.force-include` source missing
on disk is then resolved through `sdist.force-include` (by exact destination, or
under a force-included directory) and read from that original source instead. An
on-disk file always wins, so the vendored copy is preferred when present.

For cases the automatic resolution cannot express (such as if the wheel source
is the _original_ external path rather than the SDist output) use
[overrides](./overrides.md) keyed on `from-sdist`, with a separate
`wheel.force-include` entry gated on each build mode (source tree vs.
wheel-from-SDist):

```toml
[tool.scikit-build.sdist.force-include]
"../outside.txt" = "vendored/blob.txt"   # vendor it into the SDist

[[tool.scikit-build.overrides]]
if.from-sdist = false                     # source-tree build: read the original
wheel.force-include."../outside.txt" = "mypackage/blob.txt"

[[tool.scikit-build.overrides]]
if.from-sdist = true                      # wheel-from-SDist: read the vendored copy
wheel.force-include."vendored/blob.txt" = "mypackage/blob.txt"
```

## Configuring CMake arguments and defines

You can select a different build type, such as `Debug`:

```{conftabs} cmake.build-type "Debug"

```

If `cmake.build-type` is left at its default and `CMAKE_BUILD_TYPE` is set in
the environment, that value is used instead. This lets you override the build
type without editing `pyproject.toml` (for example
`CMAKE_BUILD_TYPE=RelWithDebInfo`), mirroring CMake's own handling of the
variable.

:::{versionchanged} 1.0

`CMAKE_BUILD_TYPE` is read from the environment when `cmake.build-type` is left
at its default.

:::

You can also pass a _list_ of build types to build and install more than one
configuration into the same wheel:

```{conftabs} cmake.build-type ["Release", "Debug"]

```

Single-config generators (Ninja, Makefiles) are reconfigured in place for each
extra build type, then rebuilt; multi-config generators (Visual Studio, Xcode,
Ninja Multi-Config) build each `--config`. Every configuration installs to the
same prefix, so set `CMAKE_<CONFIG>_POSTFIX` (such as `CMAKE_DEBUG_POSTFIX=_d`)
on your targets to keep the configurations from clobbering each other, and
select the right module at runtime in your package's `__init__.py`. This is
currently only supported by the default (native) and Hatchling backends.

:::{versionadded} 1.0

Passing a list of build types.

:::

You can specify CMake defines as strings, bools, or lists of strings (list
elements are joined with `;`, with semicolons inside an element escaped with a
backslash):

````{tab} pyproject.toml

```toml
[tool.scikit-build.cmake.define]
SOME_DEFINE = "Foo"
SOME_OPTION = true
FOOD_GROUPS = ["Apple", "Lemon;Lime", "Banana"]
```

````

`````{tab} config-settings


````{tab} uv

```console
$ uv pip install . -Ccmake.define.SOME_DEFINE=ON
```

````

````{tab} pip

```console
$ pip install . -Ccmake.define.SOME_DEFINE=ON
```

````

````{tab} build

```console
$ pipx run build --wheel -Ccmake.define.SOME_DEFINE=ON
```

````

````{tab} cibuildwheel

```toml
[tool.cibuildwheel.config-settings]
"cmake.define.SOME_DEFINE" = "ON"
```

````

`````

````{tab} Environment

```yaml
SKBUILD_CMAKE_DEFINE: SOME_DEFINE=ON
```

````

:::{versionchanged} 0.11

Support for list of strings.

:::

You can also (`pyproject.toml` only) specify a dict, with `env=` to load a
define from an environment variable, with optional `default=`.

```toml
[tool.scikit-build.cmake.define]
SOME_DEFINE = {env="SOME_DEFINE", default="EMPTY"}
```

You can also manually specify the exact CMake args. Beyond the normal
`SKBUILD_CMAKE_ARGS`, the `CMAKE_ARGS` space-separated environment variable is
also supported (with some filtering for options scikit-build-core doesn't
support overriding).

```{conftabs} cmake.args ["-DSOME_DEFINE=ON", "-DOTHER=OFF"]

```

:::{warning}

Setting defines through `cmake.args` in `pyproject.toml` is discouraged because
this cannot be later altered via command line. Use `cmake.define` instead.

:::

You can also specify this using `CMAKE_ARGS`, space separated:

```yaml
CMAKE_ARGS: -DSOME_DEFINE=ON -DOTHER=OFF
```

You can also specify only specific targets to build (leaving this off builds the
default targets):

```{conftabs} build.targets ["python"]

```

:::{versionchanged} 0.10

`cmake.targets` was renamed to `build.targets`.

:::

You can pass raw arguments directly to the build tool, as well:

```{conftabs} build.tool-args ["-j12", "-l13"]

```

```{versionadded} 0.9.4

```

## Environment variables for the build

:::{versionadded} 1.0

:::

The `[tool.scikit-build.env]` table sets environment variables for the CMake
configure, build, and install subprocesses. Use it for things CMake or the
generator read _from the environment_:`CC`/`CXX`, `CFLAGS`, `CMAKE_PREFIX_PATH`,
compiler launchers, parallel-build level, and so on. For CMake `-D` cache
entries, use `cmake.define` instead.

Each value is a literal string, or a table that reads from another environment
variable (`{ env = "OTHER", default = "..." }`). By default a variable is only
set if it is not already present (`setdefault`); add `force = true` to overwrite
an existing value. If a value resolves to nothing (its `env` source is unset and
there is no `default`), the key is skipped. This pairs well with
`[[tool.scikit-build.overrides]]` for platform- or state-specific values.

```toml
[tool.scikit-build.env]
SOME_VAR = "some-value"
CMAKE_PREFIX_PATH = { env = "CMAKE_PREFIX_PATH", default = "/opt/mydeps" }
```

A common use is forwarding a project's historical parallelism variable (such as
`MAX_JOBS`) to `CMAKE_BUILD_PARALLEL_LEVEL`:

```toml
[tool.scikit-build.env]
CMAKE_BUILD_PARALLEL_LEVEL = { env = "MAX_JOBS" }
```

A directly-set `CMAKE_BUILD_PARALLEL_LEVEL` still wins, since `env` entries use
`setdefault` semantics unless `force = true` is given.

```{note}
This table is independent of the `if.env` override _condition_. `if.env` only
matches against the ambient process environment and does not see variables you
define here.
```

The table form (`{ env = ..., default = ..., force = ... }`) is `pyproject.toml`
only; via config-settings or `SKBUILD_ENV_*` you can only set a literal value.

### Selecting a compiler

To pick a specific compiler -- for example, to use GCC instead of MSVC on a
Windows runner -- set `CC`/`CXX`, optionally scoped to a platform with an
override:

```toml
[[tool.scikit-build.overrides]]
if.platform-system = "win32"
env.CC = "gcc"
env.CXX = "g++"
```

These take precedence over the compiler scikit-build-core would otherwise pull
from Python's `sysconfig`, even without `force`.

By default, scikit-build-core sets `CC`/`CXX` from Python's `sysconfig` compiler
when they are not already set. If a project's compiler probes break on that
compiler (a conda narrow sysroot, a stale venv gcc, a cross or oneAPI
toolchain), list the variable in the `env` table to suppress that default and
let CMake detect the compiler from `PATH`; an entry that reads from the same
name does this without pinning a value:

```toml
[tool.scikit-build.env]
CC = { env = "CC" }
CXX = { env = "CXX" }
```

### Search paths for dependencies

To point CMake at extra prefixes (vcpkg, Homebrew, a custom install tree) when
locating dependencies, set `CMAKE_PREFIX_PATH`:

```toml
[tool.scikit-build.env]
CMAKE_PREFIX_PATH = "/opt/mydeps;/usr/local"
```

For dependencies installed as Python packages in the same environment, the
search paths are populated automatically through entry-points; see
[search paths](./search_paths.md).

## Editable installs

Editable installs (`pip install -e .`) are supported, including an optional
(experimental) rebuild-on-import mode and an inplace mode; see the dedicated
[editable installs](./editable.md) page.

[PEP 817]: https://peps.python.org/pep-0817/
[PEP 803]: https://peps.python.org/pep-0803/

## Messages

You can add a message to be printed after a successful or failed build. For
example:

```toml
[tool.scikit-build]
messages.after-success = "{green}Wheel successfully built"
messages.after-failure = """
{bold.red}Sorry{normal}, build failed. Your platform is {platform.platform}.
"""
```

This will be run through Python's formatter, so escape curly brackets if you
need them. Currently, there are several formatter-style keywords available:
`sys`, `platform` (parenthesis will be added for items like `platform.platform`
for you), `__version__` for scikit-build-core's version, and style keywords.

The style keywords are the standard ANSI colors (`red`, `green`, `blue`, ...)
and styles (`normal`, `bold`, `italic`, `underline`, `reverse`), chainable with
dots: `bold.red.bg.blue` is valid (`fg.`/`bg.` select foreground/background,
foreground being the default, and `reset` clears all styles). Remember that you
need to set the environment variable `FORCE_COLOR` to see colors with pip.

```{versionadded} 0.10

```

## Other options

You can select a custom build dir; by default scikit-build-core will use a
temporary dir. If you select a persistent one, you can get major rebuild
speedups.

```{conftabs} build-dir "build/{wheel_tag}"

```

There are several values you can access through Python's formatting syntax. See
[](./formatted.md). For example, `{name}` lets a single `build-dir` shared by
every member of a uv or hatch workspace (e.g. via `SKBUILD_BUILD_DIR`) avoid
collisions: `SKBUILD_BUILD_DIR=/path/to/cache/{name}/{cache_tag}`.

If a cached configuration goes bad, you can throw it away and configure from
scratch with {confval}`cmake.fresh`, like `cmake --fresh`.

```{conftabs} cmake.fresh True

```

```{versionadded} 1.1

```

Scikit-build-core also strictly validates configuration; if you need to disable
this, you can:

```toml
[tool.scikit-build]
strict-config = false
```

Scikit-build-core also occasionally has experimental features. This is applied
to features that do not yet carry the same forward compatibility (using
minimum-version) guarantee that other scikit-build-core features have. These can
only be used if you enable them:

```toml
[tool.scikit-build]
experimental = true
```

The following features currently require this flag:

- **Wheel variants**: [PEP 817][] variant support (`variant`, `variant-name`,
  `variant-label`, and `null-variant`), added in 1.0. See [](./variants.md).
- **Legacy `tool.scikit-build.metadata` plugins**: dynamic metadata providers
  not shipped with scikit-build-core (anything using `provider-path` or a
  provider outside the `scikit_build_core.*` namespace) used through the
  deprecated `tool.scikit-build.metadata` table. The standard
  `[[tool.dynamic-metadata]]` interface supports the same providers without this
  flag. See [](./dynamic.md).
- **Leading-slash wheel trees**: the deprecated absolute spelling (`/platlib`,
  `/data`, `/headers`, `/scripts`, `/metadata`) for `wheel.install-dir` and
  `wheel.force-include`, placed one level above the platlib root. The
  `${SKBUILD_<TREE>_DIR}` prefix is the non-experimental replacement. See
  [`wheel.install-dir`](../reference/configs.md).

The [rebuild-on-import feature](./editable.md) for editable installs is also
considered experimental and subject to change, but is not gated behind this
flag.

You can also fail the build with `fail = true`. This is useful with overrides if
you want to make a specific configuration fail. If this is set, extra
dependencies like `"cmake"` will not be requested.

```{versionadded} 0.10

```

## See also

- [Overrides](./overrides.md): customize settings for a wide variety of
  situations.
- [Full schema](#schema) for all settings.
