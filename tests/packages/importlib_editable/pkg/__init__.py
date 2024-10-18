# Don't let ruff sort imports in this file, we want to keep them with the comments as is
# for clarity.
# ruff: noqa: I001

# Level one pure modules
from . import pmod_a

# Level one extension modules
from . import emod_a

# Level one subpackages
from . import subpkg1, subpkg2

# Level two pure modules
from .subpkg1 import pmod_b
from .subpkg2 import pmod_c

# Level two extension modules
from .subpkg1 import emod_b
from .subpkg2 import emod_c

# Level two subpackages
from .subpkg2 import subsubpkg1, subsubpkg2

# Level three pure modules
from .subpkg2.subsubpkg1 import pmod_d
from .subpkg2.subsubpkg2 import pmod_e

# Level three extension modules
from .subpkg2.subsubpkg1 import emod_d
from .subpkg2.subsubpkg2 import emod_e

__all__ = [
    "emod_a",
    "emod_b",
    "emod_c",
    "emod_d",
    "emod_e",
    "pmod_a",
    "pmod_b",
    "pmod_c",
    "pmod_d",
    "pmod_e",
    "subpkg1",
    "subpkg2",
    "subsubpkg1",
    "subsubpkg2",
]
