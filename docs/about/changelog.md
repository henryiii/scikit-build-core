# Changelog

## Version 1.1.2

This patch release adds a `ctypes` backend to `scikit-build init`. It builds a
plain C library without Python headers and makes a `py3` wheel.
`editable.rebuild-dir` now accepts a `{build_dir}` template key, so the install
tree can follow the build tree. Editable redirect installs no longer redirect
imports that run inside their own CMake build, such as nanobind stub generation.

Features:

- Init: `scikit-build init --backend ctypes` in #1620
- Editable: `{build_dir}` template key for `editable.rebuild-dir` (#1606) in
  #1609

Fixes:

- Editable: the redirect finder yields to normal imports inside its own CMake
  build, so build steps that import the package see the new build (#1612) in
  #1613

Documentation:

- Explain ccache misses with build isolation (#1605) in #1621

CI and testing:

- Always replace the cached scikit-build-core wheel on rebuild in #1614
- Drop the Windows PyPy 3.9 job in #1615
- Use the prek action with `GITHUB_TOKEN` for zizmor online audits in #1602

Internal:

- Update flake8-lazy to 0.10.1 in #1603

## Version 1.1.1

This patch release improves performance and fixes two minor regressions from
1.1.0. Free-threaded builds work again on CMake versions between 3.30 and 4.1.2
(please update CMake to 4.1.2+, though). A checkout inside an ignored directory
is again left out of the SDist. Wheel builds are also faster, especially on
Windows, because package sources are no longer copied to a staging directory
first.

Fixes:

- Only set `Python_FIND_ABI` for free-threaded builds on CMake 4.1.2+, since
  older versions fail to find `Development.Module` when it is set (#1597) in
  #1598
- SDist: a repository boundary that the outer repository ignores is excluded
  with its full subtree (#1593) in #1594. Also improves performance.

Performance:

- Write package sources directly to wheels without staging copies (#1591) by
  @sepcnt in #1592

CI and testing:

- Suppress sphinx-llm unknown node warnings in #1595
- Use CMake 4.2 on `windows-11-arm` in #1590

## Version 1.1.0

Packages can now declare their own config-settings in a
`tool.scikit-build.config-setting` table. This gives packages the opportunity to
add a documented interface in place of raw CMake defines. The new
`scikit-build settings list` command shows all the config-settings that a
project accepts. New settings include `cmake.fresh`, `if.not` overrides, and
`sdist.resolve-symlinks = "error"`. `import-names` and `import-namespaces`
(PEP 794) are filled from Python if set as dynamic. `project.version` is now
kept exactly as written in the metadata (1.1+). Editable loaders expose their
search paths, redirect mode gives a deterministic `__path__` order, and you can
set up a persistent install tree even without rebuild-on-import. Other bugs and
performance issues are addressed.

Features:

- New settings:
  - `tool.scikit-build.config-setting` for package-declared config-settings in
    #1489
  - `cmake.fresh` to configure from scratch in #1516
  - `if.not` overrides in #1539
- CLI:
  - `scikit-build settings list` lists supported config-settings in #1522
  - `scikit-build build requires` accepts `-C`/`--config-setting` to pass
    config-settings to the backend hook, and `--type {static,dynamic,both}` to
    select the static `build-system.requires`, the dynamic hook output, or both
    in #1584
- SDist:
  - `sdist.resolve-symlinks = "error"` fails the SDist build if an included path
    is a symlink, and lists each link with its target. This includes
    `sdist.force-include` sources and the files under them. Directory links are
    not followed. Requires `minimum-version` 1.1 or unset (#1581) in #1583
- Metadata:
  - `import-names` and `import-namespaces` (PEP 794) listed in `project.dynamic`
    are computed from the Python packages (#1536) in #1578
  - `project.version` is kept as written in the `Version` metadata field and in
    `SKBUILD_PROJECT_VERSION_FULL`, so a calendar version such as `2024.01.05`
    keeps its leading zeros. Filenames stay normalized. Requires
    `minimum-version` 1.1 or unset. In #1572
- Editable:
  - Loaders expose their search paths as a `paths` attribute in #1567
  - An explicit `editable.rebuild = false` is honored with
    `editable.rebuild-dir`, so a persistent install tree can be used without
    rebuild-on-import (#1576) in #1577
- File API:
  - Complete the file-api models and keep reference data in #1521
- Drop Python 3.8 in #1281

Fixes:

- Builder:
  - Compute the wheel tag from the build environment (`tool.scikit-build.env`)
    in #1575
  - Honor a `CMAKE_GENERATOR` define when computing build requirements in #1557
  - Read `Py_GIL_DISABLED="0"` as not free-threaded in #1574
  - Set `Python_FIND_ABI` for free-threaded builds on CMake 3.30+ in #1532
  - Don't pass the `Python_LIBRARY` hint in SABI mode on Windows in #1533
  - Warn once for unsupported `CMAKE_ARGS` defines in #1573
  - Drop two-token `-D CMAKE_BUILD_TYPE` from `CMAKE_ARGS` by @r3wretrhy in
    #1543
  - Keep building when the CMake file-api reply is broken in #1562
- CMake discovery:
  - Prefer `cmake` over `cmake3` when searching (#1514) in #1515
  - Double the CMake discovery timeout on native Apple Silicon (#1530) by
    @DSeaStar in #1535
  - Correct the riscv64 manylinux tag for cmake wheels in #1563
  - Program search, build-dir info, and module detection robustness in #1554
- Settings:
  - `if.cmake-wheel` never matched a platform in #1538
- Editable:
  - Redirect installs give a package a deterministic `__path__` order: the CMake
    install tree first, then the source tree, so `importlib.resources` no longer
    depends on `PYTHONHASHSEED` (#1565) in #1566
- SDist:
  - Ignore rules no longer cross repository boundaries: a superproject's
    `.gitignore` does not apply inside a git submodule, matching git (#1582) in
    #1585
  - Scope the nested `.gitignore` scan to the walked subtree by @zklaus in #1542
- File API:
  - Match CMake's install-rule paths and namelink spelling in #1520
- Setuptools:
  - Pass the hook state to `GetRequires` in #1555
  - Parse `--cmake-args` with `shlex` in #1560
- Init:
  - The `abi3t` template sets `SOSABI` as well as `SOABI` by @ngoldbaum in #1587
- Variants:
  - Cap the `variantlib` build requirement to `<0.1` by @CavRiley in #1571
- Limit `fastjsonschema` on Python 3.9 in #1524

Performance:

- Scan entry points once for all groups in #1559
- Cache entry-point scans and known-wheel lookups in #1545
- Build and builder hot paths in #1547
- Read settings once per build in the setuptools plugin in #1548
- Cut editable shim import time in #1546
- Compile the CMake tokenizer regex once in #1544
- Look up nested `.gitignore` specs by ancestor in #1550

Documentation:

- Add an advanced topic on wrapping the build backend in #1518
- Add `llms.txt` and markdown copies of pages in #1523
- Recommend rebuilding editables via `find_spec` before import in #1510
- Name the external dynamic-metadata plugins in #1511
- Update moved intersphinx inventory URLs in #1569

CI and testing:

- Test the matrix CMake version, fix pass job needs, coverage and test fixes in
  #1553
- Install dynamic build requires in the downstream session in #1580
- Stop rebuilding the wheelhouse wheel every session in #1549
- Allow the setuptools-scm `file_finders` deprecation in #1568
- Accept the new CPython 3.15rc1 abi3 suffix in #1529
- Pin the wrapper's CMake install staging layout in #1512

Internal:

- Bump the CMake policy upper bound to 4.4 in #1509
- Avoid CMake 4.4.0's broken Windows SABI detection in #1513
- Backport Fedora downstream changes by @LecrisUT in #1491
- Source cleanups from the review in #1552
- Clean up leaked and stale config in #1551
- Use `unlink(missing_ok=True)` for stale `CMakeCache.txt` removal in #1517

## Version 1.0.3

This patch release polishes the setuptools compatibility plugin:
`config_settings` are now threaded through to the build command, the source tree
stays clean in strict editable mode, and the `SubCommand` protocol is fully
implemented.

Fixes:

- Complete the setuptools `SubCommand` protocol by @henryiii in #1502
- Thread `config_settings` to the build command by @henryiii in #1499
- Keep source tree clean in strict editable mode by @henryiii in #1501

Documentation:

- Put uv first in installer tabs and add it to config-settings by @henryiii in
  #1507
- List choices for Literal options in the README table by @henryiii in #1506
- Touch up README options tables, setuptools docs by @henryiii in #1504
- Show the projects list as a card grid with language/binding badges by
  @henryiii in #1503
- Add high-star projects to the known projects list by @henryiii in #1497

CI and testing:

- Make linkcheck retry timeouts from slow hosts by @henryiii in #1505
- Forward `-C` config-settings in downstream editable install by @henryiii in
  #1498

## Version 1.0.2

This patch release fixes redirect editable installs so that PEP 302 import hooks
(such as `beartype.claw`) that register a `sys.path_hooks` entry are honored for
redirected modules.

Fixes:

- Resolve redirected modules through `sys.path_hooks` by @henryiii in #1493

Internal:

- Stop using deprecated `build.util.project_wheel_metadata` in #1494

## Version 1.0.1

This patch release fixes two bugs: shared namespace packages were being
truncated in redirect editable installs, and the wheel timestamp clamp could
overflow on 32-bit `time_t` platforms.

Fixes:

- Don't truncate shared namespaces in redirect mode by @henryiii in #1483
- Wheel timestamp clamp overflows on 32-bit `time_t` platforms by @henryiii in
  #1484

Internal:

- Update pre-commit hooks in #1480

## Version 1.0.0

We've worked through over 100 issues and ran extensive review sweeps, fixing
over 90 bugs and adding 40+ features! We've added support for PEP 803
(free-threaded stable ABI), PEP 808 (partially dynamic metadata), PEP 829
(`.start` files), and experimental PEP 817 (variants). Editable installs are
much better, with lots of edge cases fixed, like namespace packages and resource
discovery. For rebuilds, which are still experimental, loaders expose a manual
`rebuild()`, inplace mode now supports rebuilds, and rebuilds can optionally
target a persistent install tree (which removes several caveats). The setuptools
and hatchling plugins are no longer experimental and Hatchling supports editable
installs. There's a new unified `scikit-build` CLI, including an `init` command
to scaffold new projects. Wheels can be reproducible. Dynamic metadata follows a
spec with entry-point discovery and uses `[[tool.dynamic-metadata]]`, and you
can write your own plugins. There are new settings: an `env` table for setting
environment variables, `install.targets`, `force-include` for SDists and wheels,
`sdist.resolve-symlinks`, and a `${SKBUILD_<TREE>_DIR}` prefix for targeting
wheel trees; existing settings gained `sdist.inclusion-mode = "explicit"` and
list-valued `cmake.build-type`. Imports are lazy on Python 3.15+ (PEP 810),
making CLI and backend startup faster. Lots of documentation has been added and
updated, along with new examples and samples. We've also polished f2py-cmake and
cython-cmake.

As (almost) always, if you set a minimum-version, your build should be
unaffected. Behavior changes to be aware of: SDists now resolve symlinks by
default, with an `sdist.resolve-symlinks` setting providing `"all"`,
`"external"`, `"none"`, and `"classic"` modes. The old names of renamed
configuration fields (`cmake.minimum-version`, `ninja.minimum-version`,
`cmake.verbose`, and `cmake.targets`) now error unless `minimum-version` is set,
and the deprecated `tool.scikit-build.metadata` table warns if minimum-version
is not set. The empty `pyproject` extra was removed; installers like pip, build,
and uv merely warn if you still request it.

Also see
[the announcement post](https://iscinumpy.dev/post/scikit-build-core-1-0).

Features:

- CLI:
  - unified `scikit-build` command with submodules as subcommands in #1355
  - add `init` command to scaffold starter projects in #1357
- Configuration providers:
  - entry-point configuration providers in #1406
- New settings:
  - `env`: settable environment variables in #1377 (replaces #1370, unreleased)
  - `install.targets` for custom install targets in #1371
  - `sdist.force-include`, `wheel.force-include` to map files to include in
    #1364; entries are served live in redirect editable installs in #1441
  - `wheel.reproducible` allows building a reproducible wheel (with some setup)
    in #1389
  - `editable.rebuild-dir` at a persistent install tree (opt-in) in #1375
- Updated settings:
  - `cmake.build-type` now can be a list for multiple builds in #1386
  - `wheel.packages` can now include single module files in #1395
  - `cmake.build-type` honors `CMAKE_BUILD_TYPE` from the environment in #1372
  - add `"explicit"` SDist inclusion-mode (opt-in include) in #1249
  - resolve symlinks by default by @Doekin in #1265, with `"external"`,
    `"classic"`, and `"none"` (store directory symlinks) modes in #1434
  - support PEP 803, the free-threaded stable ABI, including the combined
    `abi3.abi3t` wheel tag, in #1269 and #1382
- Other settings:
  - add `${SKBUILD_<TREE>_DIR}` prefix for wheel-tree targeting in #1379
  - add `{name}` placeholder for template-formatted settings in #1445
  - warn on the deprecated `tool.scikit-build.metadata` table, and error on
    renamed config fields, unless an old minimum-version is set, in #1397 and
    #1399
- Dynamic metadata:
  - support `[[tool.dynamic-metadata]]` in #1390 and #1416
  - honor the `dynamic_wheel` hook when building SDists in #1433
  - emit METADATA 2.6 for PEP 808 partially-dynamic fields, via vendored
    pyproject-metadata 0.12.1, in #1454 and #1455
- Experimental:
  - add experimental PEP 817 variant support in #1284
- Editable:
  - PEP 829 (`.start` files) support in #1297
  - expose `rebuild()` on redirect and inplace module loaders in #1403 and #1411
- Plugins:
  - de-experimentalize the setuptools and hatchling plugins in #1358
  - include plugin extras for setuptools/hatchling, and warn if the extra is
    missing from `build-system.requires`, in #1290 and #1344
- Hatchling plugin:
  - editable install support in #1282
  - reject `wheel.exclude` as unsupported in #1431
- Setuptools plugin:
  - inplace editable support in #1278
  - add `cmake_install_dir` and `cmake_install_target` in #1286 and #1374
  - add `cmake_process_manifest_hook` in #1285
  - allow `cmake_with_sdist=False` in #1287
  - honor `SKBUILD_CONFIGURE_OPTIONS` and `SKBUILD_BUILD_OPTIONS` in the wrapper
    in #1394

Fixes:

- Settings:
  - accept override-only settings via config-settings in #1307
  - flag scalar config-settings assignment to dict fields in #1435
  - entry-point providers: treat their config as dynamic for validation gates,
    with robust signature dispatch and duplicate-name handling, in #1424 and
    #1425
  - allow `=` inside dict-style env var values like `SKBUILD_CMAKE_DEFINE` in
    #1311
  - accept plain strings for list/table fields in config-settings (e.g.
    `-Cwheel.packages=src/pkg`) in #1323
  - don't crash on overrides mixing `inherit` with top-level fields in #1323
  - apply `if.state` overrides when computing `get_requires_for_build_*` in
    #1322
  - render `{root}` correctly in templated settings such as `build-dir` in #1318
  - JSON schema no longer rejects valid `cmake.define` lists in #1306
- Dynamic metadata:
  - load provider-path providers via a meta-path finder in #1366
  - correct the `DynamicMetadataProtocol.dynamic_metadata` signature in #1365
  - combine same-field `dynamic_wheel` reports with OR in #1437
  - error on unknown keys in `regex`/`template` plugin settings instead of
    silently ignoring them in #1319
  - handle typed `vcs_versioning.overrides` in mypy in #1388
- Wheel:
  - auto-discover namespace packages in wheel builds in #1385
  - don't error when a `wheel.packages` source is CMake-generated in #1440
  - use `Path.as_posix()` for including generated files in SDist/wheel by
    @shiftinv in #1381
  - clamp `SOURCE_DATE_EPOCH` to the ZIP timestamp range in #1423
  - emit installer-compatible `abi3t` wheel tag in #1380
  - honor `CMAKE_OSX_DEPLOYMENT_TARGET` in the wheel platform tag in #1338
  - honor an explicit empty `license-files` to disable license collection in
    #1311 and #1322
  - write `location = "source"` generated files as UTF-8, don't crash on
    subdirectories inside the scripts install dir, and fully prune consecutive
    excluded directories in #1322
- SDist:
  - don't crash on dangling symlinks with `resolve-symlinks = "all"`, and detect
    symlink loops when walking the source tree, in #1341 and #1421
  - don't prune directories matched only by glob includes in default inclusion
    mode in #1339
- Editable:
  - make namespace package installs importable, including remapped namespace
    packages, in #1346 and #1427
  - fix import subpackage propagation in #1304
  - don't treat versioned sonames as importable modules in #1337
  - add symlinked module's real dir to `__path__` in #1335
  - `importlib.resources.files()` in redirect mode in #1279
  - recognize Cython `__init__.pxd`/`.pyx` as package indicators by @vyasr in
    #1292
  - debounce rebuild to once per process in #1368
  - `rebuild()` no longer hides the build output on failed rebuilds in #1318
  - refuse to wipe a populated rebuild-dir, and use safe install/build paths for
    manual `rebuild()`, in #1400 and #1429
  - only block absolute `wheel.install-dir` for rebuilds in #1334
- CMake:
  - cap `SKBUILD_PROJECT_VERSION` to four components in #1369
  - strip flags from sysconfig CC/CXX to just the executable, keeping compiler
    wrappers, in #1331 and #1418
  - generator handling: detect two-token `-G Ninja` and `-G` in `CMAKE_ARGS`,
    detect multi-config generators set via `cmake.define.CMAKE_GENERATOR` so the
    right `--config` is used, and apply full Ninja handling to
    `Ninja Multi-Config` in #1320 and #1352
  - free-threaded Windows import library and two-token `-D` parsing in #1422
  - don't skip the ninja requirement when the generator is forced to Ninja in
    #1442
  - more reliably find the Python library on Windows in #1310
  - warn when CMake will build a mismatched `x86_64` extension on macOS in #1404
  - `-DCMAKE_SYSTEM_PROCESSOR` in the CMake args suppresses `ARCHFLAGS` handling
    on macOS, as documented, in #1320
  - comments inside `cmake_minimum_required(...)` no longer break
    `cmake.version = "CMakeLists.txt"`, and unparsable files fall back
    gracefully in #1319
  - File API: properly handle `Union` by @LecrisUT in #1272; read the toolchains
    reply, tolerate optional link fields, and restore missing
    `Target.sources`/`InstallRule.type` fields in #1311 and #1319
- CLI:
  - argument parsing and clear errors for common mistakes in #1426
- Hatchling plugin:
  - ignore hatchling's reserved enable-by-default hook option in #1419
  - don't double the `wheel.install-dir` prefix, which made wheels unimportable,
    in #1321
- Setuptools plugin:
  - wrapper path and classic scikit-build compatibility fixes in #1295 and #1316
  - protect `SetupError` in #1293
  - accept `wheel-free-setuptools` extra in the plugin warning in #1413
  - don't require `editable.mode` for `build_ext --inplace` in #1432
  - build-type list rejection, `package_dir` editable root, and free-threaded
    limited-API gate in #1428
  - resolve overrides with the correct `wheel`/`editable` state in #1321
- Sweeps:
  - many further small fixes across settings, wheel, editable, File API,
    generator detection, and the plugins from extensive review sweeps in #1305,
    #1306, #1311, #1318, #1319, #1320, #1321, #1322, and #1323

Documentation:

- New guides and FAQs:
  - add a workspaces and monorepos guide in #1444
  - add a Windows debug builds note in #1450
  - FAQ for IDE IntelliSense / `compile_commands.json` in #1447
  - explain target output paths on MSVC / multi-config generators in #1446
  - FAQ on coverage and debugging (gcov/gcovr/GDB) in #1409
  - tips for shipping a ctypes-loaded shared library in #1408
  - FAQ for dependency library in `site-packages/bin` or `lib` in #1393
  - document `cmake.module` entry point and metadata states in #1360
- 1.0 refresh:
  - dedupe, simplify, and restructure the documentation in #1448
  - review and refresh documentation for the 1.0 release in #1402
  - add missing versionadded/versionchanged directives for 1.0 in #1405
  - refresh stale guidance and version pins in #1361
  - fix incorrect config keys and stale claims in #1359
  - remove documented unimplemented search settings in #1354
  - show config-settings and env var forms in the config reference in #1347
  - use `-C` instead of `--config-settings` in examples in #1451
  - minor cleanup and style check in #1453
  - fix typos and grammar in #1362
- Clarifications and fixes:
  - clarify `wheel.packages` semantics (top-level, not a find/where) in #1407
  - address post-merge review notes on entry-point config in #1438
  - fix `sdist.inclusion-mode` name and dynamic-metadata field requirement in
    #1420
  - clarify README example and unify `cmake_minimum_required` ranges in #1392
  - improve docs on source in #1276
  - avoid a common timeout in #1308
- Examples:
  - use cython-cmake and f2py-cmake in getting started examples in #1353
  - link `Python::Module` in the Fortran example for CMake 4.x in #1373
- Site:
  - fix RTD version and render GitHub-style admonitions in #1410
  - make sphinx-tippy tooltips follow the active theme in #1349
  - add GitHub icon to header icon row in #1387
  - add more projects using scikit-build-core, including pyarrow by @raulcd, in
    #1266 and #1309

CI and testing:

- Cover uv as an install frontend via a workspace in #1443
- Add Python 3.15 and 3.15t to CI in #1383
- Skip heavy test matrix on docs-only changes in #1356
- Adapt to setuptools-scm 10 / vcs-versioning 2 warnings in #1350
- Exclude pytest 9.1.0 (params-fixture override regression) in #1329
- Pin old-CMake Windows rows to windows-2022, add a VS 2026 row in #1326
- Reduce test-suite wall-clock time in #1325
- Fix Windows `PermissionError` from concurrent wheelhouse lock races, and clean
  up incomplete or old editable wheels in the wheelhouse, in #1283 and #1288
- Secure GitHub Actions workflows in #1302
- Use native uv integration in RTD in #1274
- Stub macOS lipo arch probe for fake-subprocess tests in #1313 and #1314
- Migrate beakerlib test to python script by @LecrisUT in #1376

Internal:

- Faster startup via lazy imports (PEP 810) in #1415
- Unify wheel build orchestration across backend and hatch plugin in #1345
- Rename editable files to `_editable_skbc_<name>` in #1332
- Drop the empty `pyproject` extra in #1398
- Remove `orjson` from dependencies in #1333
- Support `uvx scikit-build-core` too in #1396
- Add a utils package by @LecrisUT in #1268
- Simplification cleanups from a repo sweep in #1312
- Use local `TYPE_CHECKING = False` instead of importing from typing in #1412
- Adapt to better pathspec types in #1277

## Version 0.12.2

We've fixed another issue in the new file inclusion mode on Windows. We now
always normalize SDist names, even if `minimum-version` is set to 0.4 or older,
due to the fact PyPI no longer accepts non-normalized SDist names. Please
increase your `minimum-version` anyway, though! Finally, the debug logging for
file inclusion now displays the exact rule that triggered the include/exclude
behavior.

Fixes:

- Use `as_posix` for prefix matching for better Windows support by @henryiii in
  #1246
- Always normalize SDist names, even in `<0.5` compat mode by @henryiii in #1247
- Better logging on why something fails/passes file inclusion check by @henryiii
  in #1250

Internal:

- Backport downstream RHEL patch to disable tests by @LecrisUT in #1244

## Version 0.12.1

This fixes a regression on Windows when targeting 32-bit wheels on a 64-bit
host. This reverts part of #1209. We have added 32-bit testing on Windows to our
CI.

Fixes:

- Use `CMAKE_GENERATOR`(`_PLATFORM`) on Windows again by @henryiii in #1235

Documentation:

- Use newly fixed `click-extra` for admonitions by @henryiii in #1232
- show CI state of the main branch in the badge by @LecrisUT in #1236

## Version 0.12.0

This release adds a new `sdist.inclusion-mode` setting, with a new default:
ignored directories are no longer traversed unless a file is specifically
allowed inside of it via the base path. This should be faster and less
surprising. The old behavior ("classic") and no gitignore ("manual") are also
provided.

Features:

- `sdist.inclusion-mode` by @henryiii in #1048
- Better support for cross-compilation by @LecrisUT in #1050
- Support fancy-pypi-readme 25.1's package name, bump, drop workarounds by
  @henryiii in #1201

Fixes:

- Add a setting to disallow hard-coding some setting keys in the
  `pyproject.toml` - currently applied to `fail`, by @LecrisUT in #1078
- Respect`_PYTHON_HOST_PLATFORM` env variable by @ryanking13 in #1196
- Better support for ninja on Windows by @henryiii in #1209 (partially reverted
  in 0.12.1)
- Move the file-api parsing to a debug message by @LecrisUT in #1184
- (Hatchling) Path issue on Windows mingw64 and UCRT by @henryiii in #1210
- (Setuptools) handle generic setup return type by @henryiii in #1202

Documentation:

- Add buildgen to list in quickstart by @henryiii in #1220
- Improve links back to GitHub by @henryiii in #1181
- Mention Android support by @mhsmith in #1142
- Move community meeting link by @henryiii in #1221
- Source link by @henryiii in #1224
- Color CLI on Python 3.14+ by @henryiii in #1218
- Use `sphinx-programoutput` with new ANSI support by @henryiii in #1226

CI and testing:

- Test on 3.14t in CI by @henryiii in #1185
- Cases for different use cases of generated files by @eirrgang in #1193
- Consolidate editable and isolated fixtures by @LecrisUT in #1194
- Fix Apple Silicon isolation check by @henryiii in #1227
- Fix local runs on AS macOS by @henryiii in #1182
- Rework downloading the wheelhouse for isolation tests by @henryiii in #1199
- Stale downloads could break tests by @henryiii in #1223
- Test-core, pybind11 in full test by @henryiii in #1200
- cmake-version was missing by @henryiii in #1231

Internal:

- Bumped internal pyproject-metadata to 0.11 by @henryiii in #1230
- Avoid a numpy yanked warning by @henryiii in #1222
- Break the circular dependency in pybind11 by @LecrisUT in #1188
- Bump PyPy to currently supported 3.11 by @DimitriPapadopoulos in #1164
- Bump macOS by @DimitriPapadopoulos in #1165
- Fix a broken line in the noxfile by @henryiii in #1208
- Ignore lock files too by @henryiii in #1206
- Increase test duration for pytest by @LecrisUT in #1219
- Move extras to groups by @henryiii in #1177
- pytest `log_level` is better than `log_cli_level` by @henryiii in #1178
- Support PEP 604 unions in sources (#1213) by @martinezlc99 in #1214
- Switch to `typos` by @henryiii in #1192
- Tests expect typing extensions on 3.9 by @henryiii in #1203
- Use SPDX license for our license by @henryiii in #1183

Internal (ruff linting):

- Add a few ruff checks by @henryiii in #1174
- Add even more ruff by @henryiii in #1175
- Enable more ruff using config by @henryiii in #1179
- Set ruff to ALL by @henryiii in #1176

## Version 0.11.6

This release adds known wheels for the `riscv64` platform, and adjusts a command
timeout to handle slow startup on Rosetta.

Fixes:

- Adjust the timeout when running on rosetta by @henryiii in #1131
- Add known wheels for riscv64 by @mayeut in #1129

Internal:

- Argparse defaults in Python 3.14 updated by @henryiii in #1133

CI and testing:

- Ignore setuptools-scm warning for packages that don't use it by @henryiii in
  #1126

Documentation:

- Fix small typo in docs introduction by @vepadulano in #1122

## Version 0.11.5

This release speeds up large directories (more directory changes/optimization
planned for 0.12), and adds a warning about 3.13.4 being broken on Windows.

Fixes:

- Improve `.gitignore` iteration speed by @silversquirl in #1103
- Warn on 3.13.4 on Windows by @henryiii in #1104
- Add debug logging explaining why a file is included/excluded by @henryiii in
  #1110

Documentation:

- Fix a typo in a column-name of the `platform-machine` table by @mabruzzo in
  #1096

## Version 0.11.4

This release improves support for GraalPy and fixes a few other minor issues.

Fixes:

- Typo in license-files by @henryiii in #1084
- Fix dynamic-metadata iteration (only affected GraalPy) by @henryiii in #1092
- Better abiflags implementation, uses ABIFLAGS on 3.14+, supports GraalPy by
  @henryiii in #1092
- File API `commandFragments` is optional by @henryiii in #1092
- Add `python -m scikit_build_core` printout and a few CLI issues by @henryiii
  in #1091
- Add some platform info to logging by @henryiii in #1094

Internal:

- Explicit mypy ignores by @henryiii in #1087
- Adjust typing to be ready for next mypy release by @henryiii in #1088

Documentation:

- Refactor the documentation to use single-line summaries by @LecrisUT in #1079

## Version 0.11.3

This release fixes some fields in the expanded supported dynamic-metadata fields
from 0.11.2. It also now is tested on Python 3.14, including adding color to
`--help` on the experimental commands (now documented).

Fixes:

- fix: add scripts to `_DICT_STR_FIELDS` for dynamic metadata by @bilke in #1070

CI and testing:

- Officially support Python 3.14, color help @henryiii in #1074
- Remove no-wheel based on virtualenv version by @henryiii in #1071
- Work when `CMAKE_GENERATOR` is set by @henryiii in #1066
- Try a workaround for packit `propose-downstream` by @LecrisUT in #1067
- Update coverage a bit by @henryiii in #1073

Documentation:

- Generate config value reference by @LecrisUT in #1052
- Update and fix projects list by @henryiii in #1075
- Document CLI utilities by @henryiii in #1080

## Version 0.11.2

This release allows dynamic-metadata to reference other fields, which enables a
new plugin, "template", and enables the fancy readme plugin to include the
version. There are also a few fixes; `Python_EXECUTABLE` is now a proper CMake
path, and using a renamed option from the command line or environment variable
no longer triggers an error when the min required version is from before that
was introduced.

Features:

- Add template dynamic-metadata plugin and support requesting other fields by
  @henryiii in #1047
- Parse the CMake file-api during configuration by @LecrisUT in #1016
- Add a couple of build commands by @henryiii in #1055

Fixes:

- Make sure all paths are CMake paths by @henryiii in #1063
- Support overriding renamed options by @henryiii in #1054

CI and testing:

- Add Windows ARM by @henryiii in #1046
- Add more tests of package traversal by @vyasr in #906
- A few better ids by @henryiii in #1058

Docs:

- Fix community meeting link by @jcfr in #1049
- Add a field metadata to the setting fields by @LecrisUT in #1051
- Document how to deal with dynamic linking by @LecrisUT in #1022
- Fix typo in macOS repair wheel tool name by @burgholzer in #1042

## Version 0.11.1

This release contains two small fixes for edge case issues.

Fixes:

- Bump pyproject-metadata to handle form feeds on Python < 3.12.8 by @henryiii
  in #1014
- Increase timeout on CI by @henryiii in #1019

CI and testing:

- Ignore deprecation message from cattrs on Python 3.14 alphas by @LecrisUT in
  #1020
- Add more integration tests in Fedora by @LecrisUT in #800
- Restore example builds for Windows/macOS by @henryiii in #1025

Internal:

- Remove leftover Python 3.7 checks by @LecrisUT in #1011
- Bump pytest version and include pytest-xdist by @henryiii in #1008
- Bump to ruff 0.10, work around bug by @henryiii in #1015

Docs:

- Clarify verbosity options by @LecrisUT in #1018
- Fix incorrect configuration example by @buddly27 in #1023
- Fix incorrect name (`PYBIND11_NEWPYTHON` -> `PYBIND11_FINDPYTHON`) by
  @henryiii in #1021

## Version 0.11.0

This version adds support for PEP 639 (license expressions) and updates the
default METADATA version 2.2. Support for Python 3.7 has been removed. You can
use `build.requires` to inject build requirements using overrides.

Features:

- Update vendored pyproject-metadata (PEP 639 support) by @henryiii in #917
- 0.11+ default to metadata 2.2 by @henryiii in #986
- Rework CMake search path settings and add `cmake.root` by @LecrisUT in #880
- `SKBUILD_SABI_VERSION` by @henryiii in #962
- Support TOML lists in `cmake.define` by @alexreinking in #921
- Add new field `build.requires` by @LecrisUT in #992
- Drop python<=3.7 support by @kloczek in #769
- Setuptools plugin: pyproject-toml only config support by @henryiii in #975
- Setuptools plugin: error for `cmake_install_target` by @henryiii in #976

Fixes:

- Lock during experimental `editable.rebuild` by @hauntsaninja in #968
- Add known wheels for armv7l by @mayeut in #960
- Ignore `build-dir` automatically by @henryiii in #916
- Longer timeout on Windows by @henryiii in #974
- `path_to_module` should handle hidden files (e.g. `.clang-tidy`) correctly by
  @tae-jun in #987
- Timeout checking cmake/ninja by @henryiii in #973

Internal:

- Add a `format` module that is used in the expansion of `pyproject.toml` by
  @LecrisUT in #998
- Bump Ruff to 0.8.0 by @AlexWaygood in #949
- Add citation by @henryiii in #945
- Vendor updates by @henryiii in #918

CI and testing:

- Correct the function prototype defined in the stub file in `simplest_c`
  example by @LinZhihao-723 in #937
- Synchronize with Fedora downstream by @LecrisUT in #884
- Fix RTD builds when last git tag is more than 50 commits behind by
  @agriyakhetarpal in #1001
- Tighten up permissions a bit by @henryiii in #983
- `tmt` tests improvements by @LecrisUT in #899
- Update deployment a bit by @henryiii in #922
- Use astral-sh/setup-uv instead by @henryiii in #923
- Simpler noxfile by @henryiii in #924
- Test on Linux ARM & Python 3.14 alphas by @henryiii in #1003
- Support for parallel testing by @henryiii in #1004

Docs:

- `sphinx-apidoc` changed its mind by @LecrisUT in #996
- Fix Google meet reference to use updated link by @jcfr in #931
- Clarify docs for activating stable ABI by @eirrgang in #940
- Consistently use backticks to reference Python module components by @jcfr in
  #956
- Fix instructions to check if `Development.SABIModule` was requested by @jcfr
  in #957
- Add some notes and warnings about cross-compilation by @henryiii in #985
- Add sphinx-tippy by @LecrisUT in #1000
- Correct the order of entry-points and CMake variables by @njzjz in #948
- Quickstart updates by @henryiii in #939
- Some restructuring by @LecrisUT in #997

## Version 0.10.7

This version has three fixes related to advanced usages of overrides.

Fixes:

- Avoid modifying the input dict by @henryiii in #903
- Avoid providing prepare-metadata methods if `failed` in overrides by @henryiii
  in #904
- Support negative envvar values correctly by @henryiii in #907

## Version 0.10.6

This version has several fixes; the new `remove` key in 0.10 had a mistake
making it unusable, this has been fixed along with the matching issue in the
tests. Editable installs failed if there was a folder matching an extension
name. Multiplexed paths were not supported for plugins, now they are. The
downstream nox job is also now a bit better.

Fixes:

- Use correct settings key to remove parts of the version in regex metadata
  plugin by @philippjh in #887
- Support multiplexed path by @henryiii in #896
- Editable subpackage by @henryiii in #895
- Only strip Release and MinSizeRel builds by default by @henryiii in #898
- Typo in debug message by @LecrisUT in #892

Docs:

- Add build info by @henryiii in #878
- Fix typo in `if.platform-system` example by @henryiii in #879

CI and testing:

- Packit configuration update by @LecrisUT in #799

## Version 0.10.5

This version fixes a issue rebuilding if you have a `build-dir` set and are
using isolated build environments. The cache is now correctly cleared if this
occurs. An issue with a certain style of gitignore was also fixed.

Fixes:

- Automatically refresh the cache when required by @henryiii in #870
- `sdist.exclude` takes precedence over `.gitignore` by @alexreinking in #872

## Version 0.10.4

This version fixes the logic for handling the sysconfig variables on Windows for
the values that used to be only provided on UNIX. This mostly affects targeting
the Stable ABI on Python 3.13. Editable install rebuilds now work if you have a
`wheel.install-dir` set, too.

Fixes:

- Windows 3.13 stable ABI by @LecrisUT in #865
- Editable installs now respect the value of `wheel.install-dir` by @psalvaggio
  in #867

Docs:

- Add conda help to faqs by @henryiii in #868

## Version 0.10.3

This release fixes an issue on Windows systems with non-utf-8 default encodings
for Python \<3.14 when reading gitignores with special characters.

Fixes:

- Make sure encoding is specified in more places by @henryiii in #861

## Version 0.10.2

This release fixes a regression with 0.10 where a manually included file in an
sdist would get included twice, affecting some tools (like uv).

Fixes:

- Files included twice when they match `include_spec` by @abetlen in #857

## Version 0.10.1

This is a quick fix release with two patches for specific situations.

Fixes:

- Fix crash when building inside a submodule by @ausbin in #854
- `cmake.minimum-version` logic issue by @henryiii in #853

## Version 0.10.0

This version adds auto CMake version discovery, opt-in auto minimum-version,
rebuild on failure support, quite a few new override options greatly expanding
the static config options for builds, more powerful regexs, and more.

Also see
[the announcement post](https://iscinumpy.dev/post/scikit-build-core-0-10).

New features:

- Auto CMake version by @henryiii in #804
- Auto minimum-version by @henryiii in #798
- Add `fail` setting to instant-fail build by @henryiii in #824
- Add messages config for failure/success by @henryiii in #825
- New color system for message config by @henryiii in #842
- Add `if.abi-flags` (for free-threaded) by @henryiii in #819
- Adding `if.system-cmake` and `if.cmake-wheel` by @henryiii in #826
- Add `if.from-sdist` for overrides by @henryiii in #812
- Add `if.failed` (retry) by @henryiii in #820
- Add `if.scikit-build-version` by @henryiii in #851
- Packages can also be specified via a table by @henryiii in #841
- Move `cmake.targets` and `cmake.verbose` to `build.targets` and
  `build.verbose` by @henryiii in #793
- Support multipart regex using `result=` by @henryiii in #818
- Add `remove=` postprocess to regex by @henryiii in #828

Fixes:

- Warn if cmake/ninja in build system requirements by @henryiii in #803
- Detect manual generator setting for `get_requires_*` by @henryiii in #840
- Support nested and local gitignores by @henryiii in #827

Tests:

- Fix `test_cmake_config` if `CMAKE_GENERATOR` is already set by @lorepirri in
  #847

Internal:

- Pull out overrides to separate file by @henryiii in #821
- Nicer error/warning printer by @henryiii in #813
- Speed up CI for format job by @henryiii in #814
- Avoid old wheel warning in CI test job by @henryiii in #849

Documentation:

- Fix typo in projects list by @jcfr in #797
- Add disclaimer by @henryiii in #805
- Add pointer to itk by @thewtex in #817
- Add projects list by @henryiii in #788
- Examples nox job should use local copy of scikit-build-core by @henryiii in
  #810
- Expand defs and move schema by @henryiii in #795
- Hide deprecated options in README by @henryiii in #792
- Move overrides to page, expand by @henryiii in #815
- Use modern cmake/ninja version setting in Fortran example by @henryiii in #809

## Version 0.9.10

This release backports a couple of fixes made during work towards 0.10.

Fixes:

- Regression for `'-'` in version name by @henryiii in #834
- Improve version regex to capture typed version attributes by @maxbachmann in
  #816

## Version 0.9.9

This release backports a fix made during work towards 0.10.

Fixes:

- Strip epoch from `SKBUILD_PROJECT_VERSION` by @henryiii in #829

**Full Changelog**:
https://github.com/scikit-build/scikit-build-core/compare/v0.9.8...v0.9.9

## Version 0.9.8

This version ships a few more small fixes. Multi-target builds were missing
build arguments due to an exhausted generator. And some packages seem to
hard-code `${CMAKE_INSTALL_PREFIX}` in the `install()` call, which is an
anti-pattern, but we can set that variable too. More tests now run on Python
3.7.

Fixes:

- Empty build arguments for some targets in multi-target build by @junrushao in
  #784
- Support packages that hardcode `CMAKE_INSTALL_PREFIX` in their `install`
  commands by @henryiii in #786
- Logger shouldn't warn for missing lib on UNIX by @henryiii in #787

Tests:

- Use `ZipFile` instead of `zipfile.Path` to enable more tests on Python 3.7 by
  @henryiii in #785

## Version 0.9.7

This release makes a few small fixes, enabling better Fortran support and
correct tags on MUSL. And releases now have Attestations on GitHub at
<https://github.com/scikit-build/scikit-build-core/attestations>.

Fixes:

- Set `CC` and `CXX` from sysconfig if not set by @henryiii in #782
- `musllinux` tag incorrect by @henryiii in #773
- Logger unconditionally set to `DEBUG` in non-PEP 517 usage by @henryiii in
  #779

Documentation:

- Fix Fortran example by @henryiii in #771
- Fix typo in skbuild soabi docs by @henryiii in #775
- Fortran and Cython updates by @henryiii in #781

## Version 0.9.6

This release provides a fix for the experimental setuptools plugin leaking and
affecting other setuptools plugins.

Fixes:

- Improve error message when `metadata.version.provider` not set by @thewtex in
  #762
- Only inject logic if `cmake_*` keywords present by @kiwifb in #768
- Only replace color tags if the color is defined by @bnavigator in #764

## Version 0.9.5

This release fixes building for the Windows variant of free-threaded Python
3.13.

Fixes:

- Support Windows free-threading by @henryiii in #759
- Strip whitespace around generator so that it's passed through correctly by
  @vyasr in #748

Documentation:

- Note that `-C` options can be prefixed with `skbuild.` by @KyleFromNVIDIA in
  #754

CI and testing:

- Retry pypy if fails by @henryiii in #746
- Disable rpminspect on rawhide by @LecrisUT in #753
- Use uv for minimum version check by @henryiii in #679

## Version 0.9.4

This version supports the newly available free-threading variant of Python
3.13b1 (mostly related to skipping the stable ABI). We test this via the
manylinux/musllinux images. There's also a new feature requested by third-party
packagers; the ability to pass args directly to the build tool

Features:

- Add `build.tool-args` by @henryiii in #733

Fixes:

- Support free-threaded builds of Python 3.13+ on Linux by @henryiii in #741
- Slightly better stable ABI behavior using PyPy by @henryiii in #741

Documentation:

- Fix example of configuration overrides in configuration.md by @wu-vincent in
  #739
- Update stable ABI instructions by @henryiii in #740

CI and testing:

- Use pylint 3.2, gha reporter by @henryiii in #745
- Some minor improvements to running tests on some systems by @henryiii in #741

## Version 0.9.3

This version ensures the Hatchling plugin correctly indicates editable mode is
not yet supported, supports `CMAKE_ARGS` that have spaces, and has a bit of
other minor cleanup.

Fixes:

- Properly indicate lack of editable support in Hatch plugin by @ofek in #728
- Don't generate `entrypoints.txt` if none set by @henryiii in #729
- Don't warn if lib not found on UNIX, just debug by @henryiii in #730
- Support `CMAKE_ARGS` that may have spaces inside quotes by @vyasr in #727

Docs:

- Add FAQ entry on repairing wheels by @henryiii in #731

CI and testing:

- Use `macos-13` and `macos-14` explicitly by @henryiii in #724
- `macos-latest` is changing to `macos-14` ARM runners by @henryiii in #725

## Version 0.9.2

Quick fix for quick fix in 0.9.1; if `cmake` is a broken script (which can
happen if you pip install outside an environment then enter an environment,
there was an unbound local error instead of ignoring the broken cmake script.

Fixes:

- Unbound local error by @henryiii in #719

## Version 0.9.1

Quick fix for Pyodide (WebAssembly) builds.

Fixes:

- Try `--version` if `-E capabilities` fails by @henryiii in #717

## Version 0.9.0

This version adds the ability to `inherit` in override tables, matching a
similar feature added to cibuildwheel 2.17's overrides. You can now write out
extra metadata to `${SKBUILD_METADATA_DIR}`. A new Hatchling plugin is provided
as an experimental feature (will likely be made a separate package in the future
like the setuptools plugin).

The meaning of `wheel.exclude` has been changed to match on the wheel path,
rather than the source path. We could not find any projects that would be
affected by this change, so it was not added to the minimum-version protection
policy. This now allows you to ignore CMake outputs as well.

Features:

- Preserve additivity of `cmake.define` across `overrides` tables by @stubbiali
  in #564
- Add metadata dir access by @henryiii in #702
- Experimental hatchling builder by @henryiii and @aryamanjeendgar in #637
- Vendor pyproject-metadata by @henryiii in #703
- Always require pathspec by @henryiii in #711

Fixes:

- Exclude installed files if listed in exclude by @henryiii in #652
- Make `.git_archival.txt` reproducible by @LecrisUT in #706
- Use `cmake -E capabilities` instead of `cmake --version` by @KyleFromNVIDIA in
  #675
- Ensure many/musl tags not selected by @henryiii in #698
- purelib should set py3 tag if unset by @henryiii in #661
- Validate description for 0.9+ by @henryiii in #709
- Support bools in config settings by @henryiii in #712

API changes:

- `extra_settings` for SettingsReader by @henryiii in #697
- `GetRequires` args changed by @henryiii in #699
- Make `from_file` a little more powerful by @henryiii in #700
- Metadata is part of the build backend by @henryiii in #708

Documentation:

- `cmakelists.md` Windows `SOABI` suffix variable by @thewtex in #684
- Fix hatch init command by @thewtex in #677
- Fix install strip default by @henryiii in #681
- Improve `ninja.make-fallback` description in the README by @thewtex in #676
- Mention printouts by @henryiii in #660

CI and testing:

- Lower `pybind11` test dependency by @LecrisUT in #691
- Some cleanup from uv branch by @henryiii in #686
- Fedora CI maintenance by @LecrisUT in #689
- Small additions by @henryiii in #694
- Some changes from uv job by @henryiii in #693
- Fix setuptools on Python 3.12 by @henryiii in #701
- Fedora: Port downstream PR-49 by @LecrisUT in #678

## Version 0.8.2

This version fixes a few small issues related to configuration. The wheel tag is
fixed when `wheel.platlib` is False, inplace editable installs ignore
`build-dir`, and `install-dir` no longer affects the generate path.

Fixes:

- Ensure `wheel.platlib` being false sets `<abi>-<platform>` as `"none-any"` by
  @jcfr in #655
- Inplace editable install should ignore `build-dir` by @henryiii in #644
- `install-dir` shouldn't affect generate path by @henryiii in #654
- Expand info printing by @henryiii in #651

Documentation:

- Clarify requirement for using "inplace" editable mode by @jcfr in #643
- Update README to use modern GitHub admonition by @jcfr in #641
- be explicit about what it means to "use SKBUILD_SOABI" by @minrk in #646

## Version 0.8.1

This version fixes two small issues with specific situations: if ninja/cmake is
present but not executable, and ninja on Windows not respecting the build type.

Fixes:

- Do not exit with exec permission error in ninja check by @thewtex in #626
- Include `CMAKE_BUILD_TYPE` on Windows Ninja by @henryiii in #640
- Use `-` vs `_` in error message by @nbelakovski in #638
- Make run command logged at info by @LecrisUT in #639

Documentation:

- Warning about using `cmake.args` for defines by @LecrisUT in #620
- Correct API usage example by @henryiii in #627

## Version 0.8.0

This version replaces the `cmake`/`ninja` minimum-version config option with a
more powerful free-form version field. Scikit-build-core will now respect
`CMAKE_EXECUTABLE` for finding CMake. You can override based on the build state,
allowing overrides for editable installs, for example. You can specify a build
tag (AKA build number). And you can define CMake variables from environment
variables.

Features:

- Add `build-tag` by @henryiii in #612
- Add `if.state` to overrides by @henryiii in #600
- Add `cmake.version` and `ninja.version` by @henryiii in #602
- Support `CMAKE_EXECUTABLE` by @henryiii in #603
- Config to set CMake variables with environment variables by @stubbiali in #565

Fixes:

- Include license file entry in search by @henryiii in #601
- Make sure purelib is indicated by @henryiii in #613
- Project version should always be CMake parsable by @henryiii in #608

Tests and internal:

- Compare uncompressed files by @henryiii in #610
- A couple of minor cleanups by @henryiii in #599
- Some preview Ruff touchups by @henryiii in #617

## Version 0.7.1

This is a quick fix for a downstream change in hatch-fancy-pypi-readme that
broke our plugin wrapper.

Fixes:

- Patch for change in hatch-fancy-pypi-readme by @henryiii in #593

CI and tests:

- Remove deprecated mypy setting (now defaults on) by @henryiii in #589
- Group dependabot updates by @henryiii in #584
- Use downstream tmt plans by @LecrisUT in #518

Docs:

- Fix a link by @henryiii in #568

**Full Changelog**:
https://github.com/scikit-build/scikit-build-core/compare/v0.7.0...v0.7.1

## Version 0.7.0

This release features several large improvements to overrides: a new `if.any`
group to allow selections based on any item being true, and a new `if.env`
option for selecting an override based on environment variables. You can now
build pure Python packages with `wheel.cmake = false`, perfect for providing a
slower pure Python version of a package on unsupported systems via overrides.

There's also a new `inplace` mode for editable installs, which has drawbacks but
feels like the classic `"--inplace"` setting in setuptools and can enable some
tooling that would otherwise not support modern editable installs to work. If
you are using Cython to access `.pxd` files, modern ("redirect") editable
installs now support that. And to help avoid collisions with a future user
feature, config settings can now be passed with an optional namespace,
`skbuild.`, as well.

Features:

- Add inplace mode for editable installs by @henryiii in #553
- Add `wheel.exclude` by @henryiii in #560
- Support cmake-less runs (for overrides) by @henryiii in #550
- Support `if.any` by @henryiii in #548
- Support `if.env` by @henryiii in #549
- Support namespaced config settings (`skbuild.`) by @henryiii in #556

Fixes:

- Correct issue with editable template & add more tests by @henryiii in #552
- Support editable installs of Cython `.pxd` files by @vyasr in #516

CI:

- Fix spelling for Fedora by @henryiii in #559

Docs:

- Add meeting information by @henryiii in #555
- Update intro and mention cmeel by @henryiii in #551

## Version 0.6.1

Fixes:

- Editable package imports fix (regression in 0.6.0) by @henryiii in #546
- Filter `CMAKE_ARGS` and debug printout by @henryiii in #543

Docs:

- Fix bad config option name in `configuration.md` by @0xTowel in #530

Tests and internal:

- Add a bit to Ruff config by @henryiii in #544
- Support editable installs in downstream nox check by @henryiii in #533
- Use ruff-format by @henryiii in #536
- Small updates from repo-review by @henryiii in #537
- Refactor and unit test editable install by @henryiii in #545

## Version 0.6.0

This release features overrides, a system similar to mypy and cibuildwheel's
overrides, allowing static configuration of special cases, like different
settings per operating system or Python version ranges. It also features
preliminary support for `importlib.resources` in editable mode.

Features:

- Adding overrides by @henryiii in #514
- Overrides platform node by @0xTowel in #526
- Support `importlib.resources` in editable installs by @LecrisUT in #399

Fixes:

- Better handling for -G by @henryiii in #483
- Nicer error message when SCM version missing by @henryiii in #528
- (schema) Fix a typo and better metadata support by @henryiii in #522
- (setuptools) Remove `DEBUG` envvar by @henryiii in #527

Tests and internal:

- Use virtualenv instead by @henryiii in #371
- Pre-commit update & a couple of touchups by @henryiii in #519

Docs:

- Clarify verbosity when using `pip` by @LecrisUT in #513
- Build process and faq by @henryiii in #529

## Version 0.5.1

Features:

- Add `{build_type}` and `{state}` to `build-dir` by @henryiii in #504
- Include 'python' dir as an auto search path by @henryiii in #499

Fixes:

- Parse CMake version strings containing '-' by @jllllll in #508
- Set NumPy include directory if known by @henryiii in #482
- Adapt for `setuptools_scm` 8 writing change by @henryiii in #509
- (setuptools) Support `build_type` set in toml by @henryiii in #498

Tests and internal:

- Nicer nox for docs by @henryiii in #479
- Some extra Ruff checks by @henryiii in #478
- Packit sync by @LecrisUT in #476

Docs:

- Fix template-file with template-path by @Freed-Wu in #485
- `wheel.py.api` -> `wheel.py-api` by @njzjz in #488
- A single-letter change in Configuration by @wojdyr in #490
- Fix typo in `SKBUILD_CMAKE_DEFINE` env var by @aloisklink in #501
- Typo in Configuration by @elazarcoh in #493
- Update and add discord link by @henryiii in #477
- Add page on cross-compiling by @henryiii in #510

## Version 0.5.0

This release sees the addition of a generated schema, which has also been
contributed to SchemaStore, enabling `tool.scikit-build` to be understood by
most editors. There's also now a way to enable CMake during the SDist step, a
new regex plugin, and a mechanism to write metadata to a file without having to
depend on the plugin.

Features:

- Add option to run CMake during SDist creation by @henryiii in #454
- Add a schema for validate-pyproject by @henryiii in #447, #450, #455
- Added regex plugin and dynamic-metadata rewrite by @henryiii in #457
- Add configuration option to write metadata to file by @henryiii in #459

Fixes:

- Normalize sdist names by @henryiii in #434
- Report cmake/ninja required if already present by @henryiii in #462

Tests and internal:

- Support Literals in settings by @henryiii in #460
- Clean up some extraneous types by @henryiii in #461
- Use 2x faster black mirror by @henryiii in #456
- Fix Fedora CI by @LecrisUT and @henryiii in #449, #464, #469
- Increase timeout (PyPy slow) by @henryiii in #465
- Cleaner Fedora testing by @LecrisUT in #470

Docs:

- Fix error in config names by @jpn-- in #453
- More generation of docs by @henryiii in #452
- Require Sphinx >= 7 while waiting on Furo by @henryiii in #473
- Require Sphinx < 7.2 while waiting on Setuptools by @henryii in #473
- Fix an import check issue by @LecrisUT in #471

## Version 0.4.8

This release focus on two fixes that correct some interference issues with other
setuptools plugins. A few new features were added (opt-in only): the ability to
select build targets, install components, and opt-in `--strip` (will be opt-out
in 0.5 if the minimum-version is set to 0.5+ or unset).

Features:

- Add build target support by @henryiii in #432
- Add component support and strip support by @henryiii in #430

Fixes:

- (setuptools) Avoid instantiating build too soon by @henryiii in #443
- (setuptools) Avoid interfering with other setuptools plugins by @henryiii in
  #414
- Only link to valid module paths (not things like gitignore) in editable
  installs by @henryiii in #444

Docs:

- Fix typo and invalid Markdown in `getting_started.md` by @0xTowel in #439
- Conf tabs as extension by @henryiii in #433
- Fix `nanobind`/`pybind11` `src` & sp-dev by @henryiii in #429
- Link to source by @henryiii in #431
- Small suggestions for docs by @rebecca-burwei in #428

Tests and other:

- Fix fedora downstream tests by @LecrisUT in #416
- Ruff moved to astral-sh by @henryiii in #418
- `target-version` no longer needed by Black or Ruff by @henryiii in #419
- Use `get_origin`/`get_args` by @henryiii in #423

## Version 0.4.7

This version fixes a unused variable message in 0.4.6, along with a debug
logging improvement, and a few test fixes, including a regression in the recent
noxfile reworking.

- fix: remove `SKBUILD_STATE` unused message when building by @henryiii in #401
- fix: logging environment should use reprs by @henryiii in #409

Tests and CI:

- Support running tests with `NO_COLOR` by @henryiii in #407
- `noxfile.py` added to mypy, two fixes by @henryiii in #408
- Get packages of interest from `pyproject.toml` by @henryiii in #402
- Enable more tests in the spec file by @LecrisUT in #400

## Version 0.4.6

This release has one small new feature (access to `${SKBUILD_STATE}` from
CMake), and fixes an issue when adding read-only files on Windows with Python
3.7. Some testing and docs infrastructure updates should make it easier for
downstream packagers to ship scikit-build-core.

Fixes:

- Provide access to current state in CMake by @henryiii in #394
- Support building older versions of `setuptools_scm` by @henryiii in #390
- Workaround for Windows Python 3.7 `TemporaryDirectory` bug by @henryiii in
  #391

Tests:

- Rework testing extras by @henryiii in #395 and #393
- Add `network` marker by @henryiii in #379

CI:

- Add example tests to Fedora packaging by @LecrisUT in #378
- Fedora: Correct rsync rule by @LecrisUT in #389
- Use `not network` for spec by @henryiii in #383

Docs:

- Add migration guide by @vyasr in #356
- Support building the documentation as a man page by @henryiii in #372
- Add nanobind example by @henryiii in #375
- Use `UseSWIG` for swig by @henryiii in #377
- Fix or hide nitpicks by @henryiii in #370

## Version 0.4.5

This version fixes issues with output being incorrectly interleaved with logging
messages. Symlinks are now followed when making SDists. And finally,
`SKBUILD_SOABI` is now correctly set when cross-compiling on Windows (Warning!
FindPython still does not report the correct SOABI when cross-compiling to ARM).

Fixes:

- Proper printout ordering and more displayed details by @henryiii in #365
- Sort `RUNENV` debugging log output by @jameslamb in #357
- Follow symlinks when making SDists by @henryiii in #362
- Report correct ABI when cross-compiling by @henryiii in #366

Tests:

- Fedora downstream CI by @LecrisUT in #358
- Add downstream examples by @henryiii in #363
- Add testing for scripts processing by @henryiii in #364

## Version 0.4.4

This version fixes some issues cross-compiling to Windows ARM when making
Limited API / Stable ABI extensions, and supports multiple config generators in
editable mode.

- Conditional ABI3 logic fixed by @henryiii in #352
- Set `Python_SABI_LIBRARY` by @henryiii in #352
- Editable installs now support multiconfig generators by @henryiii in #353

## Version 0.4.3

This adds support for CPython 3.12.0b1, and improves Stable ABI / Limited API
support (supported by an upcoming nanobind for Python 3.12). An editable install
fix allows running from any directory.

Fixes:

- Allow CMake to detect if limited API is targeted by @henryiii in #333 and #342
- Make abi3 support conditional on Python version by @henryiii in #344
- Windows path correction for 3.12.0b1 by @henryiii in #346
- Editable path needs to be absolute by @henryiii in #345

Other:

- Add 3.12.0b1 by @henryiii in #341
- Refactor settings by @henryiii in #338
- Document that `CMAKE_ARGS` supports space separators by @henryiii in #339

## Version 0.4.2

This is a quick followup to LICENSE file handing to closer match the current
draft of [PEP 639](https://peps.python.org/pep-0639). It also removes the
automatic optional Rich logging, which doesn't work well with Pip's subprocess
piping, being cropped to a very narrow width regardless of terminal size.

Fixes:

- Add `License-file` metadata entry & update default by @henryiii in #329
- Drop optional Rich logging/error by @henryiii in #330

Other:

- Update PyPI links by @henryiii in #331

## Version 0.4.1

A fix for LICENCE files being placed in the wrong place in the wheel. Now we
follow hatchling's structure of placing them in `*.dist-info/licenses`.

Fixes:

- LICENCE files were placed in the wrong place by @henryiii in #325

Other:

- Fix rpm inspect test failures by @LecrisUT in #324

## Version 0.4.0

An important fix/feature: LICENSE files were not being included in the wheel's
metadata folder. You can configure the license file selection via a new
configuration option, and a reasonable default was added. You can now select a
source directory for your CMakeLists.txt. A lot of work was done on the still
experimental setuptools backend; it still should be seen as completely
experimental while it is being finished.

Features:

- `cmake.source-dir` for CMakeLists in subdirectories by @henryiii in #323
- Add `LICENSE` file option by @henryiii in #321

Fixes:

- Ninja wasn't being used if present by @henryiii in #310
- Wheels were not including the `LICENSE` file by @henryiii in #321

Setuptools plugin:

- Refactor plugin as custom setuptools command by @henryiii in #312
- Adding `cmake_args` by @henryiii in #314
- Add wrapper for `skbuild.setup` compat by @henryiii in #315

Other:

- Add rpmlint and smoke tests by @LecrisUT in #313

## Version 0.3.3

This version improves WebAssembly support (Pyodide) and fixes a reported bug in
the new editable mode.

Fixes:

- Support prefix dir if toolchain has `CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY`
  by @henryiii in #303
- Find wheel files before local files in editable installs by @henryiii in #305

Other:

- Use PyPI's new trusted publisher deployment by @henryiii in #306

## Version 0.3.2

Some small fixes for edge cases. Several docs improvements, too.

Fixes:

- Suppress Unicode errors in scripts dir and move on by @henryiii in #294
- Specify platform properly for non-MSVC Windows by @henryiii in #295

Docs:

- Doc updates by @zerothi in #287
- Add a bit to plugin instructions by @henryiii in #289
- Typos fixed by @afh in #291 and #292

## Version 0.3.1

This is a small release fixing a regression in some cases caused by adding
`Python_LIBRARY`. This has been reverted on non-Windows platforms, since it is
only needed on Windows.

Fixes:

- Support older setuptools-scm by @henryiii in #284
- Only set the lib for FindPython on Windows by @henryiii in #285

Docs:

- Fix incorrect tool name by @henryiii in #276
- Typo on tab Fortran (was Cython) by @zerothi in #279
- Fix wheel.packages by @henryiii in #282

Other:

- Change Fedora PR targets by @LecrisUT in #273

## Version 0.3.0

This version brings two new dynamic metadata plugins (wrappers for
`setuptools_scm` & `hatch-pypi-fancy-readme`). Third-party packages can now add
entry-points declaring `CMAKE_PREFIX_DIR` and `CMAKE_MODULE_DIR` entries.
Support has been added for requesting metadata without building. And
experimental support was added for editable installs, including an option for
automatic rebuilds.

Several fixes have been added as well, like SABI support, ARM cross-compiling
support for FindPython, scripts entries now process shebang lines, and setting a
`build-dir` with `{wheel_tag}` was not working before. The docs have been
started, with a quickstart for common situations, a page on configuration, and
some info on authoring a CMakeLists.

Features:

- Support dynamic metadata by @bennyrowland in #197 and rework by @henryiii in
  #251
- Support modules/prefix dirs by @henryiii in #255
- Add `get_requires_for_dynamic_metadata` by @henryiii in #235
- Make setuptools wrapper more generic by @henryiii in #225
- Experimental support for editable installs by @henryiii in #212, #268, and
  #271

Fixes:

- CMake 3.26.0 (exactly) needs the backport too by @henryiii in #238
- Add python library artifact for better Windows cross compiling by @henryiii in
  #263
- Include 3.26.1 SABI fix by @henryiii in #227
- Restructure `get_requires` & fix some ninja paths by @henryiii in #250
- Support script rewriting by @henryiii in #254
- Version not a string (typing updates) by @henryiii in #231
- `{wheel_tag}` was not working by @henryiii in #262
- `CMAKE_PREFIX_DIR` and `CMAKE_MODULE_DIR` are passed in the init cache file to
  remove a unused variable warning by @henryiii in #272
- Support color printouts without Rich (pip requires `FORCE_COLOR`) by @henryiii
  in #266

Other things:

- Add Fortran testing and CI by @henryiii in #86
- Avoid internet usage in non-isolated testing by @henryiii in #247
- Add an SDist checker & fix contents by @henryiii in #253
- Add more setuptools types by @henryiii in #233
- Add FedoraProject rpm spec file by @LecrisUT in #201 and #241
- Better coverage handling by @henryiii in #270

## Version 0.2.2

This release makes a small improvement to the wheel file permissions (in line
with wheel 0.40). It also ensures the test suite will still pass in an
environment with `SOURCE_DATE_EPOCH` already set. A few internal changes are
paving the way to 0.3.0.

Fixes:

- zipinfo should report regular files by @henryiii in #220

Tests:

- Support running in environments with `SOURCE_DATE_EPOCH` set by @LecrisUT in
  #221
- Report self version too by @henryiii in #222

Other things:

- refactor: use `from_pyproject` by @henryiii and @bennyrowland in #224
- chore: fix a mypy complaint on Windows by @henryiii in #217
- docs: add quickstart by @henryiii in #226

## Version 0.2.1

This release fixes the tag for Windows ARM wheels, and has some internal
refactoring to prepare for the next new features. A new `{wheel_tag}` value is
available for `build-dir`. Some basic setup was done on the docs, as well. Debug
logging and test output has been improved a little, as well.

Changes:

- Add `{wheel_tag}` for `build-dir` by @henryiii in #207
- Support for conda's `CMAKE_SYSTEM_PROCESSOR` by @henryiii in #207

Fixes:

- Windows ARM tag by @henryiii in #215
- Include Windows ARM in known wheels by @henryiii in #203
- Print out paths by @henryiii in #205

Other things:

- docs: update readme for 3.26 backport by @henryiii in #206
- tests: support running tests with system `cmake3` visible by @LecrisUT in #211
- tests: nicer exit, minor refactors by @henryiii in #213
- refactor: minor changes & nicer environment logging printout by @henryiii in
  #214

## Version 0.2.0

This version adds local build directory support - you can now set `build-dir`
and reuse build targets. This does not yet default to on, so please test it out.
This can dramatically speed up rebuilds. If you want to mimic setuptools, you
can set this to `build/{cache_tag}`. Or you can chose some other directory, like
scikit-build classic's `_skbuild`. Along with this, we now have a native wheel
writer implementation and support `prepare_metadata_for_build_wheel`.

Scikit-build-core now also contains a backport of FindPython from CMake 3.26,
which fixes SOABI on PyPy and supports the Stable ABI / Limited API.

Features:

- Local build directory setting & build reuse by @henryiii in #181
- Add `prepare_metadata_for_build_wheel` by @henryiii in #191
- Native wheel writer implementation by @henryiii in #188
- Use 3.26 dev version port of FindPython by @henryiii in #102

Tests:

- Allow pytest 7.0+ instead of 7.2+ by @henryiii in #200
- Include cmake and ninja if missing in nox by @henryiii in #190
- Simpler pytest-subprocess by @henryiii in #159

Other things:

- chore: Python 3.11 Self usage by @henryiii in #199
- chore: fix Ruff configuration by @henryiii in #186
- chore: minor adjustments to wheel returns by @henryiii in #195
- chore: remove duplicate Ruff code by @burgholzer in #184

## Version 0.1.6

Fixes:

- Handle local cmake dir for search by @henryiii in #179
- Avoid resolving cmake/ninja paths by @henryiii in #183

Other things:

- Use Ruff by @henryiii in #175
- Ruff related additions by @henryiii in #180
- Add `isolated` marker to `test_pep518_sdist` by @bnavigator in #182

## Version 0.1.5

Fixes:

- Ninja path not being set correctly by @henryiii in #166
- Minor touchup to ninja / make by @henryiii in #167

## Version 0.1.4

Fixes:

- `entrypoints.txt` should be `entry_points.txt` by @njzjz in #161
- `EXT_SUFFIX` is wrong before 3.8.7 by @henryiii in #160
- Make tests pass on native Windows ARM by @henryiii in #157
- Windows ARM experimental cross-compile support by @henryiii in #162

Other things:

- Fix spelling mistake by @maxbachmann in #156
- Add Python 3.12 alpha 3 to the CI by @henryiii in #120
- Fix issues mocking in tests with packaging 22 by @henryiii in #155

## Version 0.1.3

Fixes:

- Issue with experimental extra directory targeting by @henryiii in #144
- Sort SDist filepaths for reproducibility by @agoose77 in #153

## Version 0.1.2

Features:

- Provide null directory (not installed) by @henryiii in #143

Fixes:

- Fix issue with 32-bit Windows in 0.1.1 by @henryiii in #142

## Version 0.1.1

Fixes:

- Windows non-default generators by @henryiii in #137
- Compute the correct default generator for CMake by @henryiii in #139

Testing:

- Support make missing by @henryiii in #140
- Clear `CMAKE_GENERATOR` by @henryiii in #141

## Version 0.1.0

First non-prerelease! Scikit-build-core is ready to be used. The remaining
limitations (like support for editable mode and build caching) will be addressed
in future releases. If you set `tool.scikit-build.minimum-version = "0.1"`,
scikit-build-core will try to respect old defaults when new versions are
released.

## Version 0.1.0rc2

Still preparing for release. One small addition to the error printout.

Features:

- Did you mean? for config-settings and pyproject.toml by @henryiii in #135

Testing:

- Split up isolated and virtualenv fixtures by @henryiii in #134

## Version 0.1.0rc1

Preparing for a non-beta release.

Fixes:

- Paths on Windows by @henryiii in #126
- Support pre-set generators by @henryiii in #118
- Warn on scripts with invalid shebangs by @henryiii in #132
- Minimum constraints now set by @henryiii in #129

Refactoring:

- Rename pyproject -> build dir by @henryiii in #121

Testing:

- Add msys2 to the CI by @henryiii in #119
- Add test report header by @henryiii in #124
- Test min constraints without Windows by @henryiii in #129
- Remove pytest-virtualenv by @henryiii in #125 and #131
- Mark unimportant test xfail non-strict for conda-forge by @henryiii in #108

## Version 0.1.0b2

A quick fix for macOS universal2 tags not expanding when enabled.

Fixes:

- Expand macos tags missing by @henryiii in #105

Other things:

- Add tests marker for PEP 518 by @henryiii in #104
- Require C++11 only in tests by @henryiii in #106
- Xfail a non-important test by @henryiii in #107

**Full Changelog**:
https://github.com/scikit-build/scikit-build-core/compare/v0.1.0b1...v0.1.0b2

## Version 0.1.0b1

This release is focused on preparing for conda-forge and some macOS fixes.

Features:

- Configuration setting for FindPython backport by @henryiii in #103

Fixes:

- Conda prefix lib support by @henryiii in #95
- Guess single config for more generators by @henryiii in #101
- Universal2 tags computation was incorrect by @henryiii in #97
- Universal2 tags computation was incorrect again by @henryiii in #100

Refactoring:

- Rename extra color -> rich by @henryiii in #98

Other things:

- Run more tests without the cmake module by @henryiii in #96
- Support running without pytest-virtualenv by @henryiii in #94

## Version 0.1.0b0

This release adds a lot of configuration options, including `minimum-version`,
which can be set to 0.0 to ensure defaults remain consistent (similar to
`cmake_minimum_required`).

Features:

- Dict options by @henryiii in #78
- Min version setting by @henryiii in #84
- Strict configuration checking by @henryiii in #75
- Support for args/define by @henryiii in #83
- Support for other wheel dirs by @henryiii in #82
- Support specifying a build type by @henryiii in #90

Fixes:

- Better logging by @henryiii in #88
- Better macOS deployment target handling by @henryiii in #74
- Don't touch mtime in non-reproducible mode by @henryiii in #76
- Fallback to ninja sooner if on known platform by @henryiii in #80

Refactoring:

- Rename CMakeConfig -> CMaker by @henryiii in #91
- Drop config prefix by @henryiii in #77
- Rename to `wheel.py-api` and expand, ignore on non-cpython / old cpython by
  @henryiii in #81

Other things:

- Add cygwin by @henryiii in #89

## Version 0.1.0a1

This release brings a lot of further development. This is starting to be used by
downstream projects; it is a good idea to be a little careful with versions
still, configuration may change.

Features:

- Allow python packages to be specified by @henryiii in #58
- Autocopy packages if names match by @henryiii in #53
- Include/exclude by @henryiii in #59
- Color status messages for wheel by @henryiii in #60
- Support reproducible sdist builds by @agoose77 in #64
- Prettier logging with config setting by @henryiii in #40
- Add `extra-tags` by @henryiii in #49
- Support for setting python & abi tag (including limited API) by @henryiii in
  #47
- (setuptools) Use setup keyword support by @henryiii in #42
- (setuptools) `cmake_source_dir` from scikit-build classic by @henryiii in #45

Fixes:

- Avoid copy, avoid failure if pre-existing by @henryiii in #41
- Better support for FindPython by @henryiii in #38
- Fallback to make if available (setting) by @henryiii in #57
- Handle `PermissionError` in reading `libdir.is_dir()` by @agoose77 in #43
- Include `--config` when installing by @henryiii in #61
- Incorrect min version of macOS by @henryiii in #50
- Lists and bool settings by @henryiii in #56
- Mkdir for sdist if missing, test polish by @henryiii in #44
- Simple example PyPy support workaround by @henryiii in #37

Refactoring:

- Tags configuration group by @henryiii in #55
- (setuptools) Use native bdist_wheel setting for abi3 by @henryiii in #52
- Rename `cmake_settings` to `skbuild_settings` by @henryiii in #46
- Refactor wheel code a bit to read better by @henryiii in #65

Other things:

- Better logging on macOS for deployment target by @henryiii in #48
- Format cmake files by @henryiii in #54

## Version 0.1.0a0

First experimental snapshot.
