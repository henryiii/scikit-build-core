# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

from __future__ import annotations

import importlib
import importlib.metadata
import inspect
import os
import sys
import warnings
from pathlib import Path

try:
    import scikit_build_core
except ModuleNotFoundError:
    scikit_build_core = None

ROOT = Path(__file__).parent.parent.resolve()

# Custom extension
sys.path.append(str(ROOT / "docs/ext"))

try:
    from scikit_build_core import __version__ as version
except ModuleNotFoundError:
    try:
        version = importlib.metadata.version("scikit_build_core")
    except ModuleNotFoundError:
        msg = (
            "Package should be installed to produce documentation! "
            "Assuming a modern git archive was used for version discovery."
        )
        warnings.warn(msg, stacklevel=1)

        from setuptools_scm import get_version

        version = get_version(root=ROOT, fallback_root=ROOT)

# Filter git details from version
release = version.split("+")[0]


# -- Generate the getting-started examples from the init templates -----------
# The init command's templates (resources/templates) are the single source of
# truth for example projects. Render each backend here so literalinclude and
# command-output pull from real, build-tested projects rather than duplicates.
EXAMPLE_BACKENDS = [
    "pybind11",
    "nanobind",
    "swig",
    "cython",
    "c",
    "abi3",
    "abi3t",
    "fortran",
    "ctypes",
]
GENERATED_EXAMPLES = ROOT / "docs/examples/generated"
if scikit_build_core is not None:
    import shutil

    from scikit_build_core.init.__main__ import generate_project

    shutil.rmtree(GENERATED_EXAMPLES, ignore_errors=True)
    for _backend in EXAMPLE_BACKENDS:
        generate_project(GENERATED_EXAMPLES / _backend, _backend, "example")


# -- Project information -----------------------------------------------------

project = "scikit-build-core"
copyright = "2022, The Scikit-Build admins"
author = "Henry Schreiner"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "conftabs",  # in /ext
    "click_extra.sphinx",
    "erbsland.sphinx.ansi",
    "myst_parser",
    "sphinx-jsonschema",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.linkcode",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinx_inline_tabs",
    "sphinx_llm.txt",
    "sphinx_tippy",
    "sphinxcontrib.programoutput",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

source_suffix = [".rst", ".md"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = [
    "_build",
    "**.ipynb_checkpoints",
    "Thumbs.db",
    ".DS_Store",
    ".env",
    "**.venv",
    "examples/downstream",
    "examples/generated",
]


intersphinx_mapping = {
    "cmake": ("https://cmake.org/cmake/help/latest/", None),
    "python": ("https://docs.python.org/3", None),
    "packaging": ("https://packaging.pypa.io/en/stable", None),
    "setuptools": ("https://setuptools.pypa.io/en/latest", None),
    "hatchling": ("https://hatch.pypa.io/latest", None),
}
tippy_rtd_urls = [
    "https://packaging.pypa.io/en/stable",
    "https://setuptools.pypa.io/en/latest",
]
# Recolored to furo's theme variables in _static/tippy.css.
tippy_props = {"theme": "light-border"}

# SkbuildMetadata subclasses the vendored StandardMetadata, whose inherited
# annotations name modules this one does not import.
suppress_warnings = ["sphinx_autodoc_typehints.forward_reference"]

nitpick_ignore = [
    ("py:class", "setuptools.dist.Distribution"),
    ("py:class", "T"),
    ("py:class", "scikit_build_core.settings.sources.T"),
    ("py:class", "scikit_build_core._vendor.pyproject_metadata.StandardMetadata"),
    ("py:class", "scikit_build_core._vendor.pyproject_metadata.RFC822Message"),
    ("py:data", "typing.Union"),
]

# sphinx-llm 1.1+ relays the markdown builder's warnings for nodes it can't
# render, which fails the -W build.
llms_txt_suppress_unknown_node_warnings = True

linkcheck_anchors_ignore = [
    # This seems to be broken on GitHub readmes
    "default-versioning-scheme",
    "git-archives",
]
# Retry transient failures (slow hosts like docs.rapids.ai) before giving up.
# The retry loop only re-tries links reported as "broken", so timeouts must be
# reported as broken for the retries to apply to them.
linkcheck_retries = 3
linkcheck_timeout = 30
linkcheck_report_timeouts_as_broken = True
linkcheck_ignore = [
    # Rate limited
    r"https://github.com/?.*",
    # Fails sometimes
    "https://learn.scientific-python.org/development",
]
# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "furo"

html_theme_options = {
    "source_repository": "https://github.com/scikit-build/scikit-build-core",
    "source_branch": "main",
    "source_directory": "docs/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/scikit-build/scikit-build-core",
            "html": """
                <svg stroke="currentColor" fill="currentColor" stroke-width="0" viewBox="0 0 16 16">
                    <path fill-rule="evenodd" d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"></path>
                </svg>
            """,
            "class": "",
        },
    ],
}
html_copy_source = False
html_show_sourcelink = False
html_static_path = ["_static"]
# The light-border theme gives the tooltip arrow an outline; tippy.css recolors
# it (and the box) from furo's theme variables. tippy.css must come last so its
# overrides win. sphinx-tippy already loads tippy.js itself from this CDN.
html_css_files = [
    "custom.css",
    "https://unpkg.com/tippy.js@6/themes/light-border.css",
    "tippy.css",
]


# -- Extension configuration -------------------------------------------------
myst_enable_extensions = [
    "alert",  # GitHub-style > [!NOTE] blockquote admonitions
    "attrs_inline",  # {.class} on links/code, used by the projects grid
    "colon_fence",
    "substitution",
    "deflist",
]


myst_substitutions = {
    "version": version,
}
myst_heading_anchors = 2

programoutput_use_ansi = True

# Needed to ensure color output
# See https://github.com/OpenNTI/sphinxcontrib-programoutput/issues/77
os.environ["FORCE_COLOR"] = "1"
os.environ.pop("NO_COLOR", None)

# One entry per manual page. List of tuples
# (source start file, name, description, authors, manual section)

man_pages = [
    (
        "man",
        project,
        "A Python module build backend for CMake",
        [author],
        7,
    )
]


commit = os.environ.get("READTHEDOCS_GIT_COMMIT_HASH", "main")
code_url = "https://github.com/scikit-build/scikit-build-core/blob"


def linkcode_resolve(domain: str, info: dict[str, str]) -> str | None:
    if scikit_build_core is None:
        return None

    if domain != "py":
        return None

    mod = importlib.import_module(info["module"])
    if "." in info["fullname"]:
        objname, attrname = info["fullname"].split(".")
        obj = getattr(mod, objname)
        try:
            # object is a method of a class
            obj = getattr(obj, attrname)
        except AttributeError:
            # object is an attribute of a class
            return None
    else:
        obj = getattr(mod, info["fullname"])

    try:
        file = Path(inspect.getsourcefile(obj))
        lines = inspect.getsourcelines(obj)
    except TypeError:
        # e.g. object is a typing.Union
        return None
    try:
        mod = Path(inspect.getsourcefile(scikit_build_core)).parent
        file = file.relative_to(mod)
    except ValueError:
        return None
    start, end = lines[1], lines[1] + len(lines[0]) - 1

    return f"{code_url}/{commit}/src/scikit_build_core/{file}#L{start}-L{end}"
