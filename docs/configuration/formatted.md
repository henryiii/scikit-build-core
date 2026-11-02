# Formattable fields

The following configure keys are formatted as Python `str.format` templates:

- `build-dir`
- `build.requires`
- `editable.rebuild-dir`

```{versionadded} 1.0
`editable.rebuild-dir` is formattable.
```

```{versionadded} 1.1.2
`{build_dir}` in `editable.rebuild-dir`.
```

For example, to get a persistent build directory per wheel tag:

```toml
[tool.scikit-build]
build-dir = "build/{wheel_tag}"
```

The available variables are the members of
{py:class}`scikit_build_core.format.PyprojectFormatter`:

```{eval-rst}
.. autoattribute:: scikit_build_core.format.PyprojectFormatter.build_dir
   :no-index:

.. autoattribute:: scikit_build_core.format.PyprojectFormatter.build_type
   :no-index:

.. autoattribute:: scikit_build_core.format.PyprojectFormatter.cache_tag
   :no-index:

.. autoattribute:: scikit_build_core.format.PyprojectFormatter.name
   :no-index:

.. autoattribute:: scikit_build_core.format.PyprojectFormatter.root
   :no-index:

.. autoattribute:: scikit_build_core.format.PyprojectFormatter.state
   :no-index:

.. autoattribute:: scikit_build_core.format.PyprojectFormatter.wheel_tag
   :no-index:
```
