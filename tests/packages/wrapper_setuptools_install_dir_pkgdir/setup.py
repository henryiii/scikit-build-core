from scikit_build_core.setuptools.wrapper import setup

# Per-package package_dir mapping (as opposed to the root "" -> "src" form):
# the editable source root must resolve to src/wrapper_pkgdir, not "." (which
# would create a junk ./wrapper_pkgdir directory).
setup(
    name="wrapper-pkgdir",
    version="0.0.1",
    cmake_source_dir=".",
    cmake_install_dir="src/wrapper_pkgdir",
    package_dir={"wrapper_pkgdir": "src/wrapper_pkgdir"},
    packages=["wrapper_pkgdir"],
    zip_safe=False,
    python_requires=">=3.10",
)
