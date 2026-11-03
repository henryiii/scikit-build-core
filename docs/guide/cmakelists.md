# Authoring your CMakeLists

Scikit-build-core provides a variety of useful variables for your CMakeLists.

## Detecting Scikit-build-core

You can write CMakeLists that support running inside and outside
scikit-build-core using the `${SKBUILD}` variable. This will be defined to "2"
for scikit-build-core (and "1" for classic scikit-build). You can also detect
the version of scikit-build-core with `${SKBUILD_CORE_VERSION}`.

## Accessing information

Scikit-build-core provides several useful variables:

- `${SKBUILD_PROJECT_NAME}`: The name of the project.
- `${SKBUILD_PROJECT_VERSION}`: The version of the project, the release segment
  capped to four components (`major.minor.patch.tweak`) so it is always valid
  for `project(VERSION ...)`.
- `${SKBUILD_PROJECT_VERSION_FULL}`: The version of the project as written in
  `project.version`, including dev & local suffix and any leading zeros
  (normalized if `minimum-version` is below 1.1).
- `${SKBUILD_STATE}`: The run state, one of `sdist`, `wheel`, `metadata_wheel`,
  `editable`, or `metadata_editable`.

```{versionchanged} 1.0
`${SKBUILD_PROJECT_VERSION}` is now capped to four release components
(`major.minor.patch.tweak`) so it is always valid for `project(VERSION ...)`.
```

## Finding Python

You can directly use FindPython:

```cmake
find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
```

You always want to find at least `Interpreter` and the `Module` component of the
`Development` package. You do not want to find the entire `Development` package,
as that include `Embed` component, which is not always present and is not
related to making Python extension modules.

If you are making a Limited API / Stable ABI package, you'll need the
`Development.SABIModule` component instead (CMake 3.26+). You can use the
`SKBUILD_SABI_COMPONENT` variable to check to see if it was requested. You can
get the version requested with `${SKBUILD_SABI_VERSION}`.

<!-- prettier-ignore-start -->
:::{warning}
:name: soabi

If you want to cross-compile to Windows ARM, you'll need to use
`${SKBUILD_SOABI}`, which is always correct, instead of trusting FindPython's
`Python_SOABI` value. You can manually set the extension suffix after making a
target:

```cmake
if(CMAKE_SYSTEM_NAME STREQUAL "Windows")
    set_property (TARGET ${name} PROPERTY SUFFIX ".${SKBUILD_SOABI}.pyd")
else()
    set_property (TARGET ${name} PROPERTY SUFFIX ".${SKBUILD_SOABI}${CMAKE_SHARED_MODULE_SUFFIX}")
endif()
```
<!-- prettier-ignore-end -->

A quicker way to do this would be to instead override `Python_SOABI` after
`find_package(Python)`:

```cmake
set(Python_SOABI ${SKBUILD_SOABI})
set(Python_SOSABI ${SKBUILD_SOABI})
```

`python_add_library` uses `Python_SOSABI` when `USE_SABI` is set, and
`Python_SOABI` otherwise. However, this isn't officially supported upstream, and
only works due to the way this variable is used when creating targets.

:::

:::{note}

If you want to use the old, deprecated FindPythonInterp and FindPythonLibs
instead, you can. FindPythonLibs requires a trick to work when no Python library
is present (like in manylinux): set `PYTHON_LIBRARY` to anything to make it
succeed.

:::

## Finding other packages

Scikit-build-core includes various pythonic paths to the CMake search paths by
default so that usually you only need to include the dependent project inside
the `build-system.requires` section. Note that `cmake` and `ninja` should not be
included in that section.

See [search paths section](../configuration/search_paths.md) for more details on
how the search paths are constructed.

(install-directories)=

## Install directories

Scikit-build-core will install directly into platlib, which will end up in
site-packages. If you are used to scikit-build, you might find targeting
`/<module_name>` to be more natural. You can mimic the old behavior with a
configuration option (`wheel.install-dir`). However, scikit-build-core is more
powerful, and allows you to install multiple packages or top-level extension
modules if you need to.

