import dataclasses
import re
from pathlib import Path
from typing import Any, Literal

import pytest
from packaging.version import Version

from scikit_build_core._compat.builtins import ExceptionGroup
from scikit_build_core.settings.sources import (
    ConfSource,
    EnvSource,
    SourceChain,
    TOMLSource,
)


@dataclasses.dataclass
class SettingChecker:
    zero: Path
    one: str
    two: int
    three: list[str]
    four: list[int] = dataclasses.field(default_factory=list)
    five: str = "empty"
    six: Path = Path("empty")
    seven: int | None = None
    eight: dict[str, str | bool] = dataclasses.field(default_factory=dict)
    nine: dict[str, int] = dataclasses.field(default_factory=dict)
    literal: Literal["one", "two", "three"] = "one"
    # TOML only
    ten: dict[str, Any] = dataclasses.field(default_factory=dict)
    eleven: list[str] | dict[str, str] | None = None


def test_empty(monkeypatch):
    monkeypatch.setenv("SKB_ZERO", "zero")
    monkeypatch.setenv("SKB_ONE", "one")
    monkeypatch.setenv("SKB_TWO", "2")
    monkeypatch.setenv("SKB_THREE", "three")

    sources = SourceChain(
        EnvSource("SKB"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two == 2
    assert settings.three == ["three"]
    assert settings.four == []
    assert settings.five == "empty"
    assert settings.six == Path("empty")
    assert settings.seven is None
    assert settings.eight == {}
    assert settings.nine == {}
    assert settings.literal == "one"


def test_env(monkeypatch):
    monkeypatch.setenv("SKBUILD_ZERO", "zero")
    monkeypatch.setenv("SKBUILD_ONE", "one")
    monkeypatch.setenv("SKBUILD_TWO", "2")
    monkeypatch.setenv("SKBUILD_THREE", "three")
    monkeypatch.setenv("SKBUILD_FOUR", "4")
    monkeypatch.setenv("SKBUILD_FIVE", "five")
    monkeypatch.setenv("SKBUILD_SIX", "six")
    monkeypatch.setenv("SKBUILD_SEVEN", "7")
    monkeypatch.setenv("SKBUILD_EIGHT", "thing=8;thought=9")
    monkeypatch.setenv("SKBUILD_NINE", "thing=8")
    monkeypatch.setenv("SKBUILD_ELEVEN", "one;two")
    monkeypatch.setenv("SKBUILD_LITERAL", "two")

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two == 2
    assert settings.three == ["three"]
    assert settings.four == [4]
    assert settings.five == "five"
    assert settings.six == Path("six")
    assert settings.seven == 7
    assert settings.eight == {"thing": "8", "thought": "9"}
    assert settings.nine == {"thing": 8}
    assert settings.eleven == ["one", "two"]
    assert settings.literal == "two"


def test_env_union(monkeypatch):
    monkeypatch.setenv("SKBUILD_ZERO", "zero")
    monkeypatch.setenv("SKBUILD_ONE", "one")
    monkeypatch.setenv("SKBUILD_TWO", "2")
    monkeypatch.setenv("SKBUILD_THREE", "three")
    monkeypatch.setenv("SKBUILD_ELEVEN", "a=one;b=two")

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)

    assert settings.eleven == {"a": "one", "b": "two"}


def test_conf():
    config_settings: dict[str, str | list[str]] = {
        "zero": "zero",
        "one": "one",
        "two": "2",
        "three": ["three"],
        "four": ["4"],
        "five": "five",
        "six": "six",
        "seven": "7",
        "eight.foo": "one",
        "eight.bar": "two",
        "nine.thing": "8",
        "eleven": ["one", "two"],
        "literal": "three",
    }

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings=config_settings),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two == 2
    assert settings.three == ["three"]
    assert settings.four == [4]
    assert settings.five == "five"
    assert settings.six == Path("six")
    assert settings.seven == 7
    assert settings.eight == {"foo": "one", "bar": "two"}
    assert settings.nine == {"thing": 8}
    assert settings.literal == "three"


