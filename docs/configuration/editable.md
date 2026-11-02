# Editable installs

Support for editable installs is provided, with some caveats and configuration.
Recommendations:

- Use `--no-build-isolation` when doing an editable install is recommended; you
  should preinstall your dependencies.
- Automatic rebuilds do not have the original isolated build dir (pip deletes
  it), so select a `build-dir` when using editable installs, especially if you
  also enable automatic rebuilds.
- You need to reinstall to pick up new files.

Resources (via `importlib.resources`) are supported and tested on all supported
Python versions.

```console
# Very experimental rebuild on initial import feature
$ pip install --no-build-isolation -Ceditable.rebuild=true -Cbuild-dir=build -ve.
```

The automatic rebuild-on-import feature (`editable.rebuild`) is still
experimental and subject to change.

You can disable the verbose rebuild output with `editable.verbose=false` if you
want. (Also available as the `SKBUILD_EDITABLE_VERBOSE` envvar when importing;
this will override if non-empty, and `"0"` will disable verbose output).

When `editable.rebuild` is enabled together with a persistent `build-dir`, the
CMake install targets a tree inside the build directory and the redirecting
finder loads the compiled artifacts from there directly, rather than from copies
in site-packages. This means `SKBUILD_PLATLIB_DIR` (or `SKBUILD_PURELIB_DIR`)
and `CMAKE_INSTALL_PREFIX` are baked at their final location when the editable
wheel is first built, so import-triggered rebuilds re-install in place with no
extra reconfigure, including projects that install to an absolute
`${SKBUILD_PLATLIB_DIR}/...` destination. Deleting the build directory breaks
the install, but a rebuildable editable already depends on it.

A build step that imports the package itself (nanobind's `nanobind_add_stub`,
for example) resolves it from the build tree, not through the redirect. Both the
backend and the import-triggered rebuild list the build directory in the
`SKBUILD_EDITABLE_SKIP` environment variable, and the redirecting finder steps
aside in any process that carries it. Put the built module's directory on
`PYTHONPATH` for that step.

`editable.rebuild-dir` selects this install tree directly, and turns on
rebuild-on-import unless `editable.rebuild` is explicitly `false`. With
`editable.rebuild = false`, the editable wheel still holds only the redirect,
and `module.__loader__.rebuild()` refreshes the tree on demand. This is useful
for a project with a large install tree or an expensive install step. It accepts
the same template substitutions as `build-dir`, and the path must be absolute,
or relative to the source directory, and stable between build and run time,
since it is baked at configure time and referenced by absolute path on rebuild.
This only moves the install tree; `build-dir` is still required and still hosts
the CMake build that the rebuild re-runs.

:::{versionadded} 1.0

`editable.rebuild-dir`, a persistent install tree for editable rebuilds.

:::

:::{versionchanged} 1.1

An explicit `editable.rebuild = false` turns off rebuild-on-import when
`editable.rebuild-dir` is set.

:::

The default `editable.mode`, `"redirect"`, uses a custom redirecting finder to
combine the static CMake install dir with the original source code. Python code
added via scikit-build-core's package discovery will be found in the original
location, so changes there are picked up on import, regardless of the
`editable.rebuild` setting. A package that has files in both trees gets a
`__path__` that lists the CMake install tree first, then the source tree, so a
file present in both (for example through `importlib.resources`) resolves to the
installed copy.

:::{versionchanged} 1.0

[PEP 829][] `.start` files are emitted for the redirecting finder on Python
3.15+. Older interpreters emit only `.pth` files.

:::

[PEP 829]: https://peps.python.org/pep-0829/

## Inplace mode

A second mode, `"inplace"`, is also available. Scikit-build-core will simply
install a `.pth` file that points at your source package(s) and do an inplace
CMake build. With all the caveats below, this is very logically simple (one
directory) and a near identical replacement for
`python setup.py build_ext --inplace`; some third party tooling might work
better with this mode.

On the command line, you can pass `-Ceditable.mode=inplace` to enable this mode.
Inplace installs support both automatic (`editable.rebuild`) and manual rebuilds
(see below); since the source directory doubles as the build directory, no
separate `build-dir` is needed (the `build-dir` setting is ignored).

All the usual in-place build caveats apply: only one build per source directory,
you can't change to an out-of-source build without removing the build artifacts,
and your source directory will be littered with build artifacts. Also, to make
your binaries importable, you should set `LIBRARY_OUTPUT_DIRECTORY` to place
them inside your source directory inside the Python packages (append the empty
generator expression `$<0:>` for multi-config generator support; see
[the MSVC FAQ](#msvc-multi-config)); they will be run from the build directory,
rather than installed. You can detect this mode by checking for an in-place
build and checking `SKBUILD` being set.

(triggering-a-rebuild-manually)=

## Triggering a rebuild manually

You don't have to enable `editable.rebuild` to rebuild on demand. Both editable
modes install a loader that exposes a `rebuild()` method. Rebuild _before_ the
first import: once Python loads a compiled extension it cannot unload it, so a
rebuild after import only takes effect in a new process.
`importlib.util.find_spec()` reaches the loader without importing the module:

```python
import importlib.util

importlib.util.find_spec("some_package").loader.rebuild()

import some_package
```

If you don't import or lazily import the compiled code you are trying to load,
you can reach the loader in Python on the outer module:

```python
some_package.__loader__.rebuild()
```

For redirect installs this runs the same `cmake --build`/`--install` cycle used
by the automatic rebuild, and works for any importable name the install provides
-- a package, a plain module, or a compiled extension. A redirect rebuild needs
a persistent build directory, so install with a `build-dir` set:

```console
$ pip install --no-build-isolation -Cbuild-dir=build -ve .
```

If a redirect editable was built without a persistent `build-dir`, there is
nothing to rebuild and the call raises `RuntimeError`.

For inplace installs, `rebuild()` runs `cmake --build` in the source tree (there
is no install step); the source directory is always the build directory, so no
`build-dir` is required.

The finder itself is also on `sys.meta_path` and carries the same method
(`ScikitBuildRedirectingFinder` for redirect installs,
`ScikitBuildInplaceFinder` for inplace):

```python
import sys

finder = next(
    f
    for f in sys.meta_path
    if type(f).__name__ in {"ScikitBuildRedirectingFinder", "ScikitBuildInplaceFinder"}
)
finder.rebuild()
```

:::{versionadded} 1.0

Manual `__loader__.rebuild()` for redirect installs, and both manual and
automatic (`editable.rebuild`) rebuilds for inplace installs.

:::

## Locating the install tree

The same loader exposes `paths`, the package's search locations in `__path__`
order: the CMake install tree and the source tree. This gives a package a
supported way to find the directory that holds its CMake outputs at runtime,
which `importlib.resources.files()` does not provide when a directory exists in
both trees:

```python
from pathlib import Path

source_tree = Path(some_package.__file__).parent
install_tree = next(p for p in some_package.__loader__.paths if p != source_tree)
```

A plain module has no search locations, so its `paths` is empty.

:::{versionadded} 1.1

`__loader__.paths`.

:::
