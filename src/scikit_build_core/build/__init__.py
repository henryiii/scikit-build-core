"""
This is the entry point for the build backend. Items in this module are designed for the build backend API.
"""

from __future__ import annotations

__lazy_modules__ = {f"{(__spec__.parent or '').rsplit('.', 1)[0]}._compat"}

import contextlib
import sys

from .._compat import tomllib

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Iterator
    from typing import Literal

__all__ = [
    "build_editable",
    "build_sdist",
    "build_wheel",
    "get_requires_for_build_editable",
    "get_requires_for_build_sdist",
    "get_requires_for_build_wheel",
]


@contextlib.contextmanager
def _exit_on_failed_live_process() -> Iterator[None]:
    """Translate a FailedLiveProcessError into a clean ``SystemExit(1)``."""
    from .._logging import rich_print
    from ..errors import FailedLiveProcessError

    try:
        yield
    except FailedLiveProcessError as err:
        sys.stdout.flush()
        rich_print("\n{bold}***", *err.args, color="red", file=sys.stderr)
        if err.msg:
            rich_print(err.msg)
        raise SystemExit(1) from None


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, list[str] | str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    from .wheel import _build_wheel_impl

    with _exit_on_failed_live_process():
        return _build_wheel_impl(
            wheel_directory,
            config_settings,
            metadata_directory,
            editable=False,
        ).wheel_filename


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, list[str] | str] | None = None,
    metadata_directory: str | None = None,
) -> str:
    from .wheel import _build_wheel_impl

    with _exit_on_failed_live_process():
        return _build_wheel_impl(
            wheel_directory,
            config_settings,
            metadata_directory,
            editable=True,
        ).wheel_filename


def _has_safe_metadata() -> bool:
    try:
        with open("pyproject.toml", "rb") as f:  # noqa: PTH123
            pyproject = tomllib.load(f)
    except FileNotFoundError:
        return True

    overrides = pyproject.get("tool", {}).get("scikit-build", {}).get("overrides", [])
    for override in overrides:
        if_override = override.get("if", {})
        if "failed" in if_override or "failed" in if_override.get("any", {}):
            return False

    return True


if _has_safe_metadata():

    def prepare_metadata_for_build_wheel(
        metadata_directory: str,
        config_settings: dict[str, list[str] | str] | None = None,
    ) -> str:
        """Prepare metadata for building a wheel. Does not build the wheel. Returns the dist-info directory."""
        from .wheel import _build_wheel_impl

        return _build_wheel_impl(
            None, config_settings, metadata_directory, editable=False
        ).wheel_filename  # actually returns the dist-info directory

    def prepare_metadata_for_build_editable(
        metadata_directory: str,
        config_settings: dict[str, list[str] | str] | None = None,
    ) -> str:
        """Prepare metadata for building a wheel. Does not build the wheel. Returns the dist-info directory."""

        from .wheel import _build_wheel_impl

        return _build_wheel_impl(
            None, config_settings, metadata_directory, editable=True
        ).wheel_filename  # actually returns the dist-info directory

    __all__ += [
        "prepare_metadata_for_build_editable",
        "prepare_metadata_for_build_wheel",
    ]


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, list[str] | str] | None = None,
) -> str:
    from .sdist import build_sdist as skbuild_build_sdist

    with _exit_on_failed_live_process():
        return skbuild_build_sdist(sdist_directory, config_settings)


def get_requires_for_build_sdist(
    config_settings: dict[str, str | list[str]] | None = None,
) -> list[str]:
    from ..builder.get_requires import GetRequires

    requires = GetRequires.from_config_settings(config_settings, state="sdist")

    # These are only injected if cmake is required for the SDist step
    cmake_requires = (
        [*requires.cmake(), *requires.ninja()] if requires.settings.sdist.cmake else []
    )

    return [
        *cmake_requires,
        *requires.dynamic_metadata(),
    ]


def _get_requires_for_build_wheel(
    config_settings: dict[str, str | list[str]] | None,
    state: Literal["wheel", "editable"],
) -> list[str]:
    from ..builder.get_requires import GetRequires

    requires = GetRequires.from_config_settings(config_settings, state=state)

    # These are only injected if cmake is required for the wheel step
    cmake_requires = (
        [*requires.cmake(), *requires.ninja()] if requires.settings.wheel.cmake else []
    )

    return [
        *cmake_requires,
        *requires.variants(),
        *requires.dynamic_metadata(),
    ]


def get_requires_for_build_wheel(
    config_settings: dict[str, str | list[str]] | None = None,
) -> list[str]:
    return _get_requires_for_build_wheel(config_settings, state="wheel")


def get_requires_for_build_editable(
    config_settings: dict[str, str | list[str]] | None = None,
) -> list[str]:
    return _get_requires_for_build_wheel(config_settings, state="editable")