def test_conf_union_str_list():
    # pip/uv/build pass a plain string for ``-Celeven=src/a``; it should be
    # split like a list, matching EnvSource and the plain-list branch.
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={
                "zero": "zero",
                "one": "one",
                "two": "2",
                "three": ["three"],
                "eleven": "src/a",
            }
        ),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)
    assert settings.eleven == ["src/a"]


def test_conf_union_str_list_multiple():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={
                "zero": "zero",
                "one": "one",
                "two": "2",
                "three": ["three"],
                "eleven": "src/a;src/b",
            }
        ),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)
    assert settings.eleven == ["src/a", "src/b"]


def test_conf_union_str_dict():
    # A plain string with ``=`` should be parsed as a dict, matching EnvSource.
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={
                "zero": "zero",
                "one": "one",
                "two": "2",
                "three": ["three"],
                "eleven": "a=one;b=two",
            }
        ),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingChecker)
    assert settings.eleven == {"a": "one", "b": "two"}


def test_conf_dict_wrong_type_raises():
    # A scalar reaching the dict branch (e.g. ``-Cmetadata.version.provider=x``
    # where the field is Dict[str, Dict[str, str]]) should raise a clear
    # TypeError, not an AssertionError (which vanishes under python -O).
    with pytest.raises(TypeError, match="Expected"):
        ConfSource.convert("x", dict[str, dict[str, str]])


def test_toml():
    toml_settings = {
        "zero": "zero",
        "one": "one",
        "two": 2,
        "three": ["three"],
        "four": [4],
        "five": "five",
        "six": "six",
        "seven": 7,
        "eight": {"one": "one", "two": "two", "bool": False},
        "nine": {"thing": 8},
        "ten": {"a": {"b": 3}},
        "eleven": ["one", "two"],
        "literal": "three",
    }

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings=toml_settings),
    )
    settings = sources.convert_target(SettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two == 2
    assert settings.three == ["three"]
    assert settings.four == [4]
    assert settings.five == "five"
    assert settings.six == Path("six")
    assert settings.seven == 7
    assert settings.eight == {"one": "one", "two": "two", "bool": False}
    assert settings.nine == {"thing": 8}
    assert settings.ten == {"a": {"b": 3}}
    assert settings.eleven == ["one", "two"]
    assert settings.literal == "three"


def test_toml_union():
    toml_settings = {
        "zero": "zero",
        "one": "one",
        "two": 2,
        "three": ["three"],
        "eleven": {"a": "one", "b": "two"},
    }

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings=toml_settings),
    )
    settings = sources.convert_target(SettingChecker)

    assert settings.eleven == {"a": "one", "b": "two"}


def test_all_names():
    keys = [x.name for x in dataclasses.fields(SettingChecker)]

    envame = [f"SKBUILD_{x.upper()}" for x in keys]
    assert list(EnvSource("SKBUILD").all_option_names(SettingChecker)) == envame

    assert list(ConfSource(settings={}).all_option_names(SettingChecker)) == keys
    skkeys = [f"skbuild.{x}" for x in keys]
    assert (
        list(ConfSource("skbuild", settings={}).all_option_names(SettingChecker))
        == skkeys
    )

    assert list(TOMLSource(settings={}).all_option_names(SettingChecker)) == keys
    assert (
        list(TOMLSource("skbuild", settings={}).all_option_names(SettingChecker))
        == skkeys
    )


@dataclasses.dataclass
class NestedSettingChecker:
    zero: Path
    one: str
    two: SettingChecker
    three: int = 3


