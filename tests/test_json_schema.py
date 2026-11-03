from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version

from scikit_build_core.settings.json_schema import FailedConversionError, convert_type


def test_convert_str():
    assert convert_type(str, normalize_keys=False) == {"type": "string"}


def test_convert_str_or_bool():
    assert convert_type(str | bool, normalize_keys=False) == {
        "oneOf": [{"type": "string"}, {"type": "boolean"}]
    }


def test_convert_optional_str():
    assert convert_type(str | None, normalize_keys=False) == {"type": "string"}


def test_convert_path():
    assert convert_type(Path, normalize_keys=False) == {"type": "string"}


def test_convert_version():
    assert convert_type(Version, normalize_keys=False) == {"type": "string"}


def test_convert_list():
    assert convert_type(list[str], normalize_keys=False) == {
        "type": "array",
        "items": {"type": "string"},
    }
    assert convert_type(list[str | bool], normalize_keys=False) == {
        "type": "array",
        "items": {"oneOf": [{"type": "string"}, {"type": "boolean"}]},
    }


def test_convert_dict():
    assert convert_type(dict[str, str], normalize_keys=False) == {
        "type": "object",
        "patternProperties": {".+": {"type": "string"}},
    }
    assert convert_type(dict[str, dict[str, str]], normalize_keys=False) == {
        "type": "object",
        "patternProperties": {
            ".+": {"type": "object", "patternProperties": {".+": {"type": "string"}}}
        },
    }
    assert convert_type(dict[str, Any], normalize_keys=False) == {
        "type": "object",
    }


def test_convert_invalid():
    with pytest.raises(FailedConversionError):
        convert_type(object, normalize_keys=False)
