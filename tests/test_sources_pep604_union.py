# mypy: ignore-errors
from typing import Union, get_origin

from scikit_build_core.utils.typing import is_union_type, process_union


class TestUnionTypeDetection:
    def test_typing_union_recognized(self):
        assert is_union_type(Union)

    def test_non_union_types_rejected(self):
        assert not is_union_type(str)
        assert not is_union_type(int)
        assert not is_union_type(list)
        assert not is_union_type(dict)

    def test_none_not_recognized_as_union(self):
        assert not is_union_type(None)

    def test_pep604_union_type_recognized(self):
        import types

        assert is_union_type(types.UnionType)


class TestProcessUnion:
    def test_typing_union_processed(self):
        typing_union = Union[list, str]  # noqa: UP007
        result = process_union(typing_union)
        assert result is not None
        assert get_origin(result) is Union or result in (list, str)

    def test_optional_unwrapped(self):
        from typing import Optional

        optional_str = Optional[str]  # noqa: UP045
        result = process_union(optional_str)
        assert result is str

    def test_non_union_passthrough(self):
        assert process_union(str) is str
        assert process_union(int) is int
        assert process_union(bool) is bool

    def test_pep604_union_processed(self):
        pep604_union = list[str] | str
        result = process_union(pep604_union)
        assert result is not None

    def test_pep604_optional_unwrapped(self):
        pep604_optional = str | None
        result = process_union(pep604_optional)
        assert result is str
