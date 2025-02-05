# Don't let ruff sort imports in this file, we want to keep them with the comments as is
# for clarity.
# ruff: noqa: I001

# Level one pure modules
from . import pmod_c

# Level one extension modules
from . import emod_c

# Level one subpackages
from . import sub_c, sub_d

# Level two pure modules
from .sub_c import pmod_d
from .sub_d import pmod_e

# Level two extension modules
from .sub_c import emod_d
from .sub_d import emod_e

__all__ = [
    "emod_c",
    "emod_d",
    "emod_e",
    "pmod_c",
    "pmod_d",
    "pmod_e",
    "sub_c",
    "sub_d",
]
