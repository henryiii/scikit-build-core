__lazy_modules__ = {
    "argparse",
    "dataclasses",
    "json",
    "pathlib",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._compat.builtins",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.utils.typing",
    f"{__spec__.parent}.model.cache",
    f"{__spec__.parent}.model.cmakefiles",
    f"{__spec__.parent}.model.codemodel",
    f"{__spec__.parent}.model.index",
    f"{__spec__.parent}.model.toolchains",
}

import argparse
import builtins
import dataclasses
import json
import typing
from pathlib import Path
from typing import Any, TypeVar, get_args, get_origin

from .._compat.builtins import ExceptionGroup, add_note
from ..utils.typing import (
    get_target_raw_type,
    is_union_type,
    process_union,
)
from .model.cache import Cache
from .model.cmakefiles import CMakeFiles
from .model.codemodel import CodeModel, Directory, Target
from .model.index import Index
from .model.toolchains import Toolchains

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["load_reply_dir"]


def __dir__() -> list[str]:
    return __all__


T = TypeVar("T")

InputDict = dict[str, Any]


class Converter:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def load(self) -> Index:
        """
        Load the newest index.json file and return the Index object.
        """
        # max() would raise ValueError, not IndexError, when there is no index
        index_file = sorted(self.base_dir.glob("index-*"))[-1]  # noqa: FURB192
        return self.make_class(self._read_json(index_file), Index)

    def _read_json(self, path: Path) -> Any:
        """
        Read a JSON file, wrapping decode errors in an ExceptionGroup.
        """
        with path.open(encoding="utf-8") as f:
            try:
                return json.load(f)
            except ValueError as err:
                # JSONDecodeError and UnicodeDecodeError are both ValueErrors
                msg = f"Failed to read {path}"
                raise ExceptionGroup(msg, [err]) from None

    def make_class(self, data: InputDict, target: type[T]) -> T:
        """
        Convert a dict to a dataclass. Automatically load a few nested jsonFile classes.

        Every conversion failure is raised as an ExceptionGroup.
        """
        msg = f"Failed converting {target}"
        if not isinstance(data, dict):
            err = TypeError(f"Expected a dict, got {type(data).__name__}: {data!r}")
            raise ExceptionGroup(msg, [err])

        if (
            target in {CodeModel, Target, Cache, CMakeFiles, Toolchains, Directory}
            and data.get("jsonFile") is not None
        ):
            file_data = self._read_json(self.base_dir.joinpath(data["jsonFile"]))
            if not isinstance(file_data, dict):
                err = TypeError(f"Expected a dict in {data['jsonFile']}")
                raise ExceptionGroup(msg, [err])
            # Keep members only present on the reference, like directoryIndex
            # and projectIndex on codemodel target entries
            data = {**file_data, **data}

        input_dict: dict[str, Any] = {}
        exceptions: list[Exception] = []

        # We don't have DataclassInstance exposed in typing yet
        for field in dataclasses.fields(target):  # type: ignore[arg-type]
            # A trailing underscore escapes a reserved word, like "from_"
            json_field = (
                field.name.rstrip("_")
                .replace("_v", "-v")
                .replace("cmakefiles", "cmakeFiles")
            )
            if json_field in data:
                field_type = field.type
                try:
                    input_dict[field.name] = self._convert_any(
                        data[json_field], field_type
                    )
                except (TypeError, ValueError) as err:
                    add_note(
                        err,
                        f"Failed to convert field {field.name!r} of type {field_type}",
                    )
                    exceptions.append(err)
                except ExceptionGroup as err:
                    exceptions.append(err)

        if exceptions:
            raise ExceptionGroup(msg, exceptions)

        try:
            return target(**input_dict)
        except TypeError as err:
            # Missing required fields
            raise ExceptionGroup(msg, [err]) from None

    @typing.overload
    def _convert_any(self, item: Any, target: type[T]) -> T: ...
    @typing.overload
    def _convert_any(self, item: Any, target: Any) -> Any: ...

    def _convert_any(self, item: Any, target: type[T] | Any) -> Any:
        target = process_union(target)
        if dataclasses.is_dataclass(target) and isinstance(target, type):
            # We don't have DataclassInstance exposed in typing yet
            return self.make_class(item, target)
        raw_target = get_target_raw_type(target)
        # For generic Unions we try each type one at a time. We first match the
        # shape of the item against the candidate, so that e.g. ``str(<dict>)``
        # cannot shadow a dataclass member in ``Union[str, Paths]``: a dict-like
        # item must go to a dataclass member, and any other item to a
        # non-dataclass member.
        if is_union_type(raw_target):
            last_err: Exception = TypeError(f"No member of {target} matched {item!r}")
            for maybe_target in get_args(target):
                sub_target = process_union(maybe_target)
                is_dataclass = dataclasses.is_dataclass(sub_target) and isinstance(
                    sub_target, type
                )
                if isinstance(item, dict) != is_dataclass:
                    continue
                try:
                    return self._convert_any(item, maybe_target)
                except (ExceptionGroup, TypeError, ValueError) as err:
                    last_err = err
                    continue
            raise last_err

        origin = get_origin(target)
        if origin is list:
            return [self._convert_any(i, get_args(target)[0]) for i in item]

        return target(item)


def load_reply_dir(path: Path) -> Index:
    return Converter(path).load()


def main_reply(args: argparse.Namespace, /) -> None:
    rich_print: Callable[[object], None]
    try:
        from rich import print as rich_print
    except ModuleNotFoundError:
        rich_print = builtins.print

    reply = Path(args.reply_dir)
    rich_print(load_reply_dir(reply))


def populate_parser(parser: argparse.ArgumentParser, /) -> None:
    """Add the ``reply`` argument to an existing parser."""
    parser.add_argument("reply_dir", type=Path, help="Path to the reply directory")
    parser.set_defaults(func=main_reply)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="python -m scikit_build_core.file_api.reply",
        allow_abbrev=False,
        description="Read a query written out to a build directory.",
    )
    populate_parser(parser)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
