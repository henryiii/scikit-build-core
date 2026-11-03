from __future__ import annotations

__lazy_modules__ = {
    "ast",
    "inspect",
    "itertools",
    "packaging.specifiers",
    "packaging.version",
    "pathlib",
    "textwrap",
    "typing",
    f"{(__spec__.parent or '').rsplit('.', 1)[0]}.utils.typing",
}

import ast
import dataclasses
import inspect
import itertools
import textwrap
import typing
from pathlib import Path
from typing import Annotated, get_args, get_origin

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .. import __version__
from ..utils.typing import NoneType, is_union_type

TYPE_CHECKING = False

if TYPE_CHECKING:
    from collections.abc import Generator


__all__ = ["pull_docs"]


def __dir__() -> list[str]:
    return __all__


version_display = ".".join(__version__.split(".")[:2])


def _get_value(value: ast.expr) -> str:
    assert isinstance(value, ast.Constant)
    assert isinstance(value.value, str)
    return value.value


def pull_docs(dc: type[object]) -> dict[str, str]:
    """
    Pulls documentation from a dataclass.
    """
    t = ast.parse(inspect.getsource(dc))
    (obody,) = t.body
    assert isinstance(obody, ast.ClassDef)
    body = obody.body
    return {
        assign.target.id: textwrap.dedent(_get_value(expr.value)).strip()  # type: ignore[union-attr]
        for assign, expr in itertools.pairwise(body)
        if isinstance(assign, ast.AnnAssign) and isinstance(expr, ast.Expr)
    }


def _flat_expressible(field_type: typing.Any) -> bool:
    """
    Whether a field can be set through a flat source (``config-settings`` or a
    ``SKBUILD_*`` environment variable).

    Both sources reject arrays of tables (handled separately via the ``[]`` name
    marker) and can't round-trip nested mappings (e.g. a dict of dicts), so no
    flat key is advertised for those. Dicts of scalars (including
    ``cmake.define``) and lists of scalars are fine.
    """
    origin = get_origin(field_type)
    if origin is Annotated:
        return _flat_expressible(get_args(field_type)[0])
    if is_union_type(origin):
        return all(
            _flat_expressible(arg)
            for arg in get_args(field_type)
            if arg is not NoneType
        )
    if origin is dict:
        return get_origin(get_args(field_type)[1]) not in (dict, list)
    return True


@dataclasses.dataclass(frozen=True)
class DCDoc:
    name: str
    type: str
    default: str
    docs: str
    field: dataclasses.Field[typing.Any]
    deprecated: bool = False
    override_only: bool = False
    choices: tuple[str, ...] = ()

    def flat_expressible(self) -> bool:
        """
        Whether the option can be set via ``config-settings`` or an env var.

        Arrays of tables (``generate[]``) and nested mappings can only be set in
        ``pyproject.toml``, so the flat forms are skipped for them.
        """
        return "[]" not in self.name and _flat_expressible(self.field.type)


def sanitize_default_field(text: str) -> str:
    return text.replace("'", '"').replace("True", "true").replace("False", "false")


def is_optional(field: type) -> bool:
    return is_union_type(get_origin(field)) and NoneType in get_args(field)


def get_display_type(field_type: type | str) -> str:
    if isinstance(field_type, str):
        return field_type
    if is_optional(field_type):
        # Special case for optional, we just take the first part
        return get_display_type(get_args(field_type)[0])
    if is_union_type(get_origin(field_type)):
        return " | ".join(
            get_display_type(a) for a in get_args(field_type) if a is not NoneType
        )
    # Handle built-ins
    if get_origin(field_type) is dict:
        key_display = get_display_type(get_args(field_type)[0])
        val_display = get_display_type(get_args(field_type)[1])
        return f"dict[{key_display},{val_display}]"
    if get_origin(field_type) is list:
        return f"list[{get_display_type(get_args(field_type)[0])}]"
    # Handle other typing specials
    if get_origin(field_type) is typing.Literal:
        return " | ".join(f'"{x}"' for x in get_args(field_type))
    if get_origin(field_type) is Annotated:
        # Display the real inner type, not the annotation metadata (e.g.
        # ``Annotated[Dict[...], "EnvVar"]`` should show the dict, not "EnvVar").
        return get_display_type(get_args(field_type)[0])
    # Otherwise just get the formatted form of the `type` object
    return field_type.__name__


def get_choices(field_type: type | str) -> tuple[str, ...]:
    """
    Return the string choices for a ``Literal`` field, unwrapping ``Annotated``
    and ``Optional``. Empty if the field is not a string ``Literal``.
    """
    if isinstance(field_type, str):
        return ()
    if get_origin(field_type) is Annotated:
        return get_choices(get_args(field_type)[0])
    if is_optional(field_type):
        return get_choices(get_args(field_type)[0])
    if get_origin(field_type) is typing.Literal:
        args = get_args(field_type)
        if all(isinstance(a, str) for a in args):
            return args
    return ()


def mk_docs(dc: type[object], prefix: str = "") -> Generator[DCDoc, None, None]:
    """
    Makes documentation for a dataclass.
    """
    assert dataclasses.is_dataclass(dc)
    docs = pull_docs(dc)

    for field in dataclasses.fields(dc):
        field_type = field.type
        if dataclasses.is_dataclass(field_type) and isinstance(field_type, type):
            yield from mk_docs(field_type, prefix=f"{prefix}{field.name}.")
            continue

        if get_origin(field.type) is list:
            field_type = get_args(field.type)[0]
            if dataclasses.is_dataclass(field_type) and isinstance(field_type, type):
                yield from mk_docs(field_type, prefix=f"{prefix}{field.name}[].")
                continue

        if default_before_format := field.metadata.get("display_default", None):
            assert isinstance(default_before_format, str)
            default = default_before_format.format(
                version=version_display,
            )
        elif field.default is not dataclasses.MISSING and field.default is not None:
            default = repr(
                str(field.default)
                if isinstance(field.default, (Path, Version, SpecifierSet))
                else field.default
            )
        elif field.default_factory is not dataclasses.MISSING:
            default = repr(field.default_factory())
        else:
            default = '""'

        yield DCDoc(
            name=f"{prefix}{field.name}".replace("_", "-"),
            type=get_display_type(field.type),
            default=sanitize_default_field(default),
            docs=docs[field.name],
            field=field,
            deprecated=field.metadata.get("deprecated", False),
            override_only=field.metadata.get("override_only", False),
            choices=get_choices(field.type),
        )
