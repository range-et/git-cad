# Materials & Assets workspace — V1 implementation specification

Status: implemented and independently re-audited, 2026-11-07. Synthesized from independent material
architecture and UI/UX scoping agents, including the user's requirement that images
and other files have the same first-class revision/lineage model as materials.
See [review results and limitations](MATERIAL_LIBRARY_REVIEW.md).

## Product promise

Every project has two independent workspaces: Geometry and Materials & Assets.
The latter browses physical/appearance materials, image assets, native shader
files and supporting documents. Each item has a stable identity and immutable
revisions. A material revision pins the exact versions of the assets it uses.
New files or property revisions never silently change old assemblies/materials.

PLA is a material identity, not a Blender graph name. It may have sourced physical
properties, a display appearance, a native Blender graph, texture-map inputs and
specification documents. Missing physical values are unspecified; no authoritative
engineering constants are inferred from a material's name or image.

## Data model and storage

One generic revision envelope serves all item kinds: material, image, document,
shader, texture_set and other. It includes stable asset_id; opaque immutable id;
revision number; label/kind/tags; parent revisions with roles; pinned dependencies
with roles; provenance (provider, source URL, creator, external ID, license name,
license URL and notes); files/hash inventory; entry_layer; additive extensions.

New durable data lives in `library/revisions/<revision-id>/`, with manifest,
COMMITTED marker, and either archived payloads or definition.json. An ownership
marker `library/library.json` binds it to the project. Existing nonempty unrelated
folders must not be taken over. The catalog can be rebuilt from committed records.
Existing flat `materials/<mat_*>` records remain unchanged and visible as captured
native shaders, with honest legacy identity rather than fabricated history.

A material's definition separates:

- physical.properties: each value has unit, status, source/conditions as available;
- appearance.preview: basic color/roughness/metallic for inspection;
- appearance.native_graph: an exact captured/native shader revision;
- appearance.maps: role and color-space entries pointing to exact image revisions;
- documents: specification/supporting revision references.

All parent and dependency references are explicit revision IDs. Imported images
are independent assets. Deriving an edited image imports the new pixels and records
its inputs and operation note; V1 does not implement an image editor. File imports
archive bytes without executing code or extracting ZIP files.

Same-asset revisions use compare-and-swap against the selected current revision.
Editing an outdated head fails explicitly. Derive creates a new identity linked to
historical inputs; same-identity named branch management is deferred. Recombination
selects physical data from revision A and appearance from revision B, preserving
both donors and pinned inputs. It does not average engineering data or merge shader
nodes. Unknown extension fields survive edits.

## Interfaces and geometry assignment

Library operations are available through core APIs and CLI: list/search, inspect,
history, import, revise, derive, create/revise material, recombine, verify, used-by,
and non-overwriting asset export. AI/MCP is optional.

Selection gains optional library_material_revision; existing material_revision
retains its native shader meaning. Saved assemblies pin logical material bindings
separately and advertise the required material-library feature to incompatible
older readers. Integrity verification follows material/asset dependencies.

An assigned physical-only material remains a valid assignment without claiming to
provide a render graph. Supported appearance produces a USD preview material and
retains the logical revision ID. Supported native Blender graphs are restored on
new-file handoff. The library can store other native files without claiming that
all their contents or graph formats can be evaluated by the manager.

## Browser UI

A top-level workspace switch preserves geometry tabs, selections and draft state.
Geometry-only actions do not accidentally act on a hidden geometry tab while
browsing the library.

The library has resizable filter/search, thumbnail/list, and inspector regions.
Items group by stable identity and show their kind, revision count and latest
revision. The inspector selects an exact revision and contains Preview, Physical
properties, Appearance/assets, Lineage/revisions and Source/license details.
Images show actual archived image previews. Native graphs and unsupported documents
show useful type/provider information and explicit Open/Reveal actions, not fake
render evaluations. Large/unsupported image formats fail safely to metadata.

Actions: Import assets, New material, New revision, Derive/recombine, Verify,
Open source, Reveal/Open file, and Use for new assembly pieces. The last action
selects an exact material revision, switches to Geometry and sets the assignment
control; it does not rewrite existing draft pieces or assemblies. Physical values
are edited in a unit/source/status table, not an obligatory JSON editor.

## Poliigon boundary

V1 provides Browse Poliigon (system browser) and import of user-selected downloaded
files/folders, recording supplied source and license information. It performs no
credential handling, scraping, automatic downloading, asset redistribution or AI
analysis of third-party images. License remains unknown until supplied; no rights
are inferred from the free filter. Authenticated/provider APIs can be added later
if their supported interfaces and permitted use are established.

Sources checked 2026-11-07:
[Free textures](https://www.poliigon.com/textures/free),
[official Blender workflow](https://help.poliigon.com/en/articles/6342599-poliigon-blender-addon),
[asset-use terms](https://help.poliigon.com/en/articles/8749749-asset-use-licensing).

## Acceptance and audit

1. Empty/legacy projects open without rewriting history or hiding captured shaders.
2. Imported image/document originals can disappear while archived revisions remain verified.
3. PLA can be created with unspecified physics and independently chosen appearance.
4. Image edits/new revisions do not change older material references.
5. Property edits preserve old values, sources, unknown fields and appearance refs.
6. Recombination retains exact physical/appearance donors and dependencies.
7. Derivatives show explicit image/material input lineage and operation notes.
8. Stale edits, missing/corrupt dependencies and unsafe paths are rejected without overwrite.
9. Logical material assignments survive USD/assembly history separately from native graphs.
10. Native graph/preview fidelity limits remain explicit; physical data is not certified.
11. Browser supports search, keyboard selection, thumbnails, revision browsing and narrow panes.
12. Geometry state survives workspace switches; per-project libraries stay isolated.
13. Late previews cannot replace a newer selection or target a closed widget.
14. Both scoping agents audit the first built implementation; fixes and remaining
    limitations are recorded before handoff.
