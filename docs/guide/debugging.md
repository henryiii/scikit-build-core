# Debugging and IDE integration

Coverage tools (`gcov`/`gcovr`), debuggers (GDB), and editor tooling (the VSCode
C/C++ extension, clangd) all depend on paths recorded at compile time. Check
which paths your tool needs and where the build recorded them.

- **CMake build directory.** Without {confval}`build-dir`, scikit-build-core
  removes its temporary build directory when the build finishes. Set it to a
  persistent directory to keep coverage notes, object files, and
  `compile_commands.json`.
- **Project sources.** For a local checkout, `pip install .`,
  `pip install -e .`, and `uv sync` build from the checkout. By default,
  `python -m build` and `uv build` first create an sdist, then build a wheel
  from its temporary extracted sources. To build the wheel directly from the
  checkout, use `python -m build --wheel` or `uv build --wheel`. See [pip’s
  local project installs][pip-local] and [build’s default build
  flow][build-default].
- **Build dependencies.** Build isolation can leave recorded include paths
  pointing to a temporary environment. If your editor or debugger needs those
  headers after the build, install the build dependencies in your own
  environment and disable isolation.

For example, after installing the build dependencies, you can keep the sources,
CMake output, and dependency headers available with an editable install:

```bash
pip install --no-build-isolation -Cbuild-dir=build -ve .
```

You can set the build directory in `pyproject.toml` instead of on the command
line:

```toml
[tool.scikit-build]
build-dir = "build"
```

## Coverage and debugging (gcov / gcovr / GDB)

GCC writes source locations and the compilation directory to its `.gcno` notes
at compile time. Running the instrumented code writes execution counts to the
corresponding `.gcda` files. Debuggers use source paths recorded in the
extension’s DWARF debug info. If the build or source paths no longer exist, you
can get errors such as

```console
$ gcovr --xml coverage.xml -r .
(ERROR) Trouble processing '.../CMakeFiles/foo.dir/_foo.c.gcda' with working directory '/home'.
```

or GDB that cannot show source lines even with debug flags enabled.

Compile and link with coverage enabled (for GCC, `--coverage`), then run the
installed extension to produce the `.gcda` files. From the source checkout,
point gcovr at the directory that contains those files and the matching `.gcno`
files:

```bash
gcovr -r . build
```

If files were compiled from different working directories, GCC’s
[`-fprofile-abs-path`][gcc-abs] records absolute source filenames in the `.gcno`
files. Keep those source paths available when collecting coverage. For debug
info, `-fdebug-prefix-map=OLD=NEW` can record a replacement path if you know
where the sources will be available to the debugger.

[pip-local]:
  https://pip.pypa.io/en/stable/topics/local-project-installs/#build-artifacts
[build-default]: https://build.pypa.io/en/stable/how-to/basic-usage.html
[gcc-abs]:
  https://gcc.gnu.org/onlinedocs/gcc/Instrumentation-Options.html#index-fprofile-abs-path

(compile-commands)=

## IDE IntelliSense (`compile_commands.json`)

Editor tooling resolves headers like `pybind11/pybind11.h` from your include
paths. With build isolation, binding libraries such as pybind11 and nanobind
live in a throwaway overlay -- CMake reports a path such as
`.../Temp/pip-build-env-xxxx/overlay/Lib/site-packages/pybind11/include`, which
no longer exists when your editor looks for it.

Extend the shared fix by having CMake export a compile database:

````{tab} uv

```bash
uv pip install scikit-build-core pybind11
uv pip install --no-build-isolation -ve . \
  -Cbuild-dir=build \
  -Ccmake.define.CMAKE_EXPORT_COMPILE_COMMANDS=1
```

In a uv-managed project, disable isolation for your package instead, so
`uv sync` reuses the environment's build dependencies rather than a discarded
overlay:

```toml
[tool.uv]
no-build-isolation-package = ["mypackage"]
```

````

````{tab} pip

```bash
pip install scikit-build-core pybind11
pip install --no-build-isolation --check-build-dependencies -ve . \
  -Cbuild-dir=build \
  -Ccmake.define.CMAKE_EXPORT_COMPILE_COMMANDS=1
```

````

This writes `build/compile_commands.json` with real, persistent paths. Then
point your editor at the file. For clangd, add `--compile-commands-dir=build`
(or a `.clangd` with a `CompileFlags.CompilationDatabase: build` entry); for the
VSCode C/C++ extension, set
`"C_Cpp.default.compileCommands": "${workspaceFolder}/build/compile_commands.json"`.
See [editable installs](../configuration/editable.md) for the related
`--no-build-isolation` recommendations.

(ccache)=

## Compiler caches (ccache / sccache)

A compiler cache compares the full compile command. With build isolation, the
include path of a build dependency such as pybind11 is in a new temporary
environment for each build (for example `/tmp/pip-build-env-xxxx/...` or
`~/.cache/uv/builds-v0/.tmpxxxx/...`). Thus the command changes each time and
the cache never hits, even with a fixed {confval}`build-dir`. `CCACHE_BASEDIR`
does not help, because the random part stays in the path.

The simplest fix is the persistent-tree install above: disable isolation and
preinstall the build dependencies. Build isolation was not designed to work well
with editable installs. A full fix would require tools like uv and pip to keep a
consistent path for repeated isolated environments, which is outside the scope
of scikit-build-core.

If you must build with isolation (for example, wheel builds in CI), get the
headers from a stable location instead of the build environment. Move pybind11
from `build-system.requires` to a fixed location, like a git submodule.

## Debug builds on Windows

A `cmake.build-type=Debug` extension links against the debug CPython
(`pythonXY_d.dll`, `_d.pyd` suffix), so it only loads under a debug interpreter
(`python_d.exe`) -- importing it under a normal `python.exe` crashes with
`0x80000003`. This is CPython behavior, not scikit-build-core's: run the build
itself under `python_d.exe` so the `_d` suffix and import library line up (and
the `t` ABI flag is added for free-threaded debug builds, e.g.
`pythonXYt_d.dll`).

To keep debug info while still loading under a normal Python, don't do a debug
build -- instead undefine `_DEBUG` around the CPython headers so they don't
auto-link `pythonXY_d.lib`, and add debug flags yourself:

```c
#ifdef _DEBUG
#  define SKB_RESTORE_DEBUG
#  undef _DEBUG
#endif
#include <Python.h>
#ifdef SKB_RESTORE_DEBUG
#  define _DEBUG
#endif
```
