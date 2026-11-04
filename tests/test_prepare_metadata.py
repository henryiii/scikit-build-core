from __future__ import annotations

import dataclasses
import sys
import textwrap
import types
from pathlib import Path
from typing import Any

import pytest
from packaging.version import Version

from scikit_build_core.build import (
    prepare_metadata_for_build_editable,
    prepare_metadata_for_build_wheel,
)
from scikit_build_core.build.metadata import get_standard_metadata
from scikit_build_core.settings.skbuild_model import ScikitBuildSettings


@pytest.mark.parametrize("package", ["simplest_c"], indirect=True)
@pytest.mark.usefixtures("package")
@pytest.mark.parametrize("editable", [True, False], ids=["editable", "wheel"])
def test_prepare_metadata_for_build(fp, editable):
    # Old versions of packaging call mac_ver via subprocess
    fp.pass_command([sys.executable, fp.any()])
    fp.pass_command([fp.program("cmake"), "-E", "capabilities"])
    fp.pass_command([fp.program("cmake3"), "-E", "capabilities"])

    if editable:
        assert (
            prepare_metadata_for_build_editable("simple") == "simplest-0.0.1.dist-info"
        )
    else:
        assert prepare_metadata_for_build_wheel("simple") == "simplest-0.0.1.dist-info"

    with Path("simple/simplest-0.0.1.dist-info").joinpath("METADATA").open() as f:
        metadata = f.read()
    assert (
        textwrap.dedent(
            """\
        Metadata-Version: 2.2
        Name: simplest
        Version: 0.0.1"""
        )
        == metadata.strip()
    )

    assert len(list(Path("simple/simplest-0.0.1.dist-info").iterdir())) == 2
    assert len(list(Path("simple").iterdir())) == 1


def test_multiline_description():
    with pytest.raises(ValueError, match="one line summary"):
        get_standard_metadata(
            pyproject_dict={
                "project": {
                    "name": "hello",
                    "version": "1.1.1",
                    "description": "One\nTwo",
                }
            },
            settings=ScikitBuildSettings(),
        )

    with pytest.raises(ValueError, match="one line summary"):
        get_standard_metadata(
            pyproject_dict={
                "project": {
                    "name": "hello",
                    "version": "1.1.1",
                    "description": "One\nTwo",
                }
            },
            settings=ScikitBuildSettings(minimum_version=Version("0.9")),
        )

    get_standard_metadata(
        pyproject_dict={
            "project": {"name": "hello", "version": "1.1.1", "description": "One\nTwo"}
        },
        settings=ScikitBuildSettings(minimum_version=Version("0.8")),
    )


def test_raw_version_keeps_leading_zeros():
    metadata = get_standard_metadata(
        pyproject_dict={"project": {"name": "hello", "version": "2024.01.05"}},
        settings=ScikitBuildSettings(),
    )
    assert str(metadata.version) == "2024.1.5"
    assert metadata.raw_version == "2024.01.05"
    assert "Version: 2024.01.05" in str(metadata.as_rfc822())
    assert metadata.as_json()["version"] == "2024.01.05"

    # Older minimum versions keep the normalized form for reproducibility
    metadata = get_standard_metadata(
        pyproject_dict={"project": {"name": "hello", "version": "2024.01.05"}},
        settings=ScikitBuildSettings(minimum_version=Version("1.0")),
    )
    assert metadata.raw_version is None
    assert "Version: 2024.1.5" in str(metadata.as_rfc822())


def test_raw_version_strips_whitespace():
    metadata = get_standard_metadata(
        pyproject_dict={"project": {"name": "hello", "version": "  2024.01.05\n"}},
        settings=ScikitBuildSettings(),
    )
    assert metadata.raw_version == "2024.01.05"
    assert "Version: 2024.01.05" in str(metadata.as_rfc822())


def test_license_normalization():
    pytest.importorskip("packaging.licenses")
    metadata = get_standard_metadata(
        pyproject_dict={
            "project": {"name": "hello", "version": "1.1.1", "license": "ApacHE-2.0"}
        },
        settings=ScikitBuildSettings(),
    )
    assert metadata.license == "Apache-2.0"


VARIANT_TABLE = """
[variant.default-priorities]
namespace = ["cpu"]
[variant.providers.cpu]
requires = ["cpu-variant-provider"]
[variant.variants.cpu]
cpu.abi = ["cp313"]
[variant.variants.bad]
cpu.abi = ["cp999"]
[variant.variants.boom]
cpu.abi = ["boom"]
"""


