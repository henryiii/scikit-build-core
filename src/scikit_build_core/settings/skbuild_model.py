import dataclasses
from typing import List, Optional

__all__ = [
    "ScikitBuildSettings",
    "NinjaSettings",
    "CMakeSettings",
    "LoggingSettings",
    "SDistSettings",
    "WheelSettings",
]


def __dir__() -> List[str]:
    return __all__


@dataclasses.dataclass
class NinjaSettings:
    #: The minimum version of Ninja to use. If Ninja is older than this, it will
    #: be upgraded via PyPI if possible. An empty string will disable this check.
    minimum_version: str = "1.5"

    #: If make is present, do not add ninja if missing.
    make_fallback: bool = True


@dataclasses.dataclass
class CMakeSettings:
    #: The minimum version of CMake to use. If CMake is older than this, it will
    #: be upgraded via PyPI if possible. An empty string will disable this check.
    minimum_version: str = "3.15"


@dataclasses.dataclass
class LoggingSettings:
    #: The logging level to display.
    level: str = "WARNING"


@dataclasses.dataclass
class SDistSettings:
    #: Files to include in the SDist even if they are skipped by default.
    include: List[str] = dataclasses.field(default_factory=list)

    #: Files to exclude from the SDist even if they are included by default.
    exclude: List[str] = dataclasses.field(default_factory=list)

    #: If set to True, try to build a reproducible distribution.
    #: SOURCE_DATE_EPOCH will be used for timestamps, or a fixed value if not set.
    reproducible: bool = True


@dataclasses.dataclass
class WheelSettings:
    #: A list of packages to auto-copy into the wheel. If this is None, it will
    #: default to the first of ``src/<package>`` or ``<package>`` if they exist.
    #: The prefix(s) will be stripped from the package name inside the wheel.
    packages: Optional[List[str]] = None

    #: The Python tags. The default (empty string) will use the default
    #: Python version. You can also set this to "cp37" to enable the CPython
    #: 3.7+ Stable ABI / Limited API (only on CPython and if the version is
    #: sufficient, otherwise this has no effect). Or you can set it to "py3"
    #: or "py2.py3" to ignore Python ABI compatibility. For the stable ABI,
    #: the CMake variable SKBUILD_SOABI will be set to abi3 on Unix-like systems
    #: (empty on Windows). FindPython doesn't have a way to target python3.dll
    #: instead of python3N.dll, so this is harder to use on Windows.
    #: The ABI tag is inferred from this tag.
    py_api: str = ""

    #: Fill out extra tags that are not required. This adds "x86_64" and "arm64"
    #: to the list of platforms when "universal2" is used, which helps older
    #: Pip's (before 21.0.1) find the correct wheel.
    expand_macos_universal_tags: bool = False


@dataclasses.dataclass
class ScikitBuildSettings:
    cmake: CMakeSettings = dataclasses.field(default_factory=CMakeSettings)
    ninja: NinjaSettings = dataclasses.field(default_factory=NinjaSettings)
    logging: LoggingSettings = dataclasses.field(default_factory=LoggingSettings)
    sdist: SDistSettings = dataclasses.field(default_factory=SDistSettings)
    wheel: WheelSettings = dataclasses.field(default_factory=WheelSettings)

    #: Strictly check all config options. If False, warnings will be
    #: printed for unknown options. If True, an error will be raised.
    strict_config: bool = True
