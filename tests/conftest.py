from __future__ import annotations

import contextlib
import dataclasses
import importlib.util
import os
import shutil
import subprocess
import sys
import sysconfig
import zipfile
from collections.abc import Iterable
from importlib import metadata
from pathlib import Path
from typing import Any, Literal, overload

import download_wheels
import packaging.tags
import packaging.utils
import pytest
import virtualenv as _virtualenv
from filelock import FileLock
from packaging.requirements import Requirement
from packaging.version import Version

if sys.version_info < (3, 11):
    import tomli as tomllib
else:
    import tomllib

from typing import TypeGuard

DIR = Path(__file__).parent.resolve()
BASE = DIR.parent

VIRTUALENV_VERSION = Version(metadata.version("virtualenv"))

UV = shutil.which("uv")


def _is_valid_wheel(wheel: Path) -> bool:
    if not zipfile.is_zipfile(wheel):
        return False
    try:
        _, _, _, tags = packaging.utils.parse_wheel_filename(wheel.name)
    except ValueError:
        return False
    supported = set(packaging.tags.sys_tags())
    return any(tag in supported for tag in tags)


def _clean_wheelhouse(wheelhouse: Path) -> None:
    for whl in wheelhouse.glob("*.whl"):
        if not _is_valid_wheel(whl):
            whl.unlink()
    for tmpf in wheelhouse.glob("*.whl.tmp"):
        tmpf.unlink()


def _newest_source_mtime() -> float:
    """Newest mtime among files that affect the built wheel.

    An editable install freezes ``importlib.metadata.version()`` at install
    time, while the real (hatch-vcs) version keeps advancing with every
    commit, so comparing version strings never matches and forces a rebuild
    every session. Comparing mtimes instead only rebuilds when the source
    actually changed.
    """
    paths = [BASE / "pyproject.toml", BASE / "src"]
    return max(
        p.stat().st_mtime
        for path in paths
        for p in ([path] if path.is_file() else path.rglob("*"))
        # hatch-vcs rewrites _version.py (and its compiled cache) in place on
        # every build, which would otherwise make the source look changed
        # right after building.
        if p.is_file() and p.name != "_version.py" and "__pycache__" not in p.parts
    )


@pytest.fixture(scope="session")
def pep518_wheelhouse(
    pytestconfig: pytest.Config, tmp_path_factory: pytest.TempPathFactory
) -> Path:
    wheelhouse = pytestconfig.cache.mkdir("wheelhouse")
    tmp_path = tmp_path_factory.mktemp("wheelhouse_tmp")

    # A single lock for all wheelhouse mutations prevents cross-lock races on
    # Windows where concurrent readers (zipfile.is_zipfile) and writers
    # (unlink/replace) on different locks would cause PermissionError (WinError 5).
    wheelhouse_lock = FileLock(wheelhouse / "wheels.lock")
    with wheelhouse_lock:
        # Only rebuild the scikit-build-core wheel when the source is newer
        # than the cached one; this avoids a redundant pip-wheel invocation
        # on every worker while still catching source changes between runs.
        cached = list(wheelhouse.glob("scikit_build_core-*.whl"))
        source_mtime = _newest_source_mtime()
        if not cached or min(whl.stat().st_mtime for whl in cached) < source_mtime:
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--wheel-dir",
                    f"{tmp_path}",
                    "--no-build-isolation",
                    f"{BASE}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            for wheel in tmp_path.glob("*.whl"):
                # Always replace: an uncommitted source edit keeps the same
                # (dirty) version, so a same-named cached wheel can be stale.
                # Copy to a sibling tmp and swap atomically; the lock keeps
                # readers out, so the swap is safe on Windows too.
                target = wheelhouse / wheel.name
                tmp_target = wheelhouse / f"{wheel.name}.tmp"
                shutil.copy(wheel, tmp_target)
                tmp_target.replace(target)

            # Remove stale scikit-build-core wheels that weren't just copied
            copied = {f.name for f in tmp_path.glob("scikit_build_core-*.whl")}
            for stale in wheelhouse.glob("scikit_build_core-*.whl"):
                if stale.name not in copied:
                    stale.unlink()

        # Clean up any invalid or orphaned wheels.  Because we hold the single
        # shared lock here, there are no concurrent readers to race against.
        _clean_wheelhouse(wheelhouse)

        if not all(
            any(_is_valid_wheel(whl) for whl in wheelhouse.glob(f"{p}*.whl"))
            for p in download_wheels.WHEELS
        ):
            download_wheels.prepare(wheelhouse)

            # Re-validate after downloading, in case a partially-written wheel
            # was cached from an interrupted run.
            _clean_wheelhouse(wheelhouse)

    return wheelhouse


