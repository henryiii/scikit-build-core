from __future__ import annotations

__lazy_modules__ = {"contextlib", "platform", "typing", f"{__spec__.parent}"}

import contextlib
import dataclasses
import enum
import functools
import logging
import os
import platform
import sys
from collections.abc import Mapping
from typing import Any, Literal, NoReturn

from . import __version__

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Iterator

    from ._compat.typing import Self

    StrMapping = Mapping[str, "Style"]
else:
    StrMapping = Mapping

__all__ = [
    "LEVEL_VALUE",
    "ScikitBuildLogger",
    "Style",
    "logger",
    "raw_logger",
    "rich_error",
    "rich_print",
    "rich_warning",
]


def __dir__() -> list[str]:
    return __all__


raw_logger = logging.getLogger("scikit_build_core")


LEVEL_VALUE = {
    "CRITICAL": logging.CRITICAL,
    "ERROR": logging.ERROR,
    "WARNING": logging.WARNING,
    "INFO": logging.INFO,
    "DEBUG": logging.DEBUG,
    "NOTSET": logging.NOTSET,
}


class PlatformHelper:
    def __getattr__(self, name: str) -> Any:
        result = getattr(platform, name)
        return result() if callable(result) else result

    def __repr__(self) -> str:
        return repr(platform)


class FStringMessage:
    "This class captures a formatted string message and only produces it on demand."

    def __init__(self, fmt: str, *args: object, **kwargs: object) -> None:
        self.fmt = fmt
        self.args = args
        self.kwargs = kwargs

    def __str__(self) -> str:
        return self.fmt.format(*self.args, **self.kwargs)

    def __repr__(self) -> str:
        return (
            f"<FStringMessage {self.fmt!r} args={self.args!r} kwargs={self.kwargs!r}>"
        )


class ScikitBuildLogger:
    # pylint: disable-next=redefined-outer-name
    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def debug(self, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.debug(FStringMessage(msg, *args, **kwargs), stacklevel=2)

    def info(self, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.info(FStringMessage(msg, *args, **kwargs), stacklevel=2)

    def warning(self, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.warning(FStringMessage(msg, *args, **kwargs), stacklevel=2)

    def error(self, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.error(FStringMessage(msg, *args, **kwargs), stacklevel=2)

    def critical(self, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.critical(FStringMessage(msg, *args, **kwargs), stacklevel=2)

    def exception(self, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.exception(  # noqa: LOG004
            FStringMessage(msg, *args, **kwargs), stacklevel=2
        )

    def log(self, level: int, msg: str, *args: object, **kwargs: object) -> None:
        self.logger.log(level, FStringMessage(msg, *args, **kwargs), stacklevel=2)

    def setLevel(self, level: int) -> None:  # noqa: N802
        self.logger.setLevel(level)

    def addHandler(self, handler: logging.Handler) -> None:  # noqa: N802
        self.logger.addHandler(handler)


logger = ScikitBuildLogger(raw_logger)


def colors() -> bool:
    if "NO_COLOR" in os.environ:
        return False
    # Pip reroutes sys.stdout, so FORCE_COLOR is required there
    if os.environ.get("FORCE_COLOR", ""):
        return True
    # sys.stdout can be None (e.g. pythonw / embedded interpreters); avoid
    # AttributeError as well as ValueError: I/O operation on closed file.
    with contextlib.suppress(ValueError, AttributeError):
        # Assume sys.stderr is similar to sys.stdout
        isatty = sys.stdout.isatty()
        if isatty and not sys.platform.startswith("win"):
            return True
    return False


class Colors(enum.Enum):
    black = 0
    red = 1
    green = 2
    yellow = 3
    blue = 4
    magenta = 5
    cyan = 6
    white = 7
    default = 9


class Styles(enum.Enum):
    bold = 1
    italic = 3
    underline = 4
    reverse = 7
    reset = 0
    normal = 22


@dataclasses.dataclass(frozen=True)
class Style(StrMapping):
    color: bool = dataclasses.field(default_factory=colors)
    styles: tuple[int, ...] = dataclasses.field(default_factory=tuple)
    current: int = 0

    def __str__(self) -> str:
        styles = ";".join(str(x) for x in self.styles)
        return f"\33[{styles}m" if styles and self.color else ""

    @property
    def fg(self) -> Self:
        return dataclasses.replace(self, current=30)

    @property
    def bg(self) -> Self:
        return dataclasses.replace(self, current=40)

    @property
    def bold(self) -> Self:
        return dataclasses.replace(self, styles=(*self.styles, Styles.bold.value))

    @property
    def italic(self) -> Self:
        return dataclasses.replace(self, styles=(*self.styles, Styles.italic.value))

    @property
    def underline(self) -> Self:
        return dataclasses.replace(self, styles=(*self.styles, Styles.underline.value))

    @property
    def reverse(self) -> Self:
        return dataclasses.replace(self, styles=(*self.styles, Styles.reverse.value))

    @property
    def reset(self) -> Self:
        return dataclasses.replace(self, styles=(Styles.reset.value,), current=0)

    @property
    def normal(self) -> Self:
        return dataclasses.replace(self, styles=(*self.styles, Styles.normal.value))

    @property
    def black(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.black.value + (self.current or 30))
        )

    @property
    def red(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.red.value + (self.current or 30))
        )

    @property
    def green(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.green.value + (self.current or 30))
        )

    @property
    def yellow(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.yellow.value + (self.current or 30))
        )

    @property
    def blue(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.blue.value + (self.current or 30))
        )

    @property
    def magenta(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.magenta.value + (self.current or 30))
        )

    @property
    def cyan(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.cyan.value + (self.current or 30))
        )

    @property
    def white(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.white.value + (self.current or 30))
        )

    @property
    def default(self) -> Self:
        return dataclasses.replace(
            self, styles=(*self.styles, Colors.default.value + (self.current or 30))
        )

    _keys = (
        "bold",
        "italic",
        "underline",
        "reverse",
        "reset",
        "normal",
        "black",
        "red",
        "green",
        "yellow",
        "blue",
        "magenta",
        "cyan",
        "white",
        "default",
    )

    def __len__(self) -> int:
        return len(self._keys)

    def __getitem__(self, name: str) -> Self:
        return getattr(self, name)  # type: ignore[no-any-return]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)


