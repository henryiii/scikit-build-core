from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.readers  # Might be Python version specific?
import importlib.util
import os
import subprocess
import sys

TYPE_CHECKING = False
if TYPE_CHECKING:
    import importlib.machinery


DIR = os.path.abspath(os.path.dirname(__file__))
MARKER = "SKBUILD_EDITABLE_SKIP"
VERBOSE = "SKBUILD_EDITABLE_VERBOSE"

__all__ = ["install"]


def __dir__() -> list[str]:
    return __all__


# Note: This solution relies on importlib's call stack in Python 3.11. Python 3.9 looks
# different, so might require a different solution, but I haven't gone deeper into that
# yet since I don't have a solution for the 3.11 case yet anyway.
class ScikitBuildRedirectingReader(importlib.readers.FileReader):
    def files(self):
        # ATTENTION: This is where the problem is. The expectation is that this returns
        # a Traversable object. We could hack together an object that satisfies that
        # API, but methods like `joinpath` don't have sensible implementations if
        # `files` could return multiple paths instead of a single one. We could do some
        # hackery to figure out which paths exist on the backend by hiding some internal
        # representation that knows both possible roots and checks for existence when
        # necessary, but that seriously violates the principle of least surprise for the
        # user so I'd be quite skeptical.
        return self.path


class ScikitBuildRedirectingLoader(importlib.machinery.SourceFileLoader):
    def get_resource_reader(self, module):
        return ScikitBuildRedirectingReader(self)


class ScikitBuildRedirectingFinder(importlib.abc.MetaPathFinder):
    def __init__(
        self,
        known_source_files: dict[str, str],
        known_wheel_files: dict[str, str],
        path: str | None,
        rebuild: bool,
        verbose: bool,
        build_options: list[str],
        install_options: list[str],
        dir: str = DIR,
    ) -> None:
        self.known_source_files = known_source_files
        self.known_wheel_files = known_wheel_files
        self.path = path
        self.rebuild_flag = rebuild
        self.verbose = verbose
        self.build_options = build_options
        self.install_options = install_options
        self.dir = dir
        # Construct the __path__ of all resource files
        # I.e. the paths of all package-like objects
        submodule_search_locations: dict[str, set[str]] = {}
        pkgs: list[str] = []
        # Loop over both python native source files and cmake installed ones
        for tree in (known_source_files, known_wheel_files):
            for module, file in tree.items():
                # Strip the last element of the module
                parent = ".".join(module.split(".")[:-1])
                # Check if it is a package
                if "__init__.py" in file:
                    parent = module
                    pkgs.append(parent)
                # Skip if it's a root module (there are no search paths for these)
                if not parent:
                    continue
                # Initialize the tree element if needed
                submodule_search_locations.setdefault(parent, set())
                # Add the parent path to the dictionary values
                parent_path = os.path.dirname(file)
                if not parent_path:
                    # root modules are skipped so all files should be in a parent package
                    msg = f"Unexpected path to source file: {file} [{module}]"
                    raise ImportError(msg)
                if not os.path.isabs(parent_path):
                    parent_path = os.path.join(self.dir, parent_path)
                submodule_search_locations[parent].add(parent_path)
        self.submodule_search_locations = submodule_search_locations
        self.pkgs = pkgs

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        # If no known submodule_search_locations is found, it means it is a root
        # module.
        if fullname in self.submodule_search_locations:
            submodule_search_locations = list(self.submodule_search_locations[fullname])
        else:
            submodule_search_locations = None
        if fullname in self.known_wheel_files:
            redir = self.known_wheel_files[fullname]
            if self.rebuild_flag:
                self.rebuild()
            return importlib.util.spec_from_file_location(
                fullname,
                os.path.join(self.dir, redir),
                submodule_search_locations=submodule_search_locations,
                loader=ScikitBuildRedirectingLoader(
                    fullname, os.path.join(self.dir, redir)
                ),
            )
        if fullname in self.known_source_files:
            redir = self.known_source_files[fullname]
            return importlib.util.spec_from_file_location(
                fullname,
                redir,
                submodule_search_locations=submodule_search_locations,
                loader=ScikitBuildRedirectingLoader(fullname, redir),
            )
        return None

    def rebuild(self) -> None:
        # Don't rebuild if not set to a local path
        if not self.path:
            return

        env = os.environ.copy()
        # Protect against recursion
        if self.path in env.get(MARKER, "").split(os.pathsep):
            return

        env[MARKER] = os.pathsep.join((env.get(MARKER, ""), self.path))

        verbose = self.verbose or bool(env.get(VERBOSE, ""))
        if env.get(VERBOSE, "") == "0":
            verbose = False
        if verbose:
            print(f"Running cmake --build & --install in {self.path}")  # noqa: T201

        result = subprocess.run(
            ["cmake", "--build", ".", *self.build_options],
            cwd=self.path,
            stdout=sys.stderr if verbose else subprocess.PIPE,
            env=env,
            check=False,
            text=True,
        )
        if result.returncode and verbose:
            print(  # noqa: T201
                f"ERROR: {result.stdout}",
                file=sys.stderr,
            )
        result.check_returncode()

        result = subprocess.run(
            ["cmake", "--install", ".", "--prefix", DIR, *self.install_options],
            cwd=self.path,
            stdout=sys.stderr if verbose else subprocess.PIPE,
            env=env,
            check=False,
            text=True,
        )
        if result.returncode and verbose:
            print(  # noqa: T201
                f"ERROR: {result.stdout}",
                file=sys.stderr,
            )
        result.check_returncode()


def install(
    known_source_files: dict[str, str],
    known_wheel_files: dict[str, str],
    path: str | None,
    rebuild: bool = False,
    verbose: bool = False,
    build_options: list[str] | None = None,
    install_options: list[str] | None = None,
) -> None:
    """
    Install a meta path finder that redirects imports to the source files, and
    optionally rebuilds if path is given.

    :param known_source_files: A mapping of module names to source files
    :param known_wheel_files: A mapping of module names to wheel files
    :param path: The path to the build directory, or None
    :param verbose: Whether to print the cmake commands (also controlled by the
                    SKBUILD_EDITABLE_VERBOSE environment variable)
    """
    sys.meta_path.insert(
        0,
        ScikitBuildRedirectingFinder(
            known_source_files,
            known_wheel_files,
            path,
            rebuild,
            verbose,
            build_options or [],
            install_options or [],
        ),
    )