def test_env_nested(monkeypatch):
    monkeypatch.setenv("SKBUILD_ZERO", "zero")
    monkeypatch.setenv("SKBUILD_ONE", "one")
    monkeypatch.setenv("SKBUILD_TWO_ZERO", "zero")
    monkeypatch.setenv("SKBUILD_TWO_ONE", "one")
    monkeypatch.setenv("SKBUILD_TWO_TWO", "2")
    monkeypatch.setenv("SKBUILD_TWO_THREE", "three")
    monkeypatch.setenv("SKBUILD_TWO_FOUR", "4")

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(NestedSettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two.zero == Path("zero")
    assert settings.two.one == "one"
    assert settings.two.two == 2
    assert settings.two.three == ["three"]
    assert settings.two.four == [4]
    assert settings.two.five == "empty"
    assert settings.two.six == Path("empty")
    assert settings.three == 3


def test_conf_nested():
    config_settings: dict[str, str | list[str]] = {
        "zero": "zero",
        "one": "one",
        "two.zero": "zero",
        "two.one": "one",
        "two.two": "2",
        "two.three": ["three"],
        "two.four": ["4"],
    }

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings=config_settings),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(NestedSettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two.zero == Path("zero")
    assert settings.two.one == "one"
    assert settings.two.two == 2
    assert settings.two.three == ["three"]
    assert settings.two.four == [4]
    assert settings.two.five == "empty"
    assert settings.two.six == Path("empty")
    assert settings.three == 3


def test_toml_nested():
    toml_settings = {
        "zero": "zero",
        "one": "one",
        "two": {
            "zero": "zero",
            "one": "one",
            "two": 2,
            "three": ["three"],
            "four": [4],
        },
    }

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings=toml_settings),
    )
    settings = sources.convert_target(NestedSettingChecker)

    assert settings.zero == Path("zero")
    assert settings.one == "one"
    assert settings.two.zero == Path("zero")
    assert settings.two.one == "one"
    assert settings.two.two == 2
    assert settings.two.three == ["three"]
    assert settings.two.four == [4]
    assert settings.two.five == "empty"
    assert settings.two.six == Path("empty")
    assert settings.three == 3


def test_all_names_nested():
    keys_two = [x.name for x in dataclasses.fields(SettingChecker)]
    ikeys = [["zero"], ["one"], *[["two", k] for k in keys_two], ["three"]]

    envame = [f"SKBUILD_{'_'.join(x).upper()}" for x in ikeys]
    assert list(EnvSource("SKBUILD").all_option_names(NestedSettingChecker)) == envame

    keys = [".".join(x) for x in ikeys]
    assert list(ConfSource(settings={}).all_option_names(NestedSettingChecker)) == keys
    skkeys = [f"skbuild.{x}" for x in keys]
    assert (
        list(ConfSource("skbuild", settings={}).all_option_names(NestedSettingChecker))
        == skkeys
    )

    assert list(TOMLSource(settings={}).all_option_names(NestedSettingChecker)) == keys
    assert (
        list(TOMLSource("skbuild", settings={}).all_option_names(NestedSettingChecker))
        == skkeys
    )


@dataclasses.dataclass
class SettingBools:
    false: bool = False
    true: bool = True


def test_env_var_bools_empty(monkeypatch):
    monkeypatch.setenv("SKBUILD_FALSE", "")
    monkeypatch.setenv("SKBUILD_TRUE", "")

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )
    settings = sources.convert_target(SettingBools)

    assert not settings.false
    assert settings.true


@pytest.mark.parametrize(
    ("truthy", "falsey"), [("1", "0"), ("true", "false"), ("yes", "no"), ("on", "off")]
)
def test_env_var_bools(monkeypatch, truthy, falsey):
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )

    monkeypatch.setenv("SKBUILD_FALSE", truthy)
    monkeypatch.setenv("SKBUILD_TRUE", falsey)

    settings = sources.convert_target(SettingBools)

    assert settings.false
    assert not settings.true


def test_conf_settings_bools():
    sources = SourceChain(
        ConfSource(settings={"false": True, "true": False}),
    )
    settings = sources.convert_target(SettingBools)

    assert settings.false
    assert not settings.true


@dataclasses.dataclass
class SettingLists:
    list0: list[str] = dataclasses.field(default_factory=list)
    list1: list[str] = dataclasses.field(default_factory=list)
    list2: list[str] = dataclasses.field(default_factory=list)
    list3: list[str] = dataclasses.field(default_factory=list)
    list4: list[str] = dataclasses.field(default_factory=list)


def test_lists(monkeypatch):
    monkeypatch.setenv("SKBUILD_LIST1", "one;two;three")

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={"list2": ["one", "two", "three"], "list3": "one;two;three"}
        ),
        TOMLSource(settings={"list4": ["one", "two", "three"]}),
    )
    settings = sources.convert_target(SettingLists)

    assert settings.list0 == []
    assert settings.list1 == ["one", "two", "three"]
    assert settings.list2 == ["one", "two", "three"]
    assert settings.list3 == ["one", "two", "three"]
    assert settings.list4 == ["one", "two", "three"]