class VEnv:
    def __init__(self, env_dir: Path, *, wheelhouse: Path | None = None) -> None:
        cmd = [str(env_dir), "--no-setuptools", "--activators", ""]
        if Version("20.31.0") > VIRTUALENV_VERSION:
            cmd.append("--no-wheel")
        result = _virtualenv.cli_run(cmd, setup_logging=False)
        self.wheelhouse = wheelhouse
        self.executable = Path(result.creator.exe)
        self.env_dir = env_dir.resolve()
        self.platlib = Path(
            self.execute("import sysconfig; print(sysconfig.get_path('platlib'))")
        )
        self.purelib = Path(
            self.execute("import sysconfig; print(sysconfig.get_path('purelib'))")
        )

    @overload
    def run(self, *args: str, capture: Literal[True]) -> str: ...

    @overload
    def run(self, *args: str, capture: Literal[False] = ...) -> None: ...

    def run(self, *args: str, capture: bool = False) -> str | None:
        __tracebackhide__ = True
        env = os.environ.copy()
        paths = {str(self.executable.parent)}
        env["PATH"] = os.pathsep.join([*paths, env["PATH"]])
        env["VIRTUAL_ENV"] = str(self.env_dir)
        env["PIP_DISABLE_PIP_VERSION_CHECK"] = "ON"
        if self.wheelhouse is not None:
            env["PIP_NO_INDEX"] = "ON"
            env["PIP_FIND_LINKS"] = str(self.wheelhouse)

        str_args = [os.fspath(a) for a in args]

        # Windows does not make a python shortcut in venv
        if str_args[0] in {"python", "python3"}:
            str_args[0] = str(self.executable)

        if capture:
            result = subprocess.run(
                str_args,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                print(result.stdout, file=sys.stdout)
                print(result.stderr, file=sys.stderr)
                print("FAILED RUN:", *str_args, file=sys.stderr)
                raise SystemExit(result.returncode)
            return result.stdout.strip()

        result_bytes = subprocess.run(
            str_args,
            check=False,
            env=env,
        )
        if result_bytes.returncode != 0:
            print("FAILED RUN:", *str_args, file=sys.stderr)
            raise SystemExit(result_bytes.returncode)
        return None

    def execute(self, command: str) -> str:
        return self.run(str(self.executable), "-c", command, capture=True)

    def module(self, *args: str) -> None:
        return self.run(str(self.executable), "-m", *args)

    def install(
        self,
        *args: str,
        isolated: bool = True,
        installer: Literal["auto", "pip", "uv"] = "auto",
    ) -> None:
        """Install into the venv.

        The default installer ("auto") uses uv when available, since it is
        much faster. Installs that are themselves under test (``.`` /
        ``-e .``) must pin ``installer="pip"`` so the frontend being
        exercised doesn't depend on what happens to be on PATH.
        """
        if installer == "auto":
            installer = "pip" if UV is None else "uv"
        isolated_flags = [] if isolated else ["--no-build-isolation"]
        if installer == "uv":
            if UV is None:
                msg = "installer='uv' requested but uv is not on PATH"
                raise RuntimeError(msg)
            cmd = [UV, "pip", "install", f"--python={self.executable}"]
            if self.wheelhouse is not None:
                cmd += ["--no-index", f"--find-links={self.wheelhouse}"]
            self.run(*cmd, *isolated_flags, *args)
        else:
            self.module("pip", "install", *isolated_flags, *args)

    def prepare_no_build_isolation(self) -> None:
        if not self.wheelhouse:
            msg = "Wheelhouse was not setup."
            raise ValueError(msg)

        ninja = [
            "ninja" for f in self.wheelhouse.iterdir() if f.name.startswith("ninja-")
        ]
        cmake = [
            "cmake" for f in self.wheelhouse.iterdir() if f.name.startswith("cmake-")
        ]

        self.install("pip>23")
        self.install("scikit-build-core", *ninja, *cmake)


@pytest.fixture
def isolated(tmp_path: Path, pep518_wheelhouse: Path) -> VEnv:
    """Isolated virtual environment.

    To control build isolation, see :py:func:`isolate`
    """
    path = tmp_path / "venv"
    return VEnv(path, wheelhouse=pep518_wheelhouse)


@pytest.fixture
def virtualenv(tmp_path: Path) -> VEnv:
    path = tmp_path / "venv"
    return VEnv(path)


@dataclasses.dataclass(frozen=True)
class PackageInfo:
    name: str
    workdir: Path
    sdist_hash: str | None = None
    sdist_dated_hash: str | None = None

    @property
    def source_date_epoch(self) -> str:
        return "12345"


def process_package(
    package: PackageInfo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pkg_src = DIR / "packages" / package.name
    assert pkg_src.exists()
    shutil.copytree(pkg_src, package.workdir, dirs_exist_ok=True)
    monkeypatch.chdir(package.workdir)


@pytest.fixture
def package(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> PackageInfo:
    """Get the test package.

    Parameterize this fixture with the package name in the tests/packages directory.
    (Use ``indirect=True`` to pass the parameterization value to the fixture instead of
    directly to the test function.)
    https://docs.pytest.org/en/stable/example/parametrize.html#indirect-parametrization
    """
    pkg_name = request.param
    assert isinstance(pkg_name, str)
    package = PackageInfo(pkg_name, tmp_path_factory.mktemp("pkg"))
    assert (DIR / "packages" / package.name).exists()
    process_package(package, monkeypatch)
    return package


@pytest.fixture
def multiple_packages(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> list[PackageInfo]:
    package_names = request.param
    assert isinstance(package_names, Iterable)
    packages = []
    for pkg_name in package_names:
        pkg = PackageInfo(pkg_name, tmp_path_factory.mktemp("pkg"))
        process_package(pkg, monkeypatch)
        packages.append(pkg)
    monkeypatch.chdir(tmp_path_factory.getbasetemp())
    return packages


@pytest.fixture
def package_simple_pyproject_ext(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> PackageInfo:
    package = PackageInfo(
        "simple_pyproject_ext",
        tmp_path_factory.mktemp("pkg"),
        "5265ac433b68b351c3258f16dbe1f8d41efb217f26ee72c0c2a29dd2ac747cb2",
        "fcbd2fdfe47ef226b54a94851b0c56b60747f4fcc83097a25d728d33fc6b3c6c",
    )
    process_package(package, monkeypatch)
    return package


@dataclasses.dataclass(frozen=True)
class Isolate:
    """Selection for build isolation."""

    state: bool
    flags: list[str]


@pytest.fixture(params=[True, False], ids=["isolated", "not_isolated"])
def isolate(request: pytest.FixtureRequest, isolated: VEnv) -> Isolate:
    """Control build isolation.

    For an isolated virtual environment, see :py:func:`isolated`
    """
    isolate_request = request.param
    assert isinstance(isolate_request, bool)
    if not isolate_request:
        isolated.prepare_no_build_isolation()
    flags = []
    if not isolate_request:
        flags.append("--no-build-isolation")
    return Isolate(
        state=isolate_request,
        flags=flags,
    )


@dataclasses.dataclass(frozen=True)
class Editable:
    mode: Literal["redirect", "inplace"] | None
    config_settings: list[str]

    @property
    def flags(self) -> list[str]:
        if not self.mode:
            return self.config_settings
        return [*self.config_settings, "-e"]


def is_editable_mode(
    maybe_mode: str | None,
) -> TypeGuard[Literal["redirect", "inplace"]]:
    return maybe_mode in {"redirect", "inplace"}


@pytest.fixture(params=[pytest.param(None, id="not_editable"), "redirect", "inplace"])
def editable(request: pytest.FixtureRequest) -> Editable:
    editable_mode = request.param
    assert editable_mode is None or is_editable_mode(editable_mode)
    config_settings = []
    if editable_mode:
        config_settings.append(f"--config-settings=editable.mode={editable_mode}")
        if editable_mode != "inplace":
            build_dir = "build/{wheel_tag}"
            config_settings.append(f"--config-settings=build-dir={build_dir}")
    return Editable(
        mode=editable_mode,
        config_settings=config_settings,
    )


def which_mock(name: str) -> str | None:
    if name in {"ninja", "ninja-build", "cmake3", "samu", "gmake", "make"}:
        return None
    if name == "cmake":
        return "cmake/path"
    return None


@pytest.fixture
def protect_get_requires(fp, monkeypatch):
    """
    Protect get_requires from actually calling anything variable during tests.
    """
    # This needs to be passed due to packaging.tags 22 extra checks if macos 10.16 is reported
    fp.pass_command([sys.executable, fp.any()])
    monkeypatch.setattr(shutil, "which", which_mock)
    monkeypatch.delenv("CMAKE_GENERATOR", raising=False)

    orig_find_spec = importlib.util.find_spec

    def find_spec(name: str, package: str | None = None) -> Any:
        if name in {"cmake", "ninja"}:
            return None
        return orig_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", find_spec)


@pytest.fixture(autouse=True)
def _stub_macos_arch_probe(request: pytest.FixtureRequest) -> None:
    """
    ``program_search.compute_timeout`` shells out to ``lipo`` on macOS arm64
    (when ``CI`` is unset) to detect x86 binaries. Tests that fake subprocesses
    with the ``fp`` fixture don't register that call, so it raises
    ``ProcessNotRegisteredError`` locally (CI passes only because the ``CI`` env
    var short-circuits the probe). Stub it out for fake-subprocess tests; real
    tests still exercise the genuine ``lipo`` path.
    """
    if "fp" not in request.fixturenames:
        return

    from scikit_build_core import program_search

    monkeypatch = request.getfixturevalue("monkeypatch")
    monkeypatch.setattr(program_search, "_macos_binary_is_x86", lambda _path: False)
    program_search.compute_timeout.cache_clear()


@pytest.fixture
def pybind11():
    return pytest.importorskip("pybind11")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        # Ensure all tests using virtualenv are marked as such
        if "virtualenv" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.virtualenv)
        if "isolated" in getattr(item, "fixturenames", ()):
            item.add_marker(pytest.mark.virtualenv)
            item.add_marker(pytest.mark.isolated)
            item.add_marker(pytest.mark.network)


def pytest_report_header() -> str:
    with BASE.joinpath("pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)
    project = pyproject.get("project", {})

    pkgs = project.get("dependencies", [])
    pkgs += [p for ps in project.get("optional-dependencies", {}).values() for p in ps]
    if "name" in project:
        pkgs.append(project["name"])
    interesting_packages = {Requirement(p).name for p in pkgs}
    interesting_packages |= {"pip", "hatch-fancy-pypi-readme", "setuptools-scm"}

    valid = []
    for package in sorted(interesting_packages):
        with contextlib.suppress(ModuleNotFoundError):
            valid.append(f"{package}=={metadata.version(package)}")
    reqs = " ".join(valid)
    lines = [
        f"installed packages of interest: {reqs}",
        f"sysconfig platform: {sysconfig.get_platform()}",
    ]
    return "\n".join(lines)


@pytest.fixture(autouse=True)
def _clear_caches() -> Iterable[None]:
    """Keep process-wide caches from leaking between tests that fake their input."""
    from scikit_build_core._compat.importlib.metadata import all_entry_points
    from scikit_build_core._logging import rich_warning
    from scikit_build_core.builder._known_wheels import is_known_platform

    caches = (all_entry_points, is_known_platform, rich_warning)
    for cached in caches:
        cached.cache_clear()
    yield
    for cached in caches:
        cached.cache_clear()
