"""Test regular and editable installs with generated files.

Illustrate the supported and correct ways to use generated files
(other than traditional compiled extension modules).

Check a variety of scenarios in which package files (modules or data) are
not present in the source tree to confirm that we can find resources as expected,
either by ``import`` or with tools such as `importlib.resources.files()`.
Note that `importlib.resources.files()` requires an argument before Python 3.12.

All scenarios share a single install of the ``cmake_generated`` package; each
assertion block below documents one supported pattern.
"""

from __future__ import annotations

import pytest


@pytest.mark.compile
@pytest.mark.configure
@pytest.mark.integration
@pytest.mark.parametrize("package", ["cmake_generated"], indirect=True)
@pytest.mark.usefixtures("package")
@pytest.mark.usefixtures("isolate")
@pytest.mark.parametrize(
    "editable",
    [
        pytest.param(None, id="not_editable"),
        "redirect",
        pytest.param(
            "inplace",
            marks=pytest.mark.skip(
                "`inplace` editable mode requires build tree layout to match package layout."
            ),
        ),
    ],
    indirect=True,
)
def test_generated_files(editable, isolated):
    isolated.install(
        "-v",
        *editable.flags,
        ".",
        installer="pip",
    )

    # Static data resources in the top-level package, a subpackage, and a
    # namespace package are all found.
    value = isolated.execute(
        "import cmake_generated; print(cmake_generated.get_static_data())"
    )
    assert value == "static value in top-level package"

    value = isolated.execute(
        "import cmake_generated.nested1; print(cmake_generated.nested1.get_static_data())"
    )
    assert value == "static value in subpackage 1"

    value = isolated.execute(
        "import cmake_generated; print(cmake_generated.get_namespace_static_data())"
    )
    assert value == "static value in namespace package"

    # Data generated at configure time (file(GENERATE)) is found.
    value = isolated.execute(
        "import cmake_generated; print(cmake_generated.get_configured_data())"
    )
    assert value == "value written by cmake file generation"

    # Data generated at build time (add_custom_command) into a namespace
    # package is found.
    value = isolated.execute(
        "import cmake_generated; print(cmake_generated.get_namespace_generated_data())"
    )
    assert value == "value written by cmake custom_command"

    # A compiled (non-extension) shared library is loadable through ctypes.
    value = isolated.execute(
        "import cmake_generated; print(cmake_generated.ctypes_function()())"
    )
    assert value == str(42)

    # A module generated at configure time (configure_file) can access and be
    # accessed by all parts of the package.
    value = isolated.execute(
        "from cmake_generated.nested1.generated import __version__; print(__version__)"
    )
    assert value == "1.2.3"

    value = isolated.execute(
        "from cmake_generated.nested1.generated import cmake_generated_static_data; print(cmake_generated_static_data())"
    )
    assert value == "static value in top-level package"

    value = isolated.execute(
        "from cmake_generated.nested1.generated import cmake_generated_nested_static_data; print(cmake_generated_nested_static_data())"
    )
    assert value == "static value in subpackage 1"

    value = isolated.execute(
        "from cmake_generated.nested1.generated import cmake_generated_namespace_static_data; print(cmake_generated_namespace_static_data())"
    )
    assert value == "static value in namespace package"

    value = isolated.execute(
        "from cmake_generated.nested1.generated import nested_data; print(nested_data)"
    )
    assert value == "success"
    value = isolated.execute(
        "from cmake_generated.nested1.generated import nested2_check; print(nested2_check())"
    )
    assert value == "success"
    value = isolated.execute(
        "from cmake_generated.nested2 import nested1_generated_check; print(nested1_generated_check())"
    )
    assert value == "success"

    # A generated module can access generated data in a namespace subpackage.
    value = isolated.execute(
        "from cmake_generated.nested1.generated import cmake_generated_namespace_generated_data; print(cmake_generated_namespace_generated_data())"
    )
    assert value == "value written by cmake custom_command"

    # The generated _version module is importable and matches the installed
    # distribution metadata.
    attr_value = isolated.execute(
        "import cmake_generated; print(cmake_generated.__version__)"
    )
    assert attr_value == "1.2.3"
    metadata_value = isolated.execute(
        "import importlib.metadata; print(importlib.metadata.version('cmake_generated'))"
    )
    assert metadata_value == "1.2.3"

    # Data generated into a regular subpackage (nested2) that has no Python
    # module of its own in the build tree.  Finding it requires propagating the
    # parent package's build-tree path down to the subpackage.
    value = isolated.execute(
        "from cmake_generated.nested2 import get_generated_data; print(get_generated_data())"
    )
    assert value == "value written into a regular subpackage"