@dataclasses.dataclass
class SettingListsOptional:
    list0: list[str] | None = None
    list1: list[str] | None = None
    list2: list[str] | None = None
    list3: list[str] | None = None
    list4: list[str] | None = None


def test_lists_optional(monkeypatch):
    monkeypatch.setenv("SKBUILD_LIST1", "one;two;three")

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={"list2": ["one", "two", "three"], "list3": "one;two;three"}
        ),
        TOMLSource(settings={"list4": ["one", "two", "three"]}),
    )
    settings = sources.convert_target(SettingListsOptional)

    assert settings.list0 is None
    assert settings.list1 == ["one", "two", "three"]
    assert settings.list2 == ["one", "two", "three"]
    assert settings.list3 == ["one", "two", "three"]
    assert settings.list4 == ["one", "two", "three"]


@pytest.mark.parametrize(
    "prefixes", [(), ("x",), ("ab", "cd"), ("x", "other")], ids=".".join
)
def test_missing_opts_conf(prefixes):
    settings = {
        "one": "one",
        "missing": "missing",
        "two.one": "one",
        "two.missing": "missing",
        "other.missing": "missing",
    }

    settings = {".".join([*prefixes, k]): v for k, v in settings.items()}
    print(settings)

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(*prefixes, settings=settings),
        TOMLSource(settings={}),
    )
    answer = ["missing", "two.missing", "other"]
    answer = [".".join([*prefixes, k]) for k in answer]
    assert list(sources.unrecognized_options(NestedSettingChecker)) == answer


def test_unrecognized_conf_under_scalar():
    # A key nested under a scalar field (``one.extra``) is bogus and must be
    # reported, not silently accepted.
    settings = {
        "one": "one",
        "one.extra": "x",
        "two.literal": "two",
    }
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings=settings),
        TOMLSource(settings={}),
    )
    assert list(sources.unrecognized_options(NestedSettingChecker)) == ["one.extra"]


def test_unrecognized_conf_scalar_to_dict_field():
    # A scalar ``-C`` assignment to a dict-valued field (``two.nine=A=1``
    # instead of ``two.nine.A=1``) can never be consumed, so it must be
    # reported rather than silently dropped.
    settings = {
        "one": "one",
        "two.nine": "A=1",
    }
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings=settings),
        TOMLSource(settings={}),
    )
    assert list(sources.unrecognized_options(NestedSettingChecker)) == ["two.nine"]


def test_unrecognized_conf_under_dict_of_dict():
    # Keys nested arbitrarily deep under a dict-typed field (``two.ten`` is
    # Dict[str, Any]) are free-form and must be accepted (no TypeError, no
    # spurious report).
    settings = {
        "one": "one",
        "two.literal": "two",
        "two.ten.foo": "x",
        "two.ten.foo.bar": "y",
    }
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings=settings),
        TOMLSource(settings={}),
    )
    assert list(sources.unrecognized_options(NestedSettingChecker)) == []


def test_ignore_conf():
    settings = {
        "one": "one",
        "missing": "missing",
        "two.one": "one",
        "two.missing": "missing",
        "other.missing": "missing",
    }

    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings=settings, verify=False),
        TOMLSource(settings={}),
    )

    assert list(sources.unrecognized_options(NestedSettingChecker)) == []


def test_missing_opts_toml():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(
            "tool",
            settings={
                "tool": {
                    "one": "one",
                    "missing": "missing",
                    "two": {"one": "one", "missing": "missing"},
                    "other": {"missing": "missing"},
                },
                "things": {"thing": "x"},
            },
        ),
    )

    assert list(sources.unrecognized_options(NestedSettingChecker)) == [
        "tool.missing",
        "tool.two.missing",
        "tool.other",
    ]


@dataclasses.dataclass
class SettingsOverride:
    dict0: dict[str, str] = dataclasses.field(default_factory=dict)
    dict1: dict[str, int] | None = None
    dict2: dict[str, str] | None = None


