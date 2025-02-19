from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import shutil
import subprocess
import sys
import sysconfig
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

from packaging.version import Version

from . import __version__
from ._logging import logger
from ._shutil import Run
from .errors import (
    CMakeConfigError,
    CMakeNotFoundError,
    CMakeVersionError,
    FailedLiveProcessError,
)
from .program_search import Program, best_program, get_cmake_program, get_cmake_programs

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Mapping, Sequence

    from packaging.specifiers import SpecifierSet

    from ._compat.typing import Self

__all__ = ["CMake", "CMaker"]


def __dir__() -> list[str]:
    return __all__


DIR = Path(__file__).parent.resolve()


@dataclasses.dataclass(frozen=True)
class CMake:
    version: Version
    cmake_path: Path

    @classmethod
    def default_search(
        cls,
        *,
        version: SpecifierSet | None = None,
        module: bool = True,
        env: Mapping[str, Any] | None = None,
    ) -> Self:
        env = env or {}
        cmake_executable = env.get("CMAKE_EXECUTABLE", "")
        candidates: Iterable[Program] = (
            [get_cmake_program(Path(cmake_executable))]
            if cmake_executable
            else get_cmake_programs(module=module)
        )
        cmake_program = best_program(candidates, version=version)

        if cmake_program is None:
            msg = f"Could not find CMake with version {version}"
            raise CMakeNotFoundError(msg)
        if cmake_program.version is None:
            msg = "CMake version undetermined @ {program.path}"
            raise CMakeNotFoundError(msg)

        return cls(version=cmake_program.version, cmake_path=cmake_program.path)

    def __fspath__(self) -> str:
        return os.fspath(self.cmake_path)


