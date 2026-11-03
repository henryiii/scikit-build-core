from setuptools import find_packages, setup


def keep_runtime_files(cmake_manifest):
    return [path for path in cmake_manifest if path != "LICENSE"]


setup(
    name="cmake-example",
    version="0.0.1",
    cmake_source_dir=".",
    cmake_process_manifest_hook=keep_runtime_files,
    zip_safe=False,
    package_dir={"": "src"},
    packages=find_packages(),
    extras_require={"test": ["pytest>=6.0"]},
    python_requires=">=3.10",
    license_files=["LICENSE"],
)
