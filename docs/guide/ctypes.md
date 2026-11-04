# Shipping a library for `ctypes`

If your package is a thin `ctypes` (or `cffi`) wrapper around a CMake-built
shared library, rather than a compiled Python extension, the goal is to install
the library alongside your Python code and then locate it at runtime without
hard-coding a path. This has the nice property that a single wheel works on
every Python version, since the library does not touch the Python ABI. The
tradeoff is that you have to find and load the library yourself.

## Quick start

You do not need a binding tool such as pybind11. The build backend is still
`scikit_build_core.build`. To make a working starter project, run:

```bash
scikit-build init --backend ctypes myproject
```

This makes these files:

```
example
├── pyproject.toml
├── CMakeLists.txt
└── src
    └── example
        ├── __init__.py
        └── _core.c
```

The `pyproject.toml` sets `wheel.py-api = "py3"`, so the wheel has a
`py3-none-<platform>` tag and works on every Python version:

```{literalinclude} ../examples/generated/ctypes/pyproject.toml
:language: toml
```

The `CMakeLists.txt` builds a plain library. It does not use
`find_package(Python)`:

```{literalinclude} ../examples/generated/ctypes/CMakeLists.txt
:language: cmake
```

The C source exports a function:

```{literalinclude} ../examples/generated/ctypes/src/example/_core.c
:language: c
```

The `__init__.py` loads the library and declares the function signature:

```{literalinclude} ../examples/generated/ctypes/src/example/__init__.py
:language: python
```

The sections below give more information about each step.

## Install the library next to your Python code

Point the install destination at your package directory so the library lands in
`site-packages/mypackage/` next to `__init__.py`:

```cmake
install(TARGETS mylib DESTINATION mypackage)
```

The destination is relative to the platlib (`${SKBUILD_PLATLIB_DIR}`) by
default; you can name any of the [install trees](#install-directories)
explicitly if you need to. If you set `wheel.install-dir = "mypackage"`, then
the destination is relative to that instead, and a bare `DESTINATION .` works.

If the library comes from a dependency added with `FetchContent` or
`add_subdirectory`, see [](#dependency-in-site-packages) to move it into your
package without a second copy.

## Find it at runtime with `importlib.resources`

Do **not** compute the path relative to `__file__`---that assumes the package
lives on a real filesystem, which is not guaranteed (it could be in a zip, and
in an editable install the Python source and the compiled library live in
different directories). Use `importlib.resources` instead, which
scikit-build-core's editable installs fully support:

```python
import ctypes
import sys
from importlib.resources import files

# Pick the right suffix for the platform.
_suffix = {"win32": ".dll", "darwin": ".dylib"}.get(sys.platform, ".so")
_lib = files("mypackage") / f"libmylib{_suffix}"

lib = ctypes.CDLL(str(_lib))
```

For the general (zip-safe) case, wrap the traversable in
`importlib.resources.as_file`, which extracts the resource to a real path if
necessary. Because `ctypes` needs the file to remain on disk for the lifetime of
the process, keep the context manager open -- for example with an
`contextlib.ExitStack` closed at interpreter exit:

```python
import atexit, ctypes
from contextlib import ExitStack
from importlib.resources import files, as_file

_files = ExitStack()
atexit.register(_files.close)
_lib = _files.enter_context(as_file(files("mypackage") / f"libmylib{_suffix}"))
lib = ctypes.CDLL(str(_lib))
```

## Editable installs and rebuilds

In redirect-mode editable installs (the default), `importlib.resources` finds
the compiled library through the redirecting finder, so the code above works
unchanged. Note that accessing a resource does **not** trigger a rebuild --
plain libraries are not importable modules, so the automatic `editable.rebuild`
on-import hook does not fire for them. To pick up C/C++ changes, either request
a rebuild explicitly (this works whenever a persistent `build-dir` is set, with
or without `editable.rebuild`)…

```python
import importlib.util

importlib.util.find_spec("mypackage").loader.rebuild()

import mypackage
```

Rebuild before importing `mypackage`: the module-level `ctypes.CDLL` call maps
the library into the process, and the old binary stays loaded even after a
rebuild.

…or import a real extension module from the same project first, which does fire
the on-import hook when `editable.rebuild` is enabled. See
[](#triggering-a-rebuild-manually) for the details and the `build-dir`
requirement.

## Runtime search paths

If your shipped library links against _other_ shared libraries, you still need
to make those discoverable at load time (`RPATH` on Linux/macOS,
`os.add_dll_directory` on Windows). See [](#dynamic-linking) for the full set of
options, including wheel-repair tools.
