# pylint: disable=duplicate-code

__lazy_modules__ = {
    "cattrs",
    "cattrs.preconf.json",
    "collections.abc",
    "json",
    f"{__spec__.parent}.model.cache",
    f"{__spec__.parent}.model.cmakefiles",
    f"{__spec__.parent}.model.codemodel",
    f"{__spec__.parent}.model.directory",
    f"{__spec__.parent}.model.index",
    f"{__spec__.parent}.model.toolchains",
}

import builtins
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import cattrs
import cattrs.preconf.json

from .model.cache import Cache
from .model.cmakefiles import CMakeFiles
from .model.codemodel import CodeModel, Directory, Target
from .model.directory import InstallPath
from .model.index import Index, Reply
from .model.toolchains import Toolchains

T = TypeVar("T")

__all__ = ["load_reply_dir", "make_converter"]


def to_path(path: str, _: type[Path]) -> Path:
    return Path(path)


def make_converter(base_dir: Path) -> cattrs.preconf.json.JsonConverter:
    converter = cattrs.preconf.json.make_converter()
    converter.register_structure_hook(Path, to_path)

    st_hook = cattrs.gen.make_dict_structure_fn(
        Reply,
        converter,
        codemodel_v2=cattrs.gen.override(rename="codemodel-v2"),
        cache_v2=cattrs.gen.override(rename="cache-v2"),
        cmakefiles_v1=cattrs.gen.override(rename="cmakeFiles-v1"),
        toolchains_v1=cattrs.gen.override(rename="toolchains-v1"),
    )
    converter.register_structure_hook(Reply, st_hook)

    ip_hook = cattrs.gen.make_dict_structure_fn(
        InstallPath,
        converter,
        from_=cattrs.gen.override(rename="from"),
    )
    converter.register_structure_hook(InstallPath, ip_hook)
    converter.register_structure_hook(
        Path | InstallPath,
        lambda v, _: (
            Path(v) if isinstance(v, str) else converter.structure(v, InstallPath)
        ),
    )

    def from_json_file(with_path: dict[str, Any], t: type[T]) -> T:
        # An error reply (e.g. an object kind unsupported by the running CMake)
        # has no "jsonFile" to follow; structure the inline dict instead, as the
        # built-in converter does.
        if with_path.get("jsonFile") is None:
            return converter.structure_attrs_fromdict(with_path, t)
        path = base_dir / Path(with_path["jsonFile"])
        raw = json.loads(path.read_text(encoding="utf-8"))
        # Keep members only present on the reference, like directoryIndex and
        # projectIndex on codemodel target entries
        raw.update(with_path)
        return converter.structure_attrs_fromdict(raw, t)

    converter.register_structure_hook(CodeModel, from_json_file)
    converter.register_structure_hook(Target, from_json_file)
    converter.register_structure_hook(Cache, from_json_file)
    converter.register_structure_hook(CMakeFiles, from_json_file)
    converter.register_structure_hook(Toolchains, from_json_file)
    converter.register_structure_hook(Directory, from_json_file)
    return converter


def load_reply_dir(reply_dir: Path) -> Index:
    converter = make_converter(reply_dir)
    indexes = sorted(reply_dir.glob("index-*"))
    if not indexes:
        msg = f"index file not found in {reply_dir}"
        raise IndexError(msg)
    index_file = indexes[-1]
    return converter.loads(index_file.read_text("utf-8"), Index)


if __name__ == "__main__":
    import argparse

    rich_print: Callable[[object], None]
    try:
        from rich import print as rich_print
    except ModuleNotFoundError:
        rich_print = builtins.print

    parser = argparse.ArgumentParser(
        allow_abbrev=False,
        description="This runs cattrs (required) instead of the built-in converter, for comparison.",
    )
    parser.add_argument("reply_dir", type=Path, help="Path to the reply directory")
    args = parser.parse_args()

    reply = Path(args.reply_dir)
    rich_print(load_reply_dir(reply))