You can access all of the possible output directories, regardless of
configuration, with the variables:

- `${SKBUILD_PLATLIB_DIR}`: The original platlib directory. Anything here goes
  directly to site-packages when a wheel is installed.
- `${SKBUILD_DATA_DIR}`: The data directory. Anything here goes to the root of
  the environment when a wheel is installed (use with care).
- `${SKBUILD_HEADERS_DIR}`: The header directory. Anything in here gets
  installed to Python's header directory.
- `${SKBUILD_SCRIPTS_DIR}`: The scripts directory. Anything placed in here will
  go to `bin` (Unix) or `Scripts` (Windows).
- `${SKBUILD_METADATA_DIR}`: The dist-info directory. Licenses go in the
  `licenses` subdirectory. _Note that CMake is not run in the
  `prepare_metadata_\*` hooks, so anything written to this directory will only
  be present when writing wheels.\_
- `${SKBUILD_NULL_DIR}`: Anything installed here will not be placed in the
  wheel.

(limited-api)=

## Limited API / Stable ABI

You can activate the Stable ABI by setting `tool.scikit-build.wheel.py-api`
equal to a valid CPython
[Python Tag](https://packaging.python.org/en/latest/specifications/platform-compatibility-tags/#python-tag)
in your `pyproject.toml`:

```toml
[tool.scikit-build]
wheel.py-api = "cp310"
```

The possible values and the resulting wheel tags are covered in
[customizing the output wheel](../configuration/index.md#customizing-the-output-wheel);
this section covers the CMake side.

When you do that, `${SKBUILD_SABI_COMPONENT}` will be set to
`Development.SABIModule` if you can target this (new enough CPython), and will
remain an empty string otherwise (PyPy). This allows the following idiom:

```cmake
find_package(Python REQUIRED COMPONENTS Interpreter Development.Module ${SKBUILD_SABI_COMPONENT})
```

This will require the `Development.SABIModule` component only if
scikit-build-core is driving the compilation and is targeting ABI3. If you want
to support Stable ABI from outside scikit-build-core, look into the
`OPTIONAL_COMPONENTS` flag for `find_package`.

When defining your module, if you only support the Stable ABI after some point,
you should use (for example for 3.11):

```cmake
if(NOT "${SKBUILD_SABI_VERSION}" STREQUAL "")
  python_add_library(some_ext MODULE WITH_SOABI USE_SABI ${SKBUILD_SABI_VERSION} ...)
else()
  python_add_library(some_ext MODULE WITH_SOABI ...)
endif()
```

If you have a lot of libraries, you can conditionally save these two items into
a variable with `set(USE_SABI USE_SABI ${SKBUILD_SABI_VERSION})` and use it in
all your `python_add_library` calls:

```
if(NOT "${SKBUILD_SABI_VERSION}" STREQUAL "")
  set(USE_SABI "USE_SABI ${SKBUILD_SABI_VERSION}")
endif()

python_add_library(some_ext MODULE WITH_SOABI ${USE_SABI} ...)
```

This will define `Py_LIMITED_API` for you. If you want to support building
directly from CMake, you need to protect this for Python version,
`Python_INTERPRETER_ID STREQUAL Python`, and free-threading Python 3.13+ doesn't
support ABI3 either.

If you are using `nanobind`'s `nanobind_add_module`, the `STABLE_ABI` flag does
this automatically for you for 3.12+.

## Language helpers

Helpers for Cython and F2Py are provided as standalone CMake packages rather
than being built into scikit-build-core: [cython-cmake][] (`include(UseCython)`)
and [f2py-cmake][] (`include(UseF2Py)`). Add them to your `build.requires` and
see the [getting started guide](getting_started.md) for full examples.

[cython-cmake]: https://github.com/scikit-build/cython-cmake
[f2py-cmake]: https://github.com/scikit-build/f2py-cmake
