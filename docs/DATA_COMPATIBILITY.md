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

Logical material assignments use `cadgit.material-library.v1` in
`required_features`, including selections saved in draft recipes. Assemblies and
asset revisions carry the same gate. Older readers must reject these semantics
rather than silently discard a logical material assignment. Legacy captured
native shader IDs retain their original meaning.

Prepared B-rep input bundles use `cadgit.brep-job.v1` and live in a separate
`artifacts/brep_jobs` collection. They do not change snapshot/assembly meanings or
replace normal Rhino mesh handoffs. A prepared job is not a reconstructed result.

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
know every property in advance. Git CAD's selected-subtree composition copies USD
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

## Publication and recovery outcomes (November 9 working tree)

A publication point and a durability confirmation are distinct. Once an exact
revision, pointer or configuration is visible, a later directory-sync/event-log
failure returns its committed identity with `publication_warning` where the API
returns a record. The UI retains that warning through background presentation.
Destination-tagged `PublishedWriteError` identifies an already-visible external
file when a low-level path-returning API cannot carry a structured warning.
Prepublication failure preserves prior authoritative state. Unreadable outcomes
are reported as uncertain rather than rolling back a potentially published pointer.

Verification follows exact snapshot parents/import provenance, assembly selections,
native materials and library parent/dependency links. Save parents must be snapshots
of the same source; cross-source provenance belongs in `imported_from`. Library
relationship role names remain extensible and are not interpreted as scene roles.
Inventoried assembly recipes must agree with their manifest selections/bindings,
including preserved additive selection data. Per-call iterative traversal checks
each reachable revision once and bounds diagnostics for shared/cyclic ancestry.

New native material records use `capture_attempt_id` for an attempt that may fail
before its snapshot commits. Existing manifests are never rewritten. A captured
material's bytes may survive and be reused by a later successful capture; the
successful snapshot pins that exact material revision.

Inbox producers publish `ready.json` last and must keep that capture directory
immutable afterward. New service ingests record `metadata.inbox_input_digest` for
the ready marker, USD input and optional frozen native input. Receipt recovery
requires exact source plus capture ID, healthy archived history and matching input
identity before native cleanup. Changed inputs are retained with an error; legacy
records without an input digest retain native input and report `cleanup_warning`.
No hash is retroactively invented for legacy inputs. Unsafe symlinked inbox paths
are rejected before locks or diagnostic writes. Digest samples detect changes at
these boundaries; they do not provide synchronization with arbitrary external
writers that ignore the immutable-ready producer contract.

These changes are tracked in [the ongoing verification review](REVIEW_FULL_VERIFICATION.md).
Final build/native/reviewer gates and the entire-project coverage target remain
separate from these local implementation contracts.
