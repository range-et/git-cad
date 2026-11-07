# Material library implementation and review

Implemented 2026-11-07 from independent architecture and UX scoping. Both agents
then audited the first implementation and rechecked fixes. The supported scope is
in [the V1 specification](MATERIAL_LIBRARY_V1.md); onboarding is covered by the
[agent-agnostic portbook](../skills/cad-git/references/material-library.md).

## Findings and corrections

Architecture review found definition/manifest integrity gaps, unsafe asset paths,
incomplete validation, provenance loss and logical-material/native-appearance
identity problems. Fixes validate immutable definitions and dependencies, preserve
unknown fields and sources, and separately track logical assignments and the actual
captured native appearance. Required-feature gates also cover draft selections.

Native rechecks exposed additional texture and return-path defects. The corrected
Blender loader maps original image datablock identities even after Blender renames
them, retains the archived graph path, and saves absolute dependency paths before
publishing the final working file. Canonical USD tags now match the captured shader
revision, including after export and re-ingestion. A real isolated Blender test
deleted originals and reopened the final published file successfully.

UX review found stale actions after filtering, lossy material editing and hidden
partial-import failures. Fixes clear filtered selection, preserve complete nested
definitions and precision, and report successful IDs alongside failures. Search
uses a cached catalog and debounce; thumbnails are cached and bounded. Follow-up
polish rejects duplicate map roles and empty graph image names, preserves reference
metadata on replacement, and describes unsupported native previews honestly.

Independent rechecks found no remaining P1 in exercised workflows. This is bounded
evidence, not a claim that every native format or renderer has been validated.

## Evidence

- [Initial architecture audit](research/material-library-architecture-audit-2026-11-07.json)
  and [post-fix recheck](research/material-library-architecture-recheck-2026-11-07.json).
- [Initial UX audit](research/material-library-ux-audit-2026-11-07.json)
  and [post-fix recheck](research/material-library-ux-recheck-2026-11-07.json).
- `tests/test_library.py`, `tests/test_native_adapter_recovery.py` and
  `tests/integration/material_library_smoke.py` cover immutable revisions, pinned
  dependencies, editor preservation, filtering, partial imports and assignment.

## Remaining boundaries

Same-identity material branches, graph-node/pixel editing, solver evaluation,
per-face native shader restoration and general renderer interchange remain deferred.
Generic asset export exports that asset, not a complete dependency bundle.
Portable USD maps support a limited set of roles/color spaces and require usable
UVs; the manager viewport does not evaluate Cycles. Engineering values are sourced
records, not certified simulation inputs. Poliigon integration opens the website
and imports local downloads. Large catalogs still need persistent indexing and
virtualization beyond the current in-memory caching.