@pytest.fixture
def fake_variantlib(fp, monkeypatch: pytest.MonkeyPatch) -> None:
    fp.pass_command([sys.executable, fp.any()])
    fp.pass_command([fp.program("cmake"), "-E", "capabilities"])
    fp.pass_command([fp.program("cmake3"), "-E", "capabilities"])

    variantlib: Any = types.ModuleType("variantlib")
    variantlib.__path__ = []  # mark as a package so submodule imports resolve
    variantlib_api: Any = types.ModuleType("variantlib.api")
    variantlib_errors: Any = types.ModuleType("variantlib.errors")
    variantlib_pyproject: Any = types.ModuleType("variantlib.pyproject_toml")

    class ValidationError(Exception):
        pass

    class PluginError(Exception):
        pass

    @dataclasses.dataclass(frozen=True, order=True)
    class VariantProperty:
        namespace: str
        feature: str
        value: str

        def to_str(self) -> str:
            return f"{self.namespace} :: {self.feature} :: {self.value}"

    class VariantDescription:
        def __init__(self, properties, label="") -> None:
            self.properties = sorted(properties)
            self.label = label

    class VariantPyProjectToml:
        def __init__(self, pyproject) -> None:
            self.pyproject = pyproject
            self.namespace_priorities = ["cpu"]
            self.variants = {
                label: VariantDescription(
                    [
                        VariantProperty(ns, feat, val)
                        for ns, feats in props.items()
                        for feat, vals in feats.items()
                        for val in vals
                    ],
                    label=label,
                )
                for label, props in pyproject["variant"].get("variants", {}).items()
            }

        def get_variant_desc(self, label):
            if label == "null":
                return VariantDescription([], label)
            return self.variants.get(label)

    # Fake plugin: the only valid property is "cpu :: abi :: cp313"
    def validate_variant(variant, variant_info):
        _ = variant_info
        if any(prop.to_str() == "cpu :: abi :: boom" for prop in variant.properties):
            msg = "Plugin invocation failed: KeyError: {plugin_api}"
            raise PluginError(msg)
        return types.SimpleNamespace(
            invalid_properties=[
                prop
                for prop in variant.properties
                if prop.to_str() != "cpu :: abi :: cp313"
            ],
            unknown_properties=[],
            multi_value_violations=frozenset(),
        )

    def make_variant_dist_info(variant, *, variant_info):
        _ = variant_info
        raw = ",".join(prop.to_str() for prop in variant.properties)
        return f"label={variant.label};properties={raw}"

    variantlib_api.make_variant_dist_info = make_variant_dist_info
    variantlib_api.validate_variant = validate_variant
    variantlib_errors.ValidationError = ValidationError
    variantlib_errors.PluginError = PluginError
    variantlib_pyproject.VariantPyProjectToml = VariantPyProjectToml

    monkeypatch.setitem(sys.modules, "variantlib", variantlib)
    monkeypatch.setitem(sys.modules, "variantlib.api", variantlib_api)
    monkeypatch.setitem(sys.modules, "variantlib.errors", variantlib_errors)
    monkeypatch.setitem(sys.modules, "variantlib.pyproject_toml", variantlib_pyproject)


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        pytest.param("cpu", "label=cpu;properties=cpu :: abi :: cp313", id="cpu"),
        pytest.param("null", "label=null;properties=", id="null"),
    ],
)
@pytest.mark.usefixtures("package_simple_pyproject_ext", "fake_variantlib")
def test_prepare_metadata_for_build_wheel_variant(tmp_path, label, expected):
    with Path("pyproject.toml").open("a", encoding="utf-8") as f:
        f.write(VARIANT_TABLE)

    mddir = tmp_path / "dist"
    mddir.mkdir()
    out = prepare_metadata_for_build_wheel(
        str(mddir), {"experimental": "true", "variant-label": label}
    )

    assert out == "cmake_example-0.0.1.dist-info"
    assert (mddir / out / "variant.json").read_text() == expected


@pytest.mark.parametrize(
    ("table", "label", "expected"),
    [
        pytest.param(False, "null", ["[variant] table"], id="null-without-table"),
        pytest.param(
            True,
            "missing",
            ["[variant.variants.missing]"],
            id="label-not-in-table",
        ),
        pytest.param(
            True,
            "bad",
            ["cpu :: abi :: cp999", "not supported"],
            id="invalid-property",
        ),
        pytest.param(True, "boom", ["KeyError: {plugin_api}"], id="plugin-error"),
    ],
)
@pytest.mark.usefixtures("package_simple_pyproject_ext", "fake_variantlib")
def test_prepare_metadata_variant_errors(tmp_path, capsys, table, label, expected):
    if table:
        with Path("pyproject.toml").open("a", encoding="utf-8") as f:
            f.write(VARIANT_TABLE)

    mddir = tmp_path / "dist"
    mddir.mkdir()
    with pytest.raises(SystemExit):
        prepare_metadata_for_build_wheel(
            str(mddir), {"experimental": "true", "variant-label": label}
        )
    err = capsys.readouterr().err
    for text in expected:
        assert text in err