@dataclasses.dataclass
class CMaker:
    cmake: CMake
    source_dir: Path
    build_dir: Path
    build_type: str
    module_dirs: list[Path] = dataclasses.field(default_factory=list)
    prefix_dirs: list[Path] = dataclasses.field(default_factory=list)
    init_cache_file: Path = dataclasses.field(init=False, default=Path())
    env: dict[str, str] = dataclasses.field(init=False, default_factory=os.environ.copy)
    single_config: bool = not sysconfig.get_platform().startswith("win")

    def __post_init__(self) -> None:
        self.init_cache_file = self.build_dir / "CMakeInit.txt"
        source_dir = self.source_dir.resolve()

        if not self.source_dir.is_dir():
            msg = f"source directory {self.source_dir} does not exist"
            raise CMakeConfigError(msg)

        self.build_dir.mkdir(parents=True, exist_ok=True)
        if not self.build_dir.is_dir():
            msg = f"build directory {self.build_dir} must be a (creatable) directory"
            raise CMakeConfigError(msg)

        skbuild_info = self.build_dir / ".skbuild-info.json"
        stale = False

        info: dict[str, str] = {}
        with contextlib.suppress(FileNotFoundError), skbuild_info.open(
            "r", encoding="utf-8"
        ) as f:
            info = json.load(f)

        if info:
            # If building via SDist, this could be pre-filled
            cached_source_dir = Path(info["source_dir"])
            if cached_source_dir != source_dir:
                logger.warning(
                    "Original src {} != {}, clearing cache",
                    cached_source_dir,
                    source_dir,
                )
                stale = True

            # Isolated environments can cause this
            cached_skbuild_dir = Path(info["skbuild_path"])
            if cached_skbuild_dir != DIR:
                logger.info(
                    "New isolated environment {} -> {}, clearing cache",
                    cached_skbuild_dir,
                    DIR,
                )
                stale = True

        # Not using --fresh here, not just due to CMake 3.24+, but also just in
        # case it triggers an extra FetchContent pull in CMake 3.30+
        if stale:
            # Python 3.8+ can use missing_ok=True
            with contextlib.suppress(FileNotFoundError):
                self.build_dir.joinpath("CMakeCache.txt").unlink()
            shutil.rmtree(self.build_dir.joinpath("CMakeFiles"), ignore_errors=True)

        with skbuild_info.open("w", encoding="utf-8") as f:
            json.dump(self._info_dict(), f, indent=2)

    def _info_dict(self) -> dict[str, str]:
        """
        Produce an information dict about the current run that can be stored in a json file.
        """
        return {
            "source_dir": os.fspath(self.source_dir.resolve()),
            "build_dir": os.fspath(self.build_dir.resolve()),
            "cmake_path": os.fspath(self.cmake),
            "skbuild_path": os.fspath(DIR),
            "skbuild_version": __version__,
            "python_executable": sys.executable,
        }

    def init_cache(
        self, cache_settings: Mapping[str, str | os.PathLike[str] | bool]
    ) -> None:
        with self.init_cache_file.open("w", encoding="utf-8") as f:
            for key, value in cache_settings.items():
                if isinstance(value, bool):
                    str_value = "ON" if value else "OFF"
                    f.write(f'set({key} {str_value} CACHE BOOL "" FORCE)\n')
                elif isinstance(value, os.PathLike):
                    # Convert to CMake's internal path format
                    str_value = str(value).replace("\\", "/")
                    f.write(f'set({key} [===[{str_value}]===] CACHE PATH "" FORCE)\n')
                else:
                    f.write(f'set({key} [===[{value}]===] CACHE STRING "" FORCE)\n')

            if self.module_dirs:
                # Convert to CMake's internal path format, otherwise this breaks try_compile on Windows
                module_dirs_str = ";".join(map(str, self.module_dirs)).replace(
                    "\\", "/"
                )
                f.write(
                    f'set(CMAKE_MODULE_PATH [===[{module_dirs_str}]===] CACHE PATH "" FORCE)\n'
                )

            if self.prefix_dirs:
                prefix_dirs_str = ";".join(map(str, self.prefix_dirs)).replace(
                    "\\", "/"
                )
                f.write(
                    f'set(CMAKE_PREFIX_PATH [===[{prefix_dirs_str}]===] CACHE PATH "" FORCE)\n'
                )
                f.write('set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "BOTH" CACHE PATH "")\n')

        contents = self.init_cache_file.read_text(encoding="utf-8").strip()
        logger.debug(
            "{}:\n{}",
            self.init_cache_file,
            textwrap.indent(contents.strip(), "  "),
        )

    def _compute_cmake_args(
        self, defines: Mapping[str, str | os.PathLike[str] | bool]
    ) -> Generator[str, None, None]:
        yield f"-S{self.source_dir}"
        yield f"-B{self.build_dir}"

        if self.init_cache_file.is_file():
            yield f"-C{self.init_cache_file}"

        for key, value in defines.items():
            if isinstance(value, bool):
                str_value = "ON" if value else "OFF"
                yield f"-D{key}:BOOL={str_value}"
            elif isinstance(value, os.PathLike):
                str_value = str(value).replace("\\", "/")
                yield f"-D{key}:PATH={str_value}"
            else:
                yield f"-D{key}={value}"

    def get_generator(self, *args: str) -> str | None:
        """
        Try to get the generator that will be used to build the project. If it's
        not set, return None (default generator will be used).
        """
        generators = [g for g in args if g.startswith("-G")]
        if generators:
            return generators[-1][2:].strip()
        return self.env.get("CMAKE_GENERATOR", None)

    def configure(
        self,
        *,
        preset: str | None = None,
        defines: Mapping[str, str | os.PathLike[str] | bool] | None = None,
        cmake_args: Sequence[str] = (),
    ) -> None:
        _cmake_args = self._compute_cmake_args(defines or {})
        all_args = [*_cmake_args, *cmake_args]

        if preset:
            if self.cmake.version < Version("3.19"):
                msg = f"CMake version ({self.cmake.version}) is too old to support presets."
                raise CMakeVersionError(msg)
            all_args.append(f"--preset={preset}")

        gen = self.get_generator(*all_args)
        if gen:
            self.single_config = gen == "Ninja" or "Makefiles" in gen

        if self.single_config and self.build_type:
            all_args.insert(2, f"-DCMAKE_BUILD_TYPE:STRING={self.build_type}")

        try:
            Run(env=self.env).live(self.cmake, *all_args)
        except subprocess.CalledProcessError:
            msg = "CMake configuration failed"
            raise FailedLiveProcessError(msg) from None

    def _compute_build_args(
        self,
        *,
        verbose: bool,
    ) -> Generator[str, None, None]:
        if verbose:
            yield "-v"
        if self.build_type and not self.single_config:
            yield "--config"
            yield self.build_type

    def build(
        self,
        build_args: Sequence[str] = (),
        *,
        targets: Sequence[str] = (),
        verbose: bool = False,
    ) -> None:
        local_args = list(self._compute_build_args(verbose=verbose))
        if not targets:
            self._build(*local_args, *build_args)
            return

        for target in targets:
            self._build(*local_args, "--target", target, *build_args)

    def _build(self, *args: str) -> None:
        try:
            Run(env=self.env).live(self.cmake, "--build", self.build_dir, *args)
        except subprocess.CalledProcessError:
            msg = "CMake build failed"
            raise FailedLiveProcessError(msg) from None

    def install(
        self,
        prefix: Path | None,
        *,
        strip: bool = False,
        components: Sequence[str] = (),
    ) -> None:
        opts = ["--prefix", str(prefix)] if prefix else []
        if not self.single_config and self.build_type:
            opts += ["--config", self.build_type]
        if strip:
            opts.append("--strip")

        if not components:
            self._install(opts)
            return

        for comp in components:
            opts_with_comp = [*opts, "--component", comp]
            logger.info("Installing component {}", comp)
            self._install(opts_with_comp)

    def _install(self, opts: Sequence[str]) -> None:
        try:
            Run(env=self.env).live(
                self.cmake,
                "--install",
                self.build_dir,
                *opts,
            )
        except subprocess.CalledProcessError:
            msg = "CMake install failed"
            raise FailedLiveProcessError(msg) from None
