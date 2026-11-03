from setuptools import find_packages, setup

setup(
    name="plugin-example",
    version="0.0.1",
    cmake_source_dir=".",
    cmake_install_dir="plugin_example",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    zip_safe=False,
    python_requires=">=3.10",
)