_style = Style()
_nostyle = Style(color=False)


def rich_print(
    *args: object,
    file: object = None,
    sep: str = " ",
    end: str = "\n",
    color: Literal[
        "", "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"
    ] = "",
    **kwargs: object,
) -> None:
    """
    Print a message with style and useful common includes provided via formatting.

    This function will process every argument with the following formatting:

        - ``{__version__}``: The version of scikit-build-core.
        - ``{platform}``: The platform module.
        - ``{sys}``: The sys module.
        - Colors and styles.

    Any keyword arguments will be passed directly to the `str.format` method
    unless they conflict with the above. ``print`` arguments work as normal, and
    the output will be flushed.

    Each argument will clear the style afterwards if a style is applied. The
    ``color=`` argument will set a default color to apply to every argument, and
    is available to arguments as ``{color}``.
    """
    kwargs["color"] = _style[color] if color else ""

    args_1 = tuple(str(arg) for arg in args)
    args_1_gen = (
        arg.format(
            __version__=__version__,
            platform=PlatformHelper(),
            sys=sys,
            **_nostyle,
            **kwargs,
        )
        for arg in args_1
    )
    args_2_gen = (
        arg.format(
            __version__=__version__,
            platform=PlatformHelper(),
            sys=sys,
            **_style,
            **kwargs,
        )
        for arg in args_1
    )
    if color:
        args_2 = (f"{_style[color]}{new}{_style.reset}" for new in args_2_gen)
    else:
        args_2 = (
            new if new == orig else f"{new}{_style.reset}"
            for new, orig in zip(args_2_gen, args_1_gen, strict=True)
        )
    print(*args_2, flush=True, sep=sep, end=end, file=file)  # type: ignore[call-overload]


@functools.cache
def rich_warning(
    *args: str,
    color: Literal[
        "", "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"
    ] = "yellow",
    file: object = None,
    **kwargs: object,
) -> None:
    rich_print(
        "{bold.yellow}WARNING:",
        *args,
        color=color,
        file=file or sys.stderr,
        **kwargs,  # type: ignore[arg-type]
    )


def rich_error(
    *args: str,
    color: Literal[
        "", "black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"
    ] = "red",
    file: object = None,
    **kwargs: object,
) -> NoReturn:
    rich_print(
        "{bold.red}ERROR:",
        *args,
        color=color,
        file=file or sys.stderr,
        **kwargs,  # type: ignore[arg-type]
    )
    raise SystemExit(7)
