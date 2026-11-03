from setuptools import find_packages

from scikit_build_core.setuptools.wrapper import setup

setup(
    name="wrapper-classic-layout",
    version="0.0.1",
    cmake_source_dir=".",
    package_dir={"": "python"},
    packages=find_packages(where="python"),
    zip_safe=False,
    python_requires=">=3.10",
)
