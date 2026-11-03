from setuptools import find_packages

from scikit_build_core.setuptools.wrapper import setup

setup(
    name="wrapper-example",
    version="0.0.1",
    cmake_source_dir=".",
    cmake_install_dir="src/wrapper_example",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    zip_safe=False,
    python_requires=">=3.10",
)