def test_override():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={"dict0.one": "one", "dict0.two": "two", "dict1.other": "2"}
        ),
        TOMLSource(settings={"dict0": {"two": "TWO", "three": "THREE"}, "dict2": {}}),
    )

    settings = sources.convert_target(SettingsOverride)

    assert settings.dict0 == {"one": "one", "two": "two", "three": "THREE"}
    assert settings.dict1 == {"other": 2}
    assert settings.dict2 == {}


@dataclasses.dataclass
class SettingVersion:
    first_req: Version = Version("1.2")
    first_opt: Version | None = None
    second_req: Version = Version("1.2")
    second_opt: Version | None = None
    third_req: Version = Version("1.2")
    third_opt: Version | None = None
    fourth_req: Version = Version("1.2")
    fourth_opt: Version | None = None


def test_versions(monkeypatch):
    monkeypatch.setenv("SKBUILD_SECOND_REQ", "2.3")
    monkeypatch.setenv("SKBUILD_SECOND_OPT", "2.4")
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={"third-req": "3.4", "third-opt": "3.5"}),
        TOMLSource(settings={"fourth-req": "4.5", "fourth-opt": "4.6"}),
    )

    settings = sources.convert_target(SettingVersion)

    assert settings.first_req == Version("1.2")
    assert settings.first_opt is None
    assert settings.second_req == Version("2.3")
    assert settings.second_opt == Version("2.4")
    assert settings.third_req == Version("3.4")
    assert settings.third_opt == Version("3.5")
    assert settings.fourth_req == Version("4.5")
    assert settings.fourth_opt == Version("4.6")


@dataclasses.dataclass
class SettingLiteral:
    literal: Literal["one", "two", "three"]
    optional: Literal["foo", "bar"] | None = None


def test_literal_failure_empty():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )

    with pytest.raises(ValueError, match="Missing value for 'literal'"):  # noqa: PT012
        try:
            sources.convert_target(SettingLiteral)
        except ExceptionGroup as e:
            assert len(e.exceptions) == 1  # noqa: PT017
            raise e.exceptions[0] from None


def test_literal_failure_not_contained():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={"literal": "four"}),
        TOMLSource(settings={}),
    )

    with pytest.raises(  # noqa: PT012
        TypeError, match=re.escape("'four' not in ('one', 'two', 'three')")
    ):
        try:
            sources.convert_target(SettingLiteral)
        except ExceptionGroup as e:
            assert len(e.exceptions) == 1  # noqa: PT017
            raise e.exceptions[0] from None


def test_literal_failure_not_contained_optional():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={"literal": "three"}),
        TOMLSource(settings={"optional": "five"}),
    )

    with pytest.raises(  # noqa: PT012
        TypeError, match=re.escape("'five' not in ('foo', 'bar')")
    ):
        try:
            sources.convert_target(SettingLiteral)
        except ExceptionGroup as e:
            assert len(e.exceptions) == 1  # noqa: PT017
            raise e.exceptions[0] from None


@dataclasses.dataclass
class ArraySetting:
    required: str
    optional: str | None = None


@dataclasses.dataclass
class ArraySettings:
    array: list[ArraySetting] = dataclasses.field(default_factory=list)


def test_empty_array():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )

    settings = sources.convert_target(ArraySettings)

    assert settings.array == []


def test_toml_required():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={"array": [{"optional": "2"}]}),
    )

    with pytest.raises(ExceptionGroup):
        sources.convert_target(ArraySettings)


def test_toml_array():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(
            settings={
                "array": [{"required": "one"}, {"required": "two", "optional": "2"}]
            }
        ),
    )

    settings = sources.convert_target(ArraySettings)

    assert settings.array == [ArraySetting("one"), ArraySetting("two", "2")]


def test_env_array_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SKBUILD_ARRAY", "one")
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(settings={}),
        TOMLSource(settings={}),
    )

    with pytest.raises(ExceptionGroup):
        sources.convert_target(ArraySettings)


def test_config_array_error():
    sources = SourceChain(
        EnvSource("SKBUILD"),
        ConfSource(
            settings={
                "array": [{"required": "one"}, {"required": "two", "optional": "2"}]  # type: ignore[list-item]
            }
        ),
        TOMLSource(settings={}),
    )

    with pytest.raises(ExceptionGroup):
        sources.convert_target(ArraySettings)
