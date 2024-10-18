# Don't let ruff sort imports in this file, we want to keep them with the comments as is
# for clarity.
# ruff: noqa: I001

# Level one pure modules
from . import pmod_c

# Level one extension modules
from . import emod_c

# Level one subpackages
from . import subsubpkg1, subsubpkg2

# Level two pure modules
from .subsubpkg1 import pmod_d
from .subsubpkg2 import pmod_e

# Level two extension modules
from .subsubpkg1 import emod_d
from .subsubpkg2 import emod_e

__all__ = [
    "emod_c",
    "emod_d",
    "emod_e",
    "pmod_c",
    "pmod_d",
    "pmod_e",
    "subsubpkg1",
    "subsubpkg2",
]
