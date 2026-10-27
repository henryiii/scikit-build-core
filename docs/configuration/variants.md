# Building wheel variants

```{versionadded} 1.0

```

```{warning}
This is an early preview of [PEP 817][] wheel variant support. The interface may
change, and it must be opted into with `experimental = true`.
```

Scikit-build-core can attach variant metadata to a wheel, producing a
variant-labeled filename (the label becomes the final field of the wheel name)
and a `variant.json` file inside `*.dist-info`. This lets you ship several
wheels for the same version that differ by hardware or library features (CPU
ABI, CUDA version, BLAS implementation, etc.).

## Declaring providers

Every namespace you provide must have a provider declared in the `[variant]`
table of `pyproject.toml`, and must be listed in `default-priorities`:

```toml
[variant]
"$schema" = "https://variants-schema.wheelnext.dev/v0.2.0.json"

[variant.default-priorities]
namespace = ["x86_64"]

[variant.providers.x86_64]
requires = ["provider-variant-x86-64>=0.0.1"]
plugin-api = "provider_variant_x86_64.plugin:X8664Plugin"
```

## Selecting a variant

Because each variant of a build needs different settings, the variant options
are **only allowed in config-settings or `[[tool.scikit-build.overrides]]`**;
they cannot be hard-coded at the top level of `pyproject.toml`. The relevant
settings are:

- `variant` / `variant-name`: variant properties in
  `namespace :: feature :: value` form (repeatable).
- `variant-label`: override the computed label used in the wheel filename.
- `null-variant`: build the null variant (mutually exclusive with the above).

When any of these are set, [`variantlib`][] is automatically injected as a build
requirement, and the experimental flag must be enabled. For example, with `pip`:

```bash
pip wheel . \
  -Cexperimental=true \
  -Cvariant="x86_64 :: level :: v3" \
  -Cvariant-label=x86_64_v3
```

This produces a wheel ending in `-x86_64_v3.whl`. To build the null variant
instead, pass `-Cnull-variant=true`.

You can also set `experimental = true` under `[tool.scikit-build]` instead of
passing it every time.

For more information you can see the available PEPs:

- [PEP 817][]: the overview of the wheel variant proposal
- [PEP 825][]: the wheel variant format
- [PEP 850][]: variant providers and the `[variant]` table

<!-- prettier-ignore-start -->

[pep 817]: https://peps.python.org/pep-0817
[`variantlib`]: https://github.com/wheelnext/variantlib
[pep 825]: https://peps.python.org/pep-0825
[pep 850]: https://peps.python.org/pep-0850

<!-- prettier-ignore-end -->
