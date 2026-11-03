from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

DIR = Path(__file__).parent.resolve()

UV = shutil.which("uv")

pytestmark = [
    pytest.mark.compile,
    pytest.mark.configure,
    pytest.mark.integration,
    pytest.mark.network,
    pytest.mark.virtualenv,
    pytest.mark.skipif(UV is None, reason="uv is not on PATH"),
]


def test_uv_workspace_editable_member(tmp_path: Path, pep518_wheelhouse: Path):
    """A scikit-build-core package as a uv workspace member.

    ``uv sync`` installs workspace members editable through the standard PEP
    660 hooks with build isolation; this drives that full path end-to-end and
    checks the redirect shim serves both the compiled module and live Python
    sources from the workspace checkout.
    """
    ws = tmp_path / "workspace"
    ws.joinpath("src/consumer").mkdir(parents=True)
    ws.joinpath("packages").mkdir()
    shutil.copytree(DIR / "packages/simplest_c", ws / "packages/simplest")

    ws.joinpath("pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [build-system]
            requires = ["scikit-build-core"]
            build-backend = "scikit_build_core.build"

            [project]
            name = "consumer"
            version = "0.1.0"
            requires-python = ">=3.10"
            dependencies = ["simplest"]

            [tool.scikit-build]
            wheel.cmake = false

            [tool.uv.sources]
            simplest = { workspace = true }

            [tool.uv.workspace]
            members = ["packages/*"]
            """
        )
    )
    ws.joinpath("src/consumer/__init__.py").write_text(
        textwrap.dedent(
            """\
            from simplest import square


            def negative_square(x):
                return -square(x)
            """
        )
    )

    env = os.environ.copy()
    # The test runner's venv must not leak into uv's project-environment
    # discovery, and a shared uv cache could serve a scikit-build-core wheel
    # from an earlier run.
    env.pop("VIRTUAL_ENV", None)
    env["UV_CACHE_DIR"] = str(tmp_path / "uv-cache")
    env["UV_PYTHON_DOWNLOADS"] = "never"
    assert UV is not None
    subprocess.run(
        [
            UV,
            "sync",
            "--no-index",
            f"--find-links={pep518_wheelhouse}",
            f"--python={sys.executable}",
        ],
        cwd=ws,
        env=env,
        check=True,
    )

    if os.name == "nt":
        venv_py = ws / ".venv/Scripts/python.exe"
    else:
        venv_py = ws / ".venv/bin/python"

    def execute(code: str) -> str:
        # cwd is outside the workspace so imports must resolve via the venv
        result = subprocess.run(
            [os.fspath(venv_py), "-c", code],
            check=True,
            capture_output=True,
            text=True,
            cwd=tmp_path,
        )
        return result.stdout.strip()

    assert execute("import consumer; print(consumer.negative_square(3.0))") == "-9.0"

    # Both members went through scikit-build-core's editable redirect, and the
    # per-package shims coexist in one environment
    platlib = Path(execute("import sysconfig; print(sysconfig.get_path('platlib'))"))
    assert list(platlib.glob("_editable_skbc_simplest.*"))
    assert list(platlib.glob("_editable_skbc_consumer.*"))

    # Python sources of the member are served live from the workspace checkout
    with ws.joinpath("packages/simplest/src/simplest/__init__.py").open("a") as f:
        f.write("\n\ndef added():\n    return 42\n")
    assert execute("import simplest; print(simplest.added())") == "42"
