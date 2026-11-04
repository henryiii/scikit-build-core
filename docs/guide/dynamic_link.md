(dynamic-linking)=

# Dynamic linking

If you want to support dynamic linkages between python projects or system
libraries, you will likely encounter some issues in making sure the compiled
libraries/python bindings work after the wheel is created and the python project
is installed on the system. The most common issues are the missing hints
pointing to where the runtime libraries are located, specifically `RPATH` on
Linux and MacOS systems, and `PATH`/`os.add_dll_directory` on Windows systems.
Here are some recommendations on how to address them. If you got here because a
vendored dependency's library landed in `site-packages/bin` or `lib`, see
[that FAQ entry](#dependency-in-site-packages) for the specific fix.

## Link to the static libraries

The easiest solution is to make sure you link to the static libraries
counterparts during the CMake build. How to achieve this depends on the specific
dependency, how it is imported in the CMake project and how the dependency is
packaged in each ecosystem.

For example for [Boost][FindBoost] this is controlled via the variable
`Boost_USE_STATIC_LIBS`.

[FindBoost]: inv:cmake:cmake:module#module:FindBoost

## Wheel repair tools

The per-platform wheel repair tools ([auditwheel], [delocate], [delvewheel]; see
[repairing wheels](#repairing-wheels)) bundle any dynamic libraries used and
patch the libraries/python bindings to prioritize them. They rename each bundled
library with a unique hash to avoid collisions if another package bundles the
same library, and they do not allow cross-wheel library dependencies.

## Manual patching

You can manually make a relative RPath. This has the benefit of working when not
running scikit-build-core, as well.

The `RPATH` patching can be done as

```cmake
if(APPLE)
  set(origin_token "@loader_path")
else()
  set(origin_token "$ORIGIN")
endif()
set_property(TARGET <target> PROPERTY INSTALL_RPATH
  "${origin_token}/install_path/to/dynamic_library"
)
```

For Windows patching, this has to be done at the python files using
`os.add_dll_directory` at the top-most package `__init__.py` file or top-level
python module files.

```python
import os
from pathlib import Path

dependency_dll_path = Path(__file__).parent / "install_path/to/dynamic_library"
os.add_dll_directory(str(dependency_dll_path))
```

<!-- prettier-ignore-start -->

[auditwheel]: https://pypi.org/project/auditwheel/
[delocate]: https://pypi.org/project/delocate/
[delvewheel]: https://pypi.org/project/delvewheel/

<!-- prettier-ignore-end -->
