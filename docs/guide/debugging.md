# Debugging and IDE integration

Coverage tools (`gcov`/`gcovr`), debuggers (GDB), and editor tooling (the VSCode
C/C++ extension, clangd) all depend on paths recorded at compile time. Two
scikit-build-core defaults make those paths disappear:

- **The build directory is temporary.** Without {confval}`build-dir` set,
  scikit-build-core builds in a temporary directory that is deleted after the
  build, taking coverage data, debug artifacts, and `compile_commands.json` with
  it.
- **Build isolation hides everything else.** `pip install .`, `python -m build`,
  `uv build`, and `uv sync` copy your project and install the build dependencies
  into throwaway environments, so recorded source paths and include paths no
  longer exist after the build.

The shared fix is a persistent build directory with isolation disabled (after
preinstalling your build dependencies), so everything stays in place:

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

gcov records the source path and compilation directory in the `.gcno`
(compile-time) and `.gcda` (run-time) files, and DWARF debug info records the
source path in the compiled extension. If those paths no longer exist when you
run the tool, you get errors such as

```console
$ gcovr --xml coverage.xml -r .
(ERROR) Trouble processing '.../CMakeFiles/foo.dir/_foo.c.gcda' with working directory '/home'.
```

or GDB that cannot show source lines even with debug flags enabled.

With the persistent-tree install above, run gcovr against the persistent tree,
pointing the root at your source:

```bash
gcovr -r . build
```

If you would rather not depend on the paths staying put, make the recorded paths
relocatable with compiler flags -- `-fprofile-abs-path` for gcov and
`-ffile-prefix-map=<build>=<src>` (or `-fdebug-prefix-map=...` for debug info
only) -- for example via {confval}`cmake.define` or `CFLAGS`.

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
