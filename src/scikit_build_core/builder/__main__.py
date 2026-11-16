from __future__ import annotations

__lazy_modules__ = {
    "argparse",
    "pathlib",
    "scikit_build_core",
    "scikit_build_core._logging",
    "scikit_build_core.builder",
    "scikit_build_core.builder.get_requires",
    "scikit_build_core.builder.sysconfig",
    "scikit_build_core.builder.wheel_tag",
    "scikit_build_core.program_search",
}

import argparse
import sys
from pathlib import Path

from scikit_build_core import __version__
from scikit_build_core._logging import rich_print
from scikit_build_core.builder import sysconfig, wheel_tag
from scikit_build_core.builder.get_requires import GetRequires
from scikit_build_core.builder.sysconfig import info_print as ip_sysconfig
from scikit_build_core.builder.wheel_tag import WheelTag
from scikit_build_core.program_search import info_print as ip_program_search

__all__ = ["main"]


def __dir__() -> list[str]:
    return __all__


def main_info(_args: argparse.Namespace | None = None, /) -> None:
    rich_print(
        f"{{bold}}Scikit-build-core {__version__}{{normal}} on Python {sys.version}"
    )

    ip_sysconfig(color="green")

    rich_print(f"{{bold.blue}}Default Wheel Tag:{{normal}} {WheelTag.compute_best([])}")
    rich_print(
        "{blue} - Note: use {bold}scikit-build builder wheel-tag -h{normal} for further options"
    )

    if Path("pyproject.toml").is_file():
        req = GetRequires.from_config_settings(None)
        all_req = [
            *req.cmake(),
            *req.ninja(),
            *req.dynamic_metadata(),
            *req.variants(),
        ]
        rich_print(f"{{bold.red}}Get Requires:{{normal}} {all_req!r}")

    ip_program_search(color="magenta")


def populate_parser(parser: argparse.ArgumentParser, /) -> None:
    """Add the ``builder`` subcommands to an existing parser."""
    parser.set_defaults(func=main_info)
    subparsers = parser.add_subparsers(help="Commands")
    wheel_tag_parser = subparsers.add_parser(
        "wheel-tag",
        help="Get the computed wheel tag for the current environment",
        description="Get the computed wheel tag for the current environment.",
        allow_abbrev=False,
    )
    wheel_tag.populate_parser(wheel_tag_parser)
    sysconfig_parser = subparsers.add_parser(
        "sysconfig",
        help="Print information about the Python environment",
        description="Print information about the Python environment.",
        allow_abbrev=False,
    )
    sysconfig.populate_parser(sysconfig_parser)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scikit_build_core.builder",
        allow_abbrev=False,
        description="Info about the system and build environment.",
    )
    populate_parser(parser)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
