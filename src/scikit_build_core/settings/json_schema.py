from __future__ import annotations

__lazy_modules__ = {
    "dataclasses",
    "packaging.specifiers",
    "packaging.version",
    "pathlib",
    "typing",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}._compat.builtins",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.utils.typing",
    f"{__spec__.parent}.documentation",
}

import dataclasses
from pathlib import Path
from typing import Annotated, Any, Literal, get_args, get_origin

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .._compat.builtins import ExceptionGroup, add_note
from ..utils.typing import NoneType, is_union_type
from .documentation import pull_docs

__all__ = ["FailedConversionError", "convert_type", "to_json_schema"]


def __dir__() -> list[str]:
    return __all__


class FailedConversionError(TypeError):
    pass


def to_json_schema(dclass: type[Any], *, normalize_keys: bool) -> dict[str, Any]:
    assert dataclasses.is_dataclass(dclass)
    props = {}
    errs = []
    required = []
    for field in dataclasses.fields(dclass):
        field_type = field.type
        if dataclasses.is_dataclass(field.type) and isinstance(field_type, type):
            props[field.name] = to_json_schema(
                field_type, normalize_keys=normalize_keys
            )
            continue

        if get_origin(field.type) is Annotated:
            if get_args(field.type)[1] == "EnvVar":
                full = convert_type(
                    get_args(field.type)[0], normalize_keys=normalize_keys
                )
                types = full["patternProperties"][".+"]
                env_branch = {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["env"],
                    "properties": {
                        "env": {"type": "string", "minLength": 1},
                        "default": types,
                    },
                }
                # Flatten a nested oneOf (e.g. Union[str, bool, List[str]]) into
                # the combined oneOf instead of nesting oneOf inside oneOf. The
                # branches are mutually exclusive by JSON type, so this is
                # equivalent and more robust across validate_pyproject /
                # fastjsonschema versions.
                value_branches = types["oneOf"] if list(types) == ["oneOf"] else [types]
                full["patternProperties"][".+"] = {
                    "oneOf": [*value_branches, env_branch]
                }
                props[field.name] = full
                continue
            if get_args(field.type)[1] == "EnvTable":
                # Each value is a literal string or a table reading from another
                # environment variable, with an optional ``force`` overwrite.
                table_branch = {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "env": {"type": "string", "minLength": 1},
                        "default": {"type": "string"},
                        "force": {"type": "boolean", "default": False},
                    },
                }
                props[field.name] = {
                    "type": "object",
                    "patternProperties": {
                        ".+": {"oneOf": [{"type": "string"}, table_branch]}
                    },
                }
                continue
            msg = "Only EnvVar is supported for Annotated"
            raise FailedConversionError(msg)

        try:
            props[field.name] = convert_type(field.type, normalize_keys=normalize_keys)
        except FailedConversionError as err:
            add_note(err, f"Field: {field.name}")
            errs.append(err)
            continue

        if field.default is not dataclasses.MISSING and field.default is not None:
            props[field.name]["default"] = (
                str(field.default)
                if isinstance(field.default, (Version, Path, SpecifierSet))
                else field.default
            )

        if (
            field.default_factory is dataclasses.MISSING
            and field.default is dataclasses.MISSING
        ):
            # props keys are dash-normalized below when normalize_keys is set,
            # so the required names must be normalized the same way to stay
            # satisfiable.
            required.append(
                field.name.replace("_", "-") if normalize_keys else field.name
            )

    if errs:
        msg = f"Failed Conversion to JSON Schema on {dclass.__name__}"
        raise ExceptionGroup(msg, errs)

    docs = pull_docs(dclass)
    for field in dataclasses.fields(dclass):
        if field.name not in docs:
            continue
        props[field.name]["description"] = docs[field.name].split("\n", maxsplit=1)[0]
        if field.metadata.get("deprecated"):
            props[field.name]["deprecated"] = True
        if field.metadata.get("override_only"):
            props[field.name]["scikit-build:override-only"] = True

    if normalize_keys:
        props = {k.replace("_", "-"): v for k, v in props.items()}

    if required:
        return {
            "type": "object",
            "additionalProperties": False,
            "required": required,
            "properties": props,
        }

    return {"type": "object", "additionalProperties": False, "properties": props}


def convert_type(t: Any, *, normalize_keys: bool) -> dict[str, Any]:
    if dataclasses.is_dataclass(t) and isinstance(t, type):
        return to_json_schema(t, normalize_keys=normalize_keys)
    if t is str or t is Path or t is Version or t is SpecifierSet:
        return {"type": "string"}
    if t is bool:
        return {"type": "boolean"}
    origin = get_origin(t)
    args = get_args(t)
    if origin is list:
        assert len(args) == 1
        return {
            "type": "array",
            "items": convert_type(args[0], normalize_keys=normalize_keys),
        }
    if origin is dict:
        assert len(args) == 2
        assert args[0] is str
        if args[1] is Any:
            return {"type": "object"}
        return {
            "type": "object",
            "patternProperties": {
                ".+": convert_type(args[1], normalize_keys=normalize_keys)
            },
        }
    if is_union_type(origin):
        # Ignore optional
        if len(args) == 2 and any(a is NoneType for a in args):
            return convert_type(
                next(iter(a for a in args if a is not NoneType)),
                normalize_keys=normalize_keys,
            )
        return {
            "oneOf": [
                convert_type(a, normalize_keys=normalize_keys)
                for a in args
                if a is not NoneType
            ]
        }
    if origin is Literal:
        return {"enum": list(args)}
    if hasattr(t, "json_schema"):
        return convert_type(t.json_schema, normalize_keys=normalize_keys)

    msg = f"Cannot convert type {t} to JSON Schema"
    raise FailedConversionError(msg)
