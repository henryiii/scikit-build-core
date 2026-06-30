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


````{tab} pip

```console
$ pip install . -v --config-settings=build.verbose=true --config-settings=logging.level=INFO
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
minimum-version = "0.2"
```

In your `pyproject.toml`, you can specify the special string
`"build-system.requires"`, which will read the minimum version from your
build-system requirements directly; you must specify a minimum there to use this
automatic feature.

```toml
[build-system]
requires = ["scikit-build-core>=0.10"]

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
  the default for `sdist.include-mode`.

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
can turn this down if you'd like ("3.15", scikit-build-core's minimum version,
would turn it off).

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
from the source distribution. You can list files to explicitly include and
exclude if you want:

```toml
[tool.scikit-build]
sdist.include = ["src/some_generated_file.txt"]
sdist.exclude = [".github"]
```

You can select a couple of alternative modes, as well. If you want to manually
control this, without reading `.gitignore`, use:

```toml
[tool.scikit-build]
sdist.include-mode = "manual"
```

There's also a `"classic"` mode, which fully traverses all directories to check
rules (default is using scikit-build-core less than 0.12).

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

### Building a CMake-free wheel from the SDist

For a package whose wheel is effectively pure (only headers, CMake config files,
and other generated-at-configure/install-time text — no compiled extension), you
can run the CMake generation once during the SDist build and ship its install
tree _inside_ the SDist. A wheel built from that SDist then needs no CMake at
all:

```toml
[tool.scikit-build]
sdist.cmake = true
# Setting sdist.install-dir upgrades the SDist CMake run to a full
# configure + build + install, vendoring the staged wheel trees into the SDist.
sdist.install-dir = ".cmake-install"
# Declare the wheel pure so the SDist-build and from-SDist wheels match
# (purelib -> py3-none-any).
wheel.platlib = false
```

That is the whole recipe. When a wheel is built from the unpacked SDist
(detected by the presence of `PKG-INFO`, the same signal as
[`if.from-sdist`](#overrides)), scikit-build-core sees the vendored
`.cmake-install` tree, **disables CMake automatically**, and restages every tree
the SDist build captured — `platlib`/`purelib`, `data`, `headers`, `scripts`,
and `metadata` — back into the wheel. Nothing CMake installed via the
`SKBUILD_*_DIR` cache variables is lost, and there is no per-tree
`wheel.force-include` recipe to maintain.

Building a wheel directly from the source tree is unchanged: there is no
`PKG-INFO`, so CMake runs as usual. The `.cmake-install` tree is written into
the SDist root (it is _not_ added to your source tree).

To opt back out of the automatic behavior for a from-SDist build, set
`wheel.cmake` explicitly (e.g. an `if.from-sdist` override with
`wheel.cmake = true` to re-run CMake, or `wheel.cmake = false` together with a
hand-written `wheel.force-include` recipe). An explicit `wheel.cmake` of either
value suppresses the automatic restaging.

#### Compiled (non-pure) wheels

Automatic repackaging only applies to pure (`purelib`) wheels. A compiled
`platlib` tree cannot be restaged this way — its platform tag is computed by the
CMake build and cannot be recovered when CMake is skipped, so a vendored
`platlib` tree built against a `purelib` wheel is an error. If your install tree
is compiled, keep `wheel.cmake` and an explicit `wheel.tags`/`force-include`
recipe instead:

```toml
[[tool.scikit-build.overrides]]
if.from-sdist = true
wheel.cmake = false
wheel.tags = ["py3-none-manylinux_2_17_x86_64"]   # the original build's tag
wheel.force-include.".cmake-install/platlib" = "${SKBUILD_PLATLIB_DIR}"
wheel.force-include.".cmake-install/headers" = "${SKBUILD_HEADERS_DIR}"
```

The vendored lib subdirectory is named `platlib` or `purelib` to match the wheel
the SDist build produced.

## Customizing the built wheel

The wheel will automatically look for Python packages at `src/<package_name>`,
`python/<package_name>`, and `<package_name>`, in that order. If you want to
list packages explicitly, you can. The final path element is the package.

```toml
[tool.scikit-build]
wheel.packages = ["python/src/mypackage"]
```

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

The available trees are `${SKBUILD_PLATLIB_DIR}` (the default),
`${SKBUILD_PURELIB_DIR}`, `${SKBUILD_DATA_DIR}`, `${SKBUILD_HEADERS_DIR}`,
`${SKBUILD_SCRIPTS_DIR}`, `${SKBUILD_METADATA_DIR}`, and `${SKBUILD_NULL_DIR}`.
This matches the cache variables available from within CMake.

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

### Force-including files

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
area), and also accept a `${SKBUILD_<TREE>_DIR}` prefix (e.g.
`${SKBUILD_DATA_DIR}`, `${SKBUILD_SCRIPTS_DIR}`, `${SKBUILD_HEADERS_DIR}`,
`${SKBUILD_METADATA_DIR}`) to target that wheel tree instead, matching the
`SKBUILD_*_DIR` CMake cache variables. The older leading-slash spelling
(`/data`, `/scripts`, ...) does the same but requires `experimental = true`.
Force-included wheel files are placed last, so they override discovered package
files and CMake output at the same destination.

A force-included _file_ also overrides the matching exclude list
(`wheel.exclude` for wheels, `sdist.exclude` for SDists): naming an exact source
is an explicit request, so it wins even if an exclude pattern matches its
destination. A force-included _directory_ stays subject to that exclude, so a
bulk tree copy can still be trimmed by an exclude pattern (e.g. force-include a
directory and exclude `**/*.bzl` to drop the Bazel files from it).

#### Building a wheel from an SDist

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

For cases the automatic resolution cannot express — e.g. the wheel source is the
_original_ external path rather than the SDist output — use
[overrides](#overrides) keyed on `from-sdist`, with a separate
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

## Customizing the output wheel

The python API tags for your wheel will be correct assuming you are building a
CPython extension. If you are building a Limited ABI extension, you should set
the wheel tags for the version you support:

```toml
[tool.scikit-build]
wheel.py-api = "cp38"
```

Scikit-build-core will only target ABI3 if the version of Python is equal to or
newer than the one you set. `${SKBUILD_SABI_COMPONENT}` is set to
`Development.SABIModule` when targeting ABI3 or ABI3T, and is an empty string
otherwise. For free-threaded Python (PEP 703), you can use `cp315t` to target
the free-threaded stable ABI, which sets `Py_TARGET_ABI3T` (if using CMake
4.4+). The emitted wheel tag is `cp315-abi3t-*` following per PEP 803.

If you are not using CPython at all, you can specify any version of Python is
fine:

```toml
[tool.scikit-build]
wheel.py-api = "py3"
```

Or even Python 2 + 3 (you still will need a version of Python scikit-build-core
supports to build the initial wheel):

```toml
[tool.scikit-build]
wheel.py-api = "py2.py3"
```

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

```{conftabs} install.components ["python"]

```

And you can turn off binary stripping:

```{conftabs} install.strip False

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

You can specify CMake defines as strings or bools:

````{tab} pyproject.toml

```toml
[tool.scikit-build.cmake.define]
SOME_DEFINE = "Foo"
SOME_OPTION = true
```

````

You can even specify a CMake define as a list of strings:

````{tab} pyproject.toml

```toml
[tool.scikit-build.cmake.define]
FOOD_GROUPS = [
    "Apple",
    "Lemon;Lime",
    "Banana",
    "Pineapple;Mango",
]
```

````

Semicolons inside the list elements will be escaped with a backslash (`\`) and
the resulting list elements will be joined together with semicolons (`;`) before
being converted to command-line arguments.

:::{versionchanged} 0.11

Support for list of strings.

:::

`````{tab} config-settings


````{tab} pip

```console
$ pip install . --config-settings=cmake.define.SOME_DEFINE=ON
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

The `[tool.scikit-build.env]` table sets environment variables for the CMake
configure, build, and install subprocesses. Use it for things CMake or the
generator read _from the environment_ — `CC`/`CXX`, `CFLAGS`,
`CMAKE_PREFIX_PATH`, compiler launchers, parallel-build level, and so on. For
CMake `-D` cache entries, use `cmake.define` instead.

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

To pick a specific compiler — for example, to use GCC instead of MSVC on a
Windows runner — set `CC`/`CXX`, optionally scoped to a platform with an
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
let CMake detect the compiler from `PATH` — an entry that reads from the same
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

## Editable installs

Support for editable installs is provided, with some caveats and configuration.
Recommendations:

- Use `--no-build-isolation` when doing an editable install is recommended; you
  should preinstall your dependencies.
- Automatic rebuilds do not have the original isolated build dir (pip deletes
  it), so select a `build-dir` when using editable installs, especially if you
  also enable automatic rebuilds.
- You need to reinstall to pick up new files.

Resources (via `importlib.resources`) are supported and tested on all supported
Python versions. On Python 3.8, use the `importlib_resources` backport, since
`importlib.resources.files` was added to the standard library in Python 3.9.

```console
# Very experimental rebuild on initial import feature
$ pip install --no-build-isolation --config-settings=editable.rebuild=true -Cbuild-dir=build -ve.
```

The automatic rebuild-on-import feature (`editable.rebuild`) is still
experimental and subject to change.

You can disable the verbose rebuild output with `editable.verbose=false` if you
want. (Also available as the `SKBUILD_EDITABLE_VERBOSE` envvar when importing;
this will override if non-empty, and `"0"` will disable verbose output).

The default `editable.mode`, `"redirect"`, uses a custom redirecting finder to
combine the static CMake install dir with the original source code. Python code
added via scikit-build-core's package discovery will be found in the original
location, so changes there are picked up on import, regardless of the
`editable.rebuild` setting.

The redirecting finder is installed at interpreter startup. On Python 3.15+,
this uses a [PEP 829][] `.start` file (the slightly safer, structured
replacement for the deprecated `import` line in a `.pth` file); on older Pythons
it uses the classic `.pth` `import` line. This is handled automatically based on
the interpreter running the editable install.

[PEP 829]: https://peps.python.org/pep-0829/
[PEP 817]: https://peps.python.org/pep-0817/

:::{note}

A second mode, `"inplace"`, is also available. This does an in-place CMake
build, so all the caveats there apply too -- only one build per source
directory, you can't change to an out-of-source builds without removing the
build artifacts, your source directory will be littered with build artifacts,
etc. Also, to make your binaries importable, you should set
`LIBRARY_OUTPUT_DIRECTORY` (include a generator expression, like the empty one
`$<0:>` for multi-config generator support, like MSVC, so you don't have to set
all possible `*_<CONFIG>` variations) to make sure they are placed inside your
source directory inside the Python packages; this will be run from the build
directory, rather than installed. This will also not support automatic rebuilds.
The build directory setting will be ignored if you use this and perform an
editable install. You can detect this mode by checking for an in-place build and
checking `SKBUILD` being set.

With all the caveats, this is very logically simple (one directory) and a near
identical replacement for `python setup.py build_ext --inplace`. Some third
party tooling might work better with this mode. Scikit-build-core will simply
install a `.pth` file that points at your source package(s) and do an inplace
CMake build.

On the command line, you can pass `-Ceditable.mode=inplace` to enable this mode.

:::

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

For styles, the colors are `default`, `red`, `green`, `yellow`, `blue`,
`magenta`, `cyan`, and `white`. These can be accessed as `fg.*` or `bg.*`,
without a qualifier the foreground is assumed. Styles like `normal`, `bold`,
`italic`, `underline`, `reverse` are also provided. A full clearing of all
styles is possible with `reset`. These all can be chained, as well, so
`bold.red.bg.blue` is valid, and will produce an optimized escape code. Remember
that you need to set the environment variable `FORCE_COLOR` to see colors with
pip.

```{versionadded} 0.10

```

## Other options

You can select a custom build dir; by default scikit-build-core will use a
temporary dir. If you select a persistent one, you can get major rebuild
speedups.

```{conftabs} build-dir "build/{wheel_tag}"

```

There are several values you can access through Python's formatting syntax. See
[](./formatted.md).

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
  `variant-label`, and `null-variant`). See
  [](../guide/faqs.md#building-wheel-variants-experimental).
- **Third-party dynamic-metadata plugins**: dynamic metadata providers not
  shipped with scikit-build-core (anything using `provider-path` or a provider
  outside the `scikit_build_core.*` namespace). See [](./dynamic.md).
- **Leading-slash wheel trees**: the deprecated absolute spelling (`/platlib`,
  `/data`, `/headers`, `/scripts`, `/metadata`) for `wheel.install-dir` and
  `wheel.force-include`, placed one level above the platlib root. The
  `${SKBUILD_<TREE>_DIR}` prefix is the non-experimental replacement. See
  [`wheel.install-dir`](../reference/configs.md).

The [rebuild-on-import feature](#editable-installs) for editable installs is
also considered experimental and subject to change, but is not gated behind this
flag.

You can also fail the build with `fail = true`. This is useful with overrides if
you want to make a specific configuration fail. If this is set, extra
dependencies like `"cmake"` will not be requested.

```{versionadded} 0.10

```

## Overrides

The overrides system allows you to customize for a wide variety of situations.
It is described at [](#overrides).

## Full Schema

You can see the full schema at [](#schema).
