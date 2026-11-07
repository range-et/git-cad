# Additive data compatibility

This is a V1 data contract and a requirement for future releases. It applies to
project configuration, manifests, assembly selections, material records and USD
payloads. The application's package/UI version is independent of the data format.

## Version rules

- `schema_version: 1` identifies the format's major version. Existing field names,
  types, units, meanings, IDs and reference semantics remain stable within it.
- Optional `schema_minor` defaults to `0` for existing records. Adding optional
  fields with safe defaults is a compatible extension. A higher minor value alone
  does not prevent loading a record.
- Missing fields retain their historical defaults. A new field cannot become
  mandatory for existing V1 data. Changing a historical default's meaning is not
  an additive change.
- `required_features`, absent by default, lists behavior a reader must understand
  to use the data correctly. An unknown required feature blocks interpretation or
  mutation with an explicit error. Authors must use this gate when an extension
  changes geometry, bindings, evaluation or other operation semantics.
- Incompatible major formats are rejected without automatic migration. A future
  major release must retain readers for existing V1 data. Any migration must be
  explicit, preserve originals and references, and be tested independently; no
  general migration engine is currently implemented.

Historical material fixtures without a version field remain readable through the
legacy-record path. New project configurations must have an explicit major version.

## Preserve unfamiliar data

Typed models retain unfamiliar fields when validating and serializing. Readers
must not reduce an entire record to only the fields known to a particular UI.
Known-field edits must preserve unrelated data in mutable configuration/pointers.
Immutable committed history is never rewritten merely because a new app opens it.

New feature/provider data should use a namespaced key in `extensions`, for example:

```json
{
  "schema_version": 1,
  "schema_minor": 0,
  "required_features": [],
  "extensions": {
    "org.cadgit.materials.engineering": {
      "density": {"value": 7850, "unit": "kg/m3"},
      "youngs_modulus": {"value": 210000000000, "unit": "Pa"}
    }
  }
}
```

This is an extension-format example, not an implemented engineering solver.
Missing engineering data means unspecified, not zero. Appearance, physical
properties and application-specific definitions may evolve separately. New
material values create a new revision; existing assemblies keep their pinned
revision. Optional fields must not silently change a historical result.

## OpenUSD's role

OpenUSD permits custom attributes and relationships without requiring our tool to
know every property in advance. CAD-GIT's selected-subtree composition copies USD
scene specs rather than rebuilding an assembly from the viewport's mesh data.
Regression tests verify unfamiliar geometry and material attributes survive this
path. This does not promise preservation of properties outside the selected
subtree or every native application's import/export behavior.

USD extensibility does not automatically make our JSON records, native shader
libraries, plugins or exporters compatible. Unknown data must be retained, and
unsupported semantics must be gated. A newer `.blend`, renderer or plugin can
still require a compatible native application; preserving its bytes does not
ensure every application version can evaluate it.

References: [OpenUSD custom attributes](https://openusd.org/release/api/class_usd_attribute.html),
[OpenUSD schema versioning](https://openusd.org/release/wp_schema_versioning.html).

## Regression and release gate

Run `uv run pytest -q` for every release. Tests include frozen original V1 JSON
fixtures and exercise:

- Opening and reusing old records without rewriting their original bytes.
- Preserving unfamiliar nested selection fields in assembly manifests and recipes.
- Keeping new material parameters and configuration extensions intact.
- Retaining unfamiliar USD geometry and bound-material attributes in composition.
- Rejecting unsupported major versions or required features without changing the
  original record, including configuration changed while the application is open.
- Preserving unrelated main-pointer extensions when selecting a new assembly.

Keep the original fixture files unchanged. Add fixtures and compatibility cases as
new record fields or providers ship. Future releases must continue to pass these
checks; a UI redesign alone must require no history migration.
