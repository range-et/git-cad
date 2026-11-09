# Git CAD first release specification

Status: final review draft, revision 1, 2026-11-07. Not yet implemented. “v1” means the first
usable product release, including the UI; package versions may initially be 0.1.x.
MUST denotes a release requirement, SHOULD a preferred implementation, and MAY an
optional behavior. Interfaces below are specified, not implemented.

## 1. Mission and preservation promise

Git CAD is a fully local USD snapshot history and assembly tool implemented in Python.
Native applications continue working normally with their existing working files.
Every tracked native save, and every configured tool snapshot, produces a new
immutable timestamped USD snapshot. The user browses that history in a 3D UI,
selects objects or subassemblies from any snapshots, and deliberately composes a
new reusable USD result on `main`.

Material assets can be selected/versioned independently of geometry. Snapshot
packages MAY include native material-only assets when needed to preserve an
authoring graph beyond the portable USD representation. A per-project material
library separates appearance, engineering properties, and assignments.

The promise is: **Every successfully recorded USD snapshot remains addressable,
and every assembled result records exactly which snapshots and scene pieces it
came from.** Source snapshots are never overwritten by composition or omission.

Git CAD preserves exported USD scene states and their file lineage. It does not
promise historical restoration of complete native documents, feature trees,
procedural modifiers, rigs, sculpt strokes, or anything the exporter omitted.
Geometry export can tessellate native CAD surfaces. The UI MUST distinguish that
limitation from a successful, complete native backup.

Git, accounts, remote services, AI agents, and network connectivity are not runtime
requirements. An optional MCP interface exposes the same local operations. Local
history is not an off-device backup.

## 2. Scope and explicit exclusions

The first release MUST include:

- A local service and command-line entry point.
- A PySide6 history/assembly UI with an embedded PyVista/VTK inspection viewport.
- Save-triggered timestamped USD snapshot history from Rhino and Blender.
- Optional timed USD snapshots of current application state.
- Source timelines with labels, timestamps, parent links, and export status.
- Visual browsing, object/subtree selection, comparison, and result preview.
- Deliberate assembly of selections from arbitrary historical snapshots.
- Reusable USD output with an exact source-selection recipe and dependency lock.
- Direct STL export of selected historical USD geometry without reopening native
  apps; outputs are registered artifacts with units, mesh reports, and provenance.
- Versioned material library, independent geometry/look selection, and a tested
  Blender-native graph restore path for a declared supported material subset.
- Named sub-branches within source timelines and explicit cross-app import lineage.
- Extensible local application plugins and optional MCP access.
- Crash-safe publication, visible failures, integrity verification, and recovery.

The first release does NOT require:

- Per-vertex edit tracking, sculpt-operation reconstruction, feature-history diff,
  geometric merge, automatic cross-application reconciliation, or topology repair.
- Global identity matching across every historical object rename or re-export.
- A permanent version archive of complete native `.3dm` or `.blend` scene saves.
  Native material-only assets are an explicit supported exception.
- Automatic native-document refresh, native import, save-path changes, or replacing
  an app's object database with a live USD stage.
- Remote collaboration, distributed version control, a hosted database, or cloud.
- A complex branch/merge system for `main` beyond an explicitly selected current
  assembly and retained output provenance.

## 3. Native working files remain native

Each bound document has one Git CAD-managed working native path, for example
`source/model.3dm` and `source/scene.blend`. Git CAD MUST NOT rename that path to
include version numbers, redirect normal saves into history folders, or maintain
one permanent native copy per USD snapshot. The application retains its normal
save, undo, autosave, backup, and recovery behavior; existing `.blend1` or Rhino
backup settings MUST NOT be disabled to enforce a literal one-file count.

Immutable native material-only libraries may live under `materials/` so a Blender
graph can survive even when USD conversion is approximate. This does not create a
new full scene copy per save or change the user's working native path.

Connectors observe completed native saves and export the corresponding scene
state. Tool-initiated snapshots export USD from current memory without overwriting
or pretending to save the native document. Such a snapshot MUST be labelled
`tool_snapshot`, with `native_state_saved: false` when it includes unsaved edits.

Save As is allowed: the connector records the new active working path after user
confirmation of the binding. Choosing a new unrelated document requires an
explicit new source binding. Git CAD MUST NOT open, close, or import into native
applications merely because a new snapshot or main assembly exists.

## 4. Source timelines and main

`rhino` and `blender` are initially convenient source timeline names. Each source
is bound to a document identity and has an independent ordered history of USD
snapshots. Additional sources or multiple documents from one app have distinct
source IDs/names. These are local logical lanes, not Git branches.

Each source MAY have multiple named authoring branches, with one explicitly active
branch per bound workspace. A branch records snapshot parents and imported inputs;
it is not a requirement to duplicate the native working document. Branch creation
and continuation from a historical USD are explicit. Capturing a subsequent save
records the active source branch and its known cross-app inputs. Unknown manual
import lineage is annotated by the user, not inferred from object similarity.

A successful native save/export appends only to the originating source timeline.
It MUST NOT advance `main` or modify another app. Each snapshot references its
previous snapshot and the triggering event. Initial native base files are chosen
by the user; they are exported as source baselines rather than silently combined.

`main` is the user's currently accepted USD assembly, not a continually synced
union of the newest source states. It may intentionally lag every source head.
The user can select any historical combination, including an older Rhino snapshot
and a newer Blender snapshot. Selectors such as `rhino~10` resolve once to immutable
snapshot IDs; they never remain floating references inside a saved recipe.

Main does not need a separate Git-like commit/merge history in v1. Each saved
assembly is already a versioned USD output with its recipe. Updating the main
pointer does not delete previous assemblies or imply that either native app has
loaded it. Restoring a previous main means selecting a retained assembly again.

## 5. Project layout

```text
project/
├── cadgit.json
├── source/                              # Suggested, not mandatory locations
│   ├── model.3dm                        # Normal current Rhino document
│   └── scene.blend                      # Normal current Blender document
├── history/
│   ├── sources/<source-id>/
│   │   └── <UTC-timestamp>_<snapshot-id>/
│   │       ├── manifest.json
│   │       ├── scene.usda                # Snapshot entry point
│   │       ├── geometry.usdc             # Where appropriate for exporter
│   │       └── assets/...
│   └── events/<sequence>-<event-id>.json
├── assemblies/<assembly-id>/
│   ├── recipe.json
│   ├── manifest.json
│   ├── scene.usda                        # Immutable reusable assembly
│   └── assets/...                       # Any newly generated dependencies
├── main/
│   ├── current.json                     # Selected immutable assembly ID
│   └── scene.usda                       # Regenerable convenience entry point
├── artifacts/<kind>/<artifact-id>/
│   ├── manifest.json
│   └── outputs/...
├── materials/<material-id>/revisions/<revision-id>/
│   ├── manifest.json
│   ├── appearance/                      # USD/MaterialX/native graph/textures
│   └── engineering/                     # Typed physical data/provider payloads
├── mcp.example.json                     # Optional local launch example
└── .cadgit/
    ├── index.sqlite                     # Rebuildable search/status index
    ├── connections.local.json
    ├── staging/                         # Incomplete exact-state exports
    ├── drafts/                          # Recoverable assembly working drafts
    ├── locks/
    └── logs/
```

Working native files MAY remain elsewhere. Initialization MUST NOT move existing
files. UTC timestamps are display/ordering aids, not unique identities: snapshot
IDs MUST avoid collisions even when clocks move backwards or saves happen in the
same timestamp unit. Each save event gets its own snapshot record, including
unchanged saves. Byte-identical immutable payloads MAY be reused internally without
collapsing those records or changing apparent history.

`history/`, `materials/`, `assemblies/`, and registered `artifacts/` are durable project content.
Committed event records are authoritative for source ordering and main selections;
the index and current-entry files can be rebuilt. Drafts and incomplete staging
MUST not be deleted merely because they are uncommitted. Runtime locations and
credentials MUST NOT become portable source references. Relative dependencies
must be resolved relative to the file that authors them.

## 6. Save-to-USD capture contract

### 6.1 Trigger and exact-state boundary

Every completed tracked native Save/Save As creates a snapshot attempt. File
watching is a fallback, not proof that every save was observed; native completion
hooks are the preferred trigger. Export must correspond to that exact saved state,
not a later state that happens to exist when a background queue runs.

A connector MUST either export/serialize an exact USD scene state within a safe
native event boundary, preserve an immutable native-memory representation for
later export, or use private transient source staging. A temporary native Save Copy
is acceptable only when necessary for exact export/retry; it is not permanent
native history and MUST NOT replace the active working path. It may be removed
only after the USD snapshot commits or explicit abandonment is recorded. A failed
export's only exact retry input MUST NOT be deleted automatically.

Subsequent edits MUST NOT race extraction. App API work is dispatched safely on
its required thread, with export settings pinned. Capture latency must be measured
and visible; zero-overhead Save is not promised. A plugin that cannot secure the
exact save state MUST advertise `best_effort`, and the UI MUST identify the gap.

Exports MUST NOT be coalesced in a way that skips saved versions. Distinct source
events remain ordered even if export completion order differs. Intermediate save
versions missed while the plugin was disconnected cannot be reconstructed by
reading only the latest native file; record the monitoring gap honestly.

### 6.2 Snapshot publication

```text
SAVE OBSERVED → EXACT STATE SECURED → EXPORTING → VALIDATING → COMMITTED
                    ↘ CAPTURE FAILED        ↘ EXPORT FAILED / INCOMPLETE
```

A snapshot is a history entry only when its USD and required manifest commit
successfully. Failed attempts remain visible as events with export/capture errors
and retry availability. A native save may succeed while USD export fails; these
outcomes MUST never be conflated.

Each manifest MUST record:

- Schema version, snapshot/event/source IDs, parent snapshot, and timestamps.
- Trigger kind: user save, Save As, tool snapshot, manual export, or baseline.
- Source app/document identity and observed working path.
- Whether exported state was saved natively; exact/best-effort capture status.
- App, plugin, USD backend versions, export settings, and scope/filter selection.
- Entry layer and complete file inventory with sizes and SHA-256 hashes.
- Dependencies, unsupported/omitted content, units, axis, and validation results.
- Optional `derived_from_assembly`/`derived_from_snapshot` provenance when known.
- Source branch, imported-input roles, material revision IDs, and native/portable
  material fidelity status when those assets were captured.

Snapshots MUST be immutable after commitment. A retry yields a new outcome record
and a new snapshot when successful, linked to the original event; it MUST NOT
rewrite a previously committed snapshot. When the exact old state is unavailable,
a retry cannot silently export today's native state as yesterday's version.

### 6.3 Assets and export fidelity

Capture textures and other resolvable file dependencies into immutable history or
an immutable shared store. Missing/unsupported dependencies produce an incomplete
status. An incomplete snapshot MAY be viewed with warnings but cannot be silently
presented as a complete reusable assembly input.

The connector MUST state what native content the exporter omits or converts. Raw
native files are not permanently copied into the snapshot archive by default.
Application settings, add-ons, native procedures, and full editability are not
recoverable solely because USD export succeeded.

Timed tool snapshots are configurable and disabled until enabled by the user.
They export current state, label unsaved content accurately, and do not change the
native file's path, dirty flag, undo history, or native autosave policy. Busy-app
postponement is visible. Save/export callbacks MUST distinguish their origins to
avoid recursively creating snapshots from Git CAD's own export operations.

## 7. Domain model and lineage

| Record | Meaning |
| --- | --- |
| Source | One named native document/export stream. |
| Snapshot | Immutable exported USD state plus dependencies and provenance. |
| Event | Save observed, export outcome, label, main selection, or operation result. |
| Selection | Snapshot ID plus source prim/subtree or instance and extraction options. |
| Assembly draft | User's editable collection of selections and placement choices. |
| Assembly | Immutable USD result and exact source recipe. |
| Main pointer | Current accepted assembly; not native application state. |
| Artifact | Render, print file, package, or another derived output with pinned input. |
| Material revision | Immutable appearance and/or engineering assets with provider capabilities and provenance. |
| Material assignment | Pinned visual surface binding or engineering body/region assignment; these are separate roles. |
| Material slot | Software-independent binding identity preserved/remapped by adapters; distinct from display names and native slot indices. |

The required lineage graph is file/snapshot/selection/assembly/output lineage.
Cross-version vertex correspondence or universal CAD part identity is not required.
A selection uses `(snapshot_id, prim_path)` and instance information where needed;
this is unambiguous even if a later snapshot renames that object. Optional native
IDs can improve browsing but MUST NOT be required for ordinary snapshot splicing.

A recipe records exact source snapshots, source prim paths, destination paths,
parent/child selections, placement transforms, dependency policy, and any explicit
property overrides. Snapshot, recipe, assembly, and artifact IDs are separate.
Parent links are recorded; timestamps do not establish causality.

When a user imports a Git CAD result into a native app, known import provenance can
be attached to later snapshots. Unobserved manual imports need a user-supplied
lineage annotation. The tool MUST NOT infer proof of lineage from visual similarity
or a filename alone. Source editing histories can diverge freely without producing
an automatic merge conflict on every save.

### 7.1 Record and versioning contract

Format evolution MUST follow the [additive data compatibility contract](DATA_COMPATIBILITY.md).
UI versions are independent of data versions. New optional fields MUST preserve
historical defaults, unknown fields MUST survive validation and known-field edits,
and unsupported required semantics MUST be rejected explicitly. Every future
release MUST retain V1 readers and pass the frozen V1 compatibility tests.

All persistent record types MUST have an explicit schema version and opaque ID.
Use UUID-based record IDs and SHA-256 content hashes; neither filenames nor native
material names are identity. Snapshot parents, source-branch parents, imported
inputs, selected pieces, and derived artifacts are distinct typed relationships.
An exported source snapshot can link to multiple inputs without pretending they
are one linear native edit history. No automatic squash, rebase, or pruning is
part of v1.

The service writer serializes immutable event/record publication. Mutable source
heads and main selection are derived references backed by committed events.
Pydantic models MUST reject unknown required schema versions and invalid references;
JSON Schema exports document the file/plugin contracts. Schema upgrades create a
new explicitly versioned projection/migration record, preserving old payloads.
Unknown optional provider payloads remain preserved as opaque versioned assets.

The snapshot manifest's `files` inventory is relative to the snapshot root;
referenced assets outside that root require an explicit project-local asset ID
and hash. No portable reference may depend solely on an external absolute path.
Operational timestamps are UTC; the UI localizes them and can show exact UTC.

An illustrative snapshot record is:

```json
{
  "schema_version": 1,
  "id": "snapshot_...",
  "source_id": "source_...",
  "branch_id": "branch_...",
  "parent_snapshot_id": "snapshot_previous",
  "created_at": "2026-11-07T18:00:00.000000Z",
  "trigger": "user_save",
  "native_state_saved": true,
  "capture_quality": "exact",
  "entry_layer": "scene.usda",
  "imported_inputs": [{"kind": "assembly", "id": "assembly_input"}],
  "material_revisions": ["material_revision_..."],
  "files": [{"path": "scene.usda", "sha256": "<64-hex-digits>", "bytes": 1234}],
  "capabilities": {"geometry": "complete", "native_materials": "partial"},
  "warnings": ["One material requires an unavailable provider dependency."]
}
```

The IDs/hashes above are placeholders, not valid production records. Exporter
versions/settings, all dependencies, unsupported scopes, and validation outcomes
remain required manifest data as defined in section 6. Partial material status
does not silently convert into a native-fidelity success.

## 8. UI required in the first release

The UI is a release requirement, not a later enhancement. It MUST run locally
without an agent and provide:

- Source lanes and snapshot cards/timeline with timestamps, labels, status, and
  source app. Save history and USD animation time must be distinct controls.
- Opening supported snapshot geometry in the inspection viewport, with scene tree, object picking,
  orbit/pan/zoom, fit, isolation, visibility, and shading/wireframe controls.
- Side-by-side or toggle comparison of snapshots, with a shared camera option.
  A changed-object/property summary is useful; per-vertex tracking is not required.
- Selecting objects/subtrees from multiple snapshots and adding them to a draft.
- Browsing historical project materials, choosing a shader independently from
  geometry, and reporting native fidelity versus portable preview fidelity.
- A result hierarchy with source badges, source-revision jump links, placement
  controls, rename/remove/duplicate, and a clear preview of the combined result.
- Dependency and namespace issue explanations with explicit resolution choices.
- Save draft, save assembly, set current main, reopen prior assembly, and export.
- Export selected source/assembly parts as STL with dimensions/unit preview, mesh
  validation results, and a link to the registered print artifact.
- A durable operation/status panel showing export queues, failures, gaps, and
  unsupported features. Closing a review cannot silently accept or delete data.

Initial selection granularity is prim, subtree, subassembly, or supported instance.
Arbitrary vertex/face fragments are not required. Whole materials/cameras/lights
can be selected when their dependencies are supported. Per-property overrides MAY
be added for well-defined placement/visibility/appearance fields; a general shader
or CAD editor is not part of v1.

### 8.1 PyVista inspection viewport

The first-release viewer uses PyVista/VTK embedded in PySide6 through
`pyvistaqt.QtInteractor`. It is a geometry inspection/selection viewport, not a
universal USD renderer or a Cycles shader evaluator. The reference OpenUSD SDK
opens and composes the stage; an extraction worker creates display meshes and
metadata for the viewer. PyVista is not responsible for interpreting arbitrary
USD composition arcs. See [Qt embedding](https://qt.pyvista.org/usage.html),
[mesh picking](https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.enable_mesh_picking),
and [basic PBR display](https://docs.pyvista.org/examples/02-plot/pbr).

Required display subset: polygon meshes, source hierarchy, evaluated transforms,
supported instances, bounds, normals, wireframe/edges, neutral shading, and basic
supported material colors. Textures/basic PBR MAY be shown after explicit
qualification. Curves, lights/cameras as display icons, point instancers, volumes,
subdivision evaluation, full animation playback, and arbitrary shader execution
are not guaranteed in v1. Their presence MUST be listed; unsupported content may
be inspected as metadata/bounds where possible and remains preserved in USD.

Every actor pick MUST map back to `(snapshot_id, prim_path, instance_occurrence)`.
Split display meshes/material groups and any display triangulation MUST retain
that map. A simplified display mesh is not a new source geometry revision.
Assembly/export always uses original USD selections, never reconstructed viewport
triangles. Source hierarchy and selection remain available independently of which
objects currently have a rendered actor.

The worker MUST evaluate transform stacks, visibility/purpose, unit/axis
conversion, and instance placement consistently for the supported display subset.
It MUST validate indices/finite values before sending geometry to VTK. USD time
samples are distinct from version history; v1 MUST support selecting an inspection
time code, with an explicit indication if a feature cannot be evaluated. Full
animation editing/playback is not required. Dependency or topology errors cannot
be hidden by a plausible-looking fallback mesh.

The Qt application owns one GUI event loop. Widget, actor, and VTK render-window
mutations occur on the GUI thread. Workers return validated immutable result data
through queued signals; large USD parsing/mesh extraction must not freeze the UI.
Viewer crashes/GPU failures must not damage durable history. An external usdview
launcher MAY be supplied as a diagnostic, not as a required runtime UI or an
unimplemented substitute for integrated selection/assembly preview.

### 8.2 Monad System visual language

The UI MUST use [Monad System](https://github.com/range-et/monad_system). The
reviewed revision is `358d0559da407897957a5817b24f9ebd8774b791`. Its `colors.json`
is the palette source; its generated CSS supplies reference spacing/typography.
The inspected repo does not include a Qt adapter. Git CAD must generate a small
Qt palette/QSS adapter from pinned tokens rather than treating browser CSS as a
Qt stylesheet. Preserve the upstream MIT notice with reused assets.

Required theme mapping uses semantic names: background/layer surfaces, primary
and secondary text, border/focus, interactive, information, success, warning, and
error. Dark is the initial default; light and system-following modes are supported.
Theme switching changes chrome/viewport background, not saved material colors.
Source-lane categorical colors are distinct from error/status colors.

Use the reference 8-unit spacing grid, squared/simple controls, sans-serif UI text,
and monospace IDs/technical values. Font families follow the reference theme with
installed-platform fallbacks; a missing preferred font cannot break layout.
Use clear keyboard focus, labelled icons, and text/pattern indicators in addition
to color. Subtle hover/focus transitions MAY follow the theme's short motion
values; reduced-motion disables nonessential animation. No flashing timelines,
heavy decorative motion, or automatic camera animation on every save.

The token adapter MUST have tests proving selected upstream tokens propagate to
Qt and PyVista surfaces. Theme data is packaged locally; no theme-server, CDN,
remote font fetch, or upstream build tool is required for normal operation.
The app Python version need not match Monad's palette-build environment.

### 8.3 First-release workspace layout and interactions

```text
+---------------------------------------------------------------+
| Project / source connection status          Snapshot / Export  |
+-------------+-------------------------------+-----------------+
| Sources and | Snapshot / assembly viewport  | Inspector       |
| branches    | [source A] [source B] [result] | Provenance      |
| Scene tree  |                               | Material slots  |
| Materials   |                               | Dependencies    |
+-------------+-------------------------------+-----------------+
| Timeline: application lanes, branches, snapshots, lineage links |
+---------------------------------------------------------------+
| Draft tray: selected pieces / transforms / material bindings    |
| Save assembly       Set main       Export / Open in application |
+---------------------------------------------------------------+
```

Panels can resize/collapse; timeline and draft state survive reopening. A source
snapshot click changes inspection, never main or native content. Adding a picked
prim or tree selection adds a recipe item; removing it removes only that item.
Drag/drop is a convenience and MUST have keyboard/context-menu equivalents.
Selecting a material opens its provider/revision/fidelity/physical-data details.
A follow-latest working binding is visually distinct from a pinned saved binding.

The UI distinguishes browsing a historical snapshot, editing a draft, and viewing
an accepted assembly. Save assembly and Set main are distinct explicit actions.
The lineage inspector shows source-parent and imported-input links separately.
Errors offer retry/inspect rather than silently replacing the native working state.
No panel needs to present low-level IPC/backend details outside diagnostics.

## 9. Splicing and assembly semantics

The user can take, for example, an engine block from Rhino snapshot R12, its cover
from Rhino R8, and a sculpted housing from Blender B5. These become selections
inside one assembly draft. No shared native feature history is required.

For each selection Git CAD MUST:

1. Resolve the exact immutable snapshot and verify that the selected path exists.
2. Include the selected prim/subtree plus required dependencies and inherited
   context. Preserve source-world placement unless the user explicitly changes it.
3. Assign a distinct destination namespace so selections from different snapshots
   can coexist. Preserve source metadata in the recipe rather than guessing which
   objects are logically identical.
4. Resolve material targets, external asset references, transforms, instance
   prototypes, and other supported relationships needed for the selection.
5. Preview and validate the composed result before saving or setting main.

USD references are useful for reusable subassemblies, but blindly referencing an
arbitrary mesh prim is insufficient: required parent transforms or material
bindings may live outside that subtree. The extraction step MUST capture needed
context, copy/remap dependencies, or explicitly block unsupported selections.
Selecting a child and its parent twice MUST be detected so unintended duplicate
content is visible. Choosing two versions of a similarly named part is allowed;
the user may deliberately want both.

An assembly recipe MUST store an immutable array of selections and separate
bindings rather than a serialized UI selection state. For example:

```json
{
  "schema_version": 1,
  "id": "assembly_...",
  "label": "Engine presentation",
  "selections": [
    {
      "id": "selection_block",
      "snapshot_id": "rhino_snapshot_12",
      "prim_path": "/Engine/Block",
      "destination": "/World/Engine/Block",
      "placement_policy": "preserve_source_world"
    },
    {
      "id": "selection_cover",
      "snapshot_id": "blender_snapshot_5",
      "prim_path": "/Housing",
      "destination": "/World/Engine/Cover",
      "placement_policy": "preserve_source_world"
    }
  ],
  "bindings": [
    {
      "target_selection": "selection_block",
      "slot_id": "slot_surface",
      "appearance_revision": "historical_blender_graph_4",
      "engineering_revision": "engineering_card_2"
    }
  ],
  "main_selection_requested": false
}
```

Instance selections add occurrence/prototype identity; user placement changes add
an explicit transform with unit/basis metadata. A validated saved recipe also pins
the complete dependency lock and any material resolver outcomes. Main selection
is recorded separately after save; the example flag is intent, not an atomic
mutation of the main pointer.

### 9.1 Issues are assembly choices, not geometric merge conflicts

Independent native saves are normal history, not errors requiring reconciliation.
Issues arise when building a result: duplicate destination names, overlapping
selections, unresolved relationships, incompatible coordinate/time contexts, or
missing dependencies. The UI MUST show the actual issue and available actions:
rename/namespace, keep both, omit one selection, include dependency/context, or
supply an explicit override. Omitting a selection never erases its source history.

Two different shape versions can coexist without proving which is correct. Physical
intersections MAY be displayed, but manufacturability or automatic geometric
reconciliation is not promised. The user is assembling scene assets, not asking
Git CAD to merge vertex edits or synthesize a combined native CAD feature tree.

## 10. Coordinates, composition, and validation

The shared interchange contract is units, coordinate conventions, and optional
portable materials. Geometry is captured and selected, not live-synchronized.
Normalization applies to exported/assembled USD; Git CAD MUST NOT silently change
native document units, origin, or application settings. A user's explicit assembly
placement is separate from automatic unit/basis conversion.

Preserve exporter-native USD and record declared units/axis. Assembly roots SHOULD
use a canonical Z-up, right-handed, meter coordinate system with explicit per-input
basis/unit conversion wrappers. Changing metadata alone is not conversion. Normals,
winding, transforms, negative scale, and instance placement need fixture tests.

Source layer metadata and dependency context must remain inspectable. Heavy mesh
data SHOULD use USDC and readable composition SHOULD use USDA. Snapshot layers
and assembly references must be pinned, not floating `latest` paths. Session-layer
choices needed for persistence must be authored into the saved result.

Assembly validation MUST check stage opening, selected prim existence, reference
closure, namespace uniqueness, material/relationship targets, unit/axis conversion,
and finite geometry/transforms for the supported subset. Unsupported schemas or
export omissions must be visible. Source snapshot files are never mutated to fix
an assembly. Default output preserves composition; flatten/package creates a
separately labelled portable export with lineage back to the assembly.

### 10.1 Versioned appearance and engineering materials

Geometry/instances can carry stable material slots referring to app-independent
catalog assets. Rhino can store a display proxy and assignment metadata while
Blender resolves the same appearance asset to its compatible native graph. Future
OpenFOAM/FreeFEM/Ansys adapters resolve independent engineering representations.
Plugins MUST preserve/remap slot bindings through native metadata plus the USD
assignment manifest; native exporters are not presumed to do this automatically.

The project material library MUST separate appearance from engineering properties
and their assignments. Appearance can include native Blender graphs, supported
MaterialX, USD Preview Surface, and derived texture bakes. Engineering data can
include typed density/constitutive properties and opaque provider material cards.
Visual PBR parameters MUST NOT be treated as engineering density or strength.

Material revisions are immutable; recipes pin exact graph/data revisions and
bindings. Selecting new Rhino geometry with an old Blender shader is a required
first-release workflow for the tested native graph subset. USD carries the scene,
portable look, and native asset references; restoring the exact native graph needs
the Git CAD Blender adapter or an explicit native material append step. A bare USD
import cannot be advertised as preserving arbitrary Cycles graphs.

Working assignments MAY follow the latest compatible provider representation.
Every recorded snapshot/assembly/task MUST freeze the exact resolved asset and
representation revisions and hashes. Updating a material later never retroactively
updates recorded history. Surface/body regions lost through geometry edits are
marked unresolved rather than silently reassigned by slot name or face index.

The library MUST retain required node groups, textures, mapping dependencies, and
provider/version provenance. Missing named attributes, UVs, object coordinate
sources, or runtime requirements are surfaced before claiming a material works on
new geometry. Native graph preservation is distinct from identical rendered
appearance after geometry or renderer changes. The UI MUST distinguish portable
viewport fallback from intended native render fidelity.

USD snapshot completion and native-material preservation are separate statuses.
If the geometry/preview export succeeds but native graph capture fails, preserve
the USD snapshot and report native fidelity unavailable. Do not associate a later
graph capture with the old scene unless exact state provenance is established.
An assembly requesting native fidelity must block or obtain explicit approval for
a fallback when that required material asset is missing.

Portable representations are optional fallbacks, not a restriction that every
material must fit one PBR subset. Unsupported graph translation MUST NOT silently
replace a retained native graph with a simplified material. Automatic baking and
universal renderer equivalence remain outside v1. Physical material values require
units, provenance, validity conditions, and explicit body/region assignments; full
FEA/FEM execution and Substance/Ansys providers remain future integrations.

See [Versioned materials and cross-application lineage](MATERIALS_AND_LINEAGE.md)
for the data model, provider boundaries, local Blender evidence, and acceptance gate.

## 11. Main, reusable outputs, and native continuation

`main` is a current selection, not an autonomous process. The user explicitly saves
an immutable assembly and then may set it as current main. Previous assemblies
remain reopenable without a mandatory Git-style main branch graph. Main can be an
empty valid USD stage before the first assembly exists.

Each main output includes a recipe and dependency lock. Moving main changes only
the current pointer/convenience layer. Artifact exports, such as STL/3MF, renders,
or packaged USD assets, pin the exact assembly ID and settings that produced them.
Nothing silently repoints already recorded artifacts to the new main.

### 11.1 Direct geometry exports for printing and reuse

Git CAD MUST export printable mesh files directly from any committed USD snapshot
or saved assembly, including older versions and individual selected parts. The
operation MUST work while Rhino and Blender are closed. Main promotion is not
required to export a historical source part. STL is required in v1; 3MF, OBJ, PLY,
and other formats are extensible exporters with explicitly declared capabilities.
Support for a format MUST NOT be inferred solely from a filename extension.

The source is the original committed USD scene evaluated by the reference SDK,
not a decimated PyVista actor or whatever happens to be open in a native app. Pin
snapshot/assembly ID, selected prims and instance occurrences, visibility/purpose
policy, time code, placement/origin policy, geometry evaluation settings, output
units, exporter version, and output hashes. UI Export Selected and CLI/MCP use
the same operation. Unsaved draft exports are labelled preview artifacts and pin
an immutable copy of the draft recipe and its inputs before export.

The export worker MUST load required payloads, apply inherited/instance transforms,
convert coordinates/units exactly once, extract supported mesh data, triangulate
as needed, and handle negative-scale winding/normals consistently. Unsupported
subdivision, skinning, point-instance, or deformation evaluation MUST block the
affected selection or require an explicitly labelled base-mesh fallback. It MUST
not silently export a control cage while claiming the evaluated/rendered surface.
Export reports MUST state whether native-export tessellation or additional
evaluation produced the mesh; a later mesh export cannot recover CAD precision
that the original USD tessellation discarded.

STL stores triangles without a standard unit declaration or portable material
definitions. The print preset MUST explicitly convert numeric coordinates to
millimeters by default, show resulting bounding dimensions, and record the unit in
the artifact manifest. Users can choose another numeric unit; changing an export
unit MUST preserve intended physical size. Source placement is preserved unless
an explicit local-origin/centering option is selected. These choices do not mutate
the source scene. See [STL unit behavior](https://help.autodesk.com/view/fusion360/ENU/?caas=caas%2Fsfdcarticles%2Fsfdcarticles%2FSTL-files-exported-from-Fusion-360-are-scaled-down-in-3d-printing-software.html).

Multiple selections default to one file per selected part/instance. An explicit
combined-file option may concatenate transformed meshes; it is not a Boolean union
or an automatic repair of intersecting shells. Name collisions are resolved with
stable selection IDs, never silent overwrites. STL export does not carry Cycles
shader graphs or engineering material definitions; those stay linked in provenance.

The export report MUST check finite coordinates, valid indices, nonempty triangles,
degenerate faces, boundary/nonmanifold edges, winding where testable, connected
components, and bounding size. Numerical/structural errors block output. Open or
nonmanifold geometry requires explicit acknowledgement to export as a mesh with
issues; the artifact must retain that status. Self-intersections, wall thickness,
and other unimplemented checks MUST be reported as not checked, not passed.
Passing these checks is not a certification of printability. Repairs/decimation
must be explicit derived operations with settings and lineage, never hidden edits.

A rendered appearance does not necessarily represent printable geometry: normal
maps, bump, shader displacement, and other renderer-only effects may not be stored
as evaluated mesh in the USD. The UI MUST explain this when applicable. A user who
wants those effects printed needs an appropriately evaluated/baked geometry
snapshot, not an assumption that a material is geometric surface detail.

Generated print outputs live under `artifacts/prints/<artifact-id>/` with their
manifest, validation report, and output file(s). A user-selected destination MAY
receive an additional copy, but the registered artifact remains immutable and
reproducible from pinned inputs/settings. Export failures preserve source history
and do not register a partial STL as a successful artifact. Exporting a source
part records source lineage directly; it MUST NOT invent an intermediate main.

### 11.2 Native continuation

The user can manually import an assembly USD into Rhino, Blender, or another native
app and keep working. No automatic object-preserving apply engine is required.
An optional plugin import action must be explicit and must not overwrite the
working native file or discard unsaved edits without protection. Native backup
copies needed for such an optional operation are recovery data, not an implied
per-save native archive. Imported meshes do not automatically regain native BRep
or procedural editability. The next save/export is simply another source snapshot,
with imported lineage recorded when available.

Native editability across application round trips and optional native version
archives are deferred in [Future features and open questions](FUTURE_FEATURES_AND_OPEN_QUESTIONS.md); neither is a V1 release requirement.

For an assembly requiring native Blender material fidelity, an explicit Git CAD
import can append archived material datablocks after importing USD geometry and
bind them from the recipe. This small native-asset restoration path is required
for the supported material profile; an automatic geometry refresh engine is not.

## 12. Python implementation and extensible plugins

### 12.1 Selected first-release stack

| Responsibility | Selected approach |
| --- | --- |
| Application/domain core | Typed Python modules; no Rust requirement. |
| USD reading/composition/authoring | Reference Pixar OpenUSD SDK through `pxr` Python bindings. |
| Geometry extraction/display buffers | OpenUSD plus NumPy; original USD remains authoritative. |
| Desktop shell | PySide6 Qt Widgets. |
| Embedded viewport | PyVista/VTK with pyvistaqt and the PySide6 Qt binding. |
| Theme | Pinned Monad System tokens mapped to Qt/QSS and viewport surfaces. |
| CLI | Typer calling the shared domain services. |
| Models and validation | Pydantic with published versioned JSON Schemas. |
| Query/cache index | Python `sqlite3`; immutable files/events are authoritative. |
| Optional agent interface | Official Python MCP SDK, stdio. |
| Development environment | `pyproject.toml`, uv-managed environment and committed lockfile. |
| Tests | pytest, real native-app probes, and Qt/PyVista integration tests. |

The packaging baseline is a separately managed Python 3.12 environment, subject
to a clean macOS dependency qualification before version locking. Native Blender
and Rhino adapters run in their own supported interpreters and communicate with
the core; the core environment MUST NOT be installed into their application Python
paths. Select and lock a compatible OpenUSD/NumPy/VTK/PyVista/PySide6 combination;
no untested latest-version claims or implicit dependency upgrades are permitted.
The SDK's C++ processing and VTK rendering remain native dependencies; Python is
the orchestration layer, not a rewritten USD parser/renderer.

Hydra, native Rust USD crates, and a Rust store/service are not required for v1.
They remain optional future alternatives if measurements/capabilities justify
adoption. A future implementation language change must preserve record formats
and public operations. Distribution/SDK ABI compatibility is a release gate.

### 12.2 Process and package boundaries

```text
Rhino/Blender native hooks ───→ Local project service
                                      ↑
                         CLI / Qt UI / optional MCP
                                      |
                         USD/extraction workers
                                      |
                  Immutable project files + SQLite index
```

Use one local service writer per project. CLI/UI/MCP share domain operations;
none maintains a competing interpretation of main, snapshots, or materials.
USD export runs through the relevant app adapter when native access is required.
Core USD composition/extraction MAY use isolated subprocess workers. A worker owns
its stage; mutable SDK/Qt/VTK objects MUST NOT be shared across process boundaries.
Opaque native asset loading remains an explicit adapter action.

Suggested package boundaries are `models`, `store`, `history`, `usd`, `assembly`,
`materials`, `plugins`, `service`, `cli`, `ui`, and `mcp`. These are Python package
responsibilities, not independently deployed microservices. Core imports must not
require Qt, VTK, or an MCP client when running headless history/verification tasks.
GPU/viewer failures cannot corrupt the service writer or previous records.

### 12.3 Minimal application plugins

Plugins perform document discovery, native save notifications, exact-state USD
export, metadata/slot mapping, and supported material capture/import. Optional
blank-document/import helpers are explicit user actions. History storage,
assembly choices, retention, and material-provider policy stay in the core.

Use a versioned local executable protocol with a plugin manifest, app/version
range, capabilities, and entry point. Plugins MAY use native Python/.NET runtimes.
Required operations are handshake, enumerate documents, inspect capabilities,
observe saves where supported, and export exact state. Material-aware reference
plugins also implement capture material and restore supported assignments. An
export-only integration can supply manually ingested snapshots without save hooks.

Capabilities include exact-save/current-memory export, USD formats/schemas,
dependency inventory, material capture/restore, slot preservation, and optional
import. Stable per-part identity, native historical restore, and mesh-level diff
are not prerequisites. An opaque provider asset can be retained without claiming
it is executable or convertible in another app.

Messages MUST carry protocol/version, request/operation IDs, document identity,
origin, and structured result/error. Large arrays/files are passed through
validated local staging references rather than unbounded JSON. Use framed/bounded
messages, deadlines, idempotency keys for mutations, and explicit completion.
No fixed Rhino/Blender port is assumed. Community MCP transports MAY be reused
behind adapters, but neither an MCP client nor an agent is required at runtime.
Unknown plugins require explicit registration; project files cannot execute code
merely by being opened.

### 12.4 Runtime and distribution qualification

The first developer distribution MAY be a locked uv environment with an app/CLI
launcher. The first user release must document or bundle its supported runtime;
users must not compile OpenUSD to browse a project. Package SDK/Qt/VTK resources
and record third-party licenses. Test startup, viewport/picking, worker spawning,
path resolution, and optional Blender material restore from a clean machine.
Do not promise a single executable or cross-platform support before those builds
are tested. Normal local operation must not download dependencies or require
network activation.

## 13. CLI and optional MCP

Canonical executable: `git-cad`. Required CLI operations are:

| Command | Behavior |
| --- | --- |
| `init [path] --app rhino --app blender` | Create local metadata, choose base files, create empty main, and configure source definitions. |
| `begin [path]` | Start/resume source monitoring and export queues; no auto-convergence. |
| `stop` | Stop cleanly without closing apps or deleting staging/history. |
| `status [--json]` | Show sources, current native paths, export state, gaps, and current main. |
| `snapshot --source NAME` | Export current app state as a labelled USD snapshot without forcing native save. |
| `autosnapshot on\|off [--interval SECONDS]` | Configure timed USD snapshots. |
| `ingest PATH --source NAME` | Record an existing USD package with dependencies and declared provenance. |
| `log [SOURCE]` | Browse source snapshot history. |
| `branch create NAME --source SOURCE --from SNAPSHOT` | Create an independent source history head without silently changing native files. |
| `branch use NAME --source SOURCE` | Select the next-save branch and record any explicitly imported starting state. |
| `material list\|show\|capture` | Inspect or version project material assets using provider capabilities. |
| `material bind --slot ID --appearance REF` | Assign a visual asset or explicit follow policy to a stable slot. |
| `material bind --slot ID --engineering REF` | Assign a separately versioned engineering definition to its supported body/region scope. |
| `view SNAPSHOT` | Open a selected USD snapshot in the local UI. |
| `ui` | Open the history/assembly interface. |
| `compose --input SNAPSHOT:PRIM ...` | Create a draft from exact selections; UI can refine the draft. |
| `assembly save DRAFT --name NAME` | Validate and preserve an immutable assembly. |
| `main set ASSEMBLY` | Explicitly select current main. |
| `export REF --format FORMAT --select PRIM --output PATH` | Export a snapshot/assembly selection as USD or a supported mesh format, including STL; pin provenance and validate. |
| `import ASSEMBLY --app APP --materials native\|portable` | Explicit supported native import/material restore through an adapter; protect current work and report fidelity. |
| `artifact register PATH --kind KIND --from REF` | Record an output and pinned snapshot/assembly lineage. |
| `show ID` / `lineage ID` | Inspect provenance and dependencies. |
| `verify [ID]` / `doctor` | Check integrity and diagnose plugins, queues, and dependencies. |
| `plugin list\|inspect\|register` | Manage explicitly registered local connectors. |
| `mcp --project PATH` | Expose the same operations to an optional agent client over stdio. |

`init` creates a blank OpenUSD scene, not an MCP geometry format. The optional
`mcp.example.json` is a separate client launch template, not a global agent-config
edit. Existing native base files are selected, not renamed or auto-imported. Blank
native files can be created only by an explicit supported plugin action. `begin`
may offer init on an uninitialized folder but must not overwrite existing metadata.

Mutations support operation IDs/idempotency keys; JSON output is versioned and
separated from diagnostics. Timeout/closing a client does not imply cancellation.
CLI/UI/MCP MUST share one domain API. Agents cannot bypass snapshot immutability,
source selection, or dependency checks. MCP/skill integration is optional; the UI
is not optional in the first usable release.

Example direct print export (specified interface, not yet implemented):

```sh
git-cad export rhino~3 --select /Engine/Block --format stl --units mm --output exports/block.stl
git-cad export main --select /World/Engine/Cover --format stl --units mm --output exports/cover.stl
```

The selector must resolve to an immutable snapshot/assembly before work starts.
Format-specific options include binary/ASCII STL, numeric units, instance scope,
per-part/combined output, origin policy, and explicit acceptance of mesh issues.
The optional MCP facade MUST expose the same export operation and report.

## 14. Configuration

Illustrative portable configuration:

```json
{
  "schema_version": 1,
  "implementation": {"language": "python", "usd_backend": "reference_pxr"},
  "project": {"id": "<uuid>", "name": "engine"},
  "sources": [
    {"id": "<uuid>", "name": "rhino", "app": "rhino", "working_file": "source/model.3dm"},
    {"id": "<uuid>", "name": "blender", "app": "blender", "working_file": "source/scene.blend"}
  ],
  "snapshots": {
    "on_native_save": true,
    "tool_interval_seconds": null,
    "format": "usd",
    "retention": "all",
    "archive_native_files": false,
    "require_exact_state": true
  },
  "assembly": {
    "main_advancement": "explicit_selection",
    "selection_granularity": "prim_subtree_or_instance",
    "up_axis": "Z",
    "meters_per_unit": 1.0,
    "material_policy": "native_asset_with_portable_fallback",
    "automatic_native_refresh": false
  },
  "ui": {"required": true, "toolkit": "pyside6", "viewport": "pyvistaqt", "theme": "monad", "theme_mode": "dark"},
  "materials": {"path": "materials", "pin_revisions": true, "engineering_execution": false},
  "paths": {"history": "history", "assemblies": "assemblies", "runtime": ".cadgit"}
}
```

Machine-local endpoints, process IDs, and credentials remain outside this config.
Config changes are recorded with snapshots/assemblies where relevant. The earlier
`test/bridge.json` is not this schema. Do not guess a migration from its old
one-way ownership settings.

## 15. Durability, failure handling, and performance

Use one project writer. Stage exports on the same filesystem, flush files as
supported, verify hashes/manifest, rename into an immutable location, and publish
an ordered commit event. Partially written USD must not appear as complete history.
Index updates occur after durable publication and can be rebuilt. Main selection
uses an expected-current check to avoid accepting a stale review accidentally.

On restart, inspect staging and operation records, resume only exact inputs that
still exist, and expose irrecoverable gaps rather than inventing versions. Failure
or cancellation must not erase source snapshots or accepted outputs. History is
never automatically pruned in v1. Disk-full stops recording safely with a visible
error; a normal native save may still succeed independently.

No cloud database/message broker is required. USD workers/plugins should be
isolated so malformed input or a crash cannot corrupt the history writer. Local
IPC requires bounded messages, typed errors, deadlines, and user-scoped access.
Project paths are data, not shell fragments. Archive extraction and dependency
resolution must reject path traversal and unauthorized resource access.

Index the timeline without reopening every USD file. Load selected snapshots and
payloads on demand. Run expensive export, extraction, and validation off the UI
thread where native APIs permit. Progressive preview and cache reuse must not
change retained snapshot fidelity. Benchmarks must report capture overhead, large
snapshot opening, selection/assembly latency, memory, and storage growth. No
unmeasured zero-latency or perfect-fidelity claim is permitted.

Git integration is optional. Generated `.gitignore`/`.gitattributes` sections must
preserve existing rules; native binaries are never text-merged. Ignoring history
in Git means a push does not back it up. Complete project backup includes durable
snapshots, assembly recipes, dependencies, event records, and artifacts.

## 16. First-release acceptance criteria

1. **Normal native behavior:** repeated saves keep the same working `.3dm`/`.blend`
   paths and normal native editing/undo/backup behavior. No permanent native
   version archive is created by default.
2. **Every save exports:** rapid saves with distinct states yield corresponding
   timestamped USD snapshots, not repeated exports of the eventual head. Failed
   captures/exports are visibly distinct from successful native saves.
3. **No event collapse:** unchanged saves retain distinct records; same-time saves
   cannot collide. Export ordering cannot lose source-parent ordering.
4. **Timed snapshots:** enabled tool snapshots include current unsaved state and
   label it accurately, without overwriting or falsely saving the native file.
5. **History UI:** first release includes source timelines, labels/status, scene
   inspection, picking/isolation, and an embedded PyVista/VTK viewport on macOS.
6. **Arbitrary historical splicing:** choose pieces from two different Rhino
   snapshots and a Blender snapshot, preview them together, and save a USD assembly
   while all original snapshots remain byte-for-byte intact.
7. **Context/dependencies:** a selected nested mesh retains its required placement
   and material context; an instance retains required prototype data. Unsupported
   selections block or warn explicitly instead of silently losing dependencies.
8. **Namespace choices:** two versions of a part can deliberately coexist. Naming
   collisions and duplicate parent/child selection are explained and resolvable.
9. **Main is deliberate:** save events, opening history, changing drafts, and
   cancelling review never move main. Selecting a saved assembly moves only main.
10. **Lineage:** from an exported artifact, trace to assembly recipe, every selected
    source snapshot/prim, and the original app/save event, including omissions and
    conversion settings.
11. **Reopen previous results:** after new source saves and new main selections,
    earlier snapshots and assemblies still open with pinned dependencies. No
    mandatory main commit-graph implementation is needed to achieve this.
12. **Native continuation:** manually import an assembly into Rhino or Blender,
    continue modeling, and create a new save-triggered USD snapshot. USD import is
    not represented as a lossless native feature-history restore.
13. **Failure recovery:** interrupted exports, missing dependencies, disk full,
    malformed USD, and worker/viewer crashes leave earlier history intact and
    show actionable status. A failed export never substitutes a later native state.
14. **Rebuild:** rebuild timeline/main query state from durable records after
    deleting only rebuildable runtime indexes while stopped.
15. **Plugin extension:** ingest/export through a third test plugin without
    core changes. Missing live-save or schema capabilities are reported accurately.
16. **Agent independence:** all required operations work through CLI/UI with no
    AI/MCP client. Optional MCP uses identical validation and mutation rules.
17. **Fidelity reporting:** tests distinguish successful USD preservation from
    omitted native features, and snapshot timestamps from animation time samples.
18. **Viewer integration:** picks return exact snapshot/prim identity, result
    preview placement matches the saved assembly, and preview limitations are
    explicit. Export uses original USD, not triangulated/decimated display meshes.
19. **Historical shader reuse:** preserve an old Blender procedural graph with
    node groups/textures, change its live version, select new Rhino geometry plus
    the old graph, and restore/render through the adapter. Verify graph/dependency
    preservation and lineage; preview fallback alone does not satisfy this test.
20. **Independent material facets:** changing appearance does not alter the pinned
    engineering data, and changing a physical material revision does not rewrite
    the shader or any historical assembly. Unknown physics values stay unknown.
21. **Source sub-branches:** record an explicit Rhino-to-Blender-to-Rhino chain and
    a second Blender branch. Imported-input links and source-parent links remain
    distinct; native paths remain user-managed and no vertex merge is required.
22. **Provider capability limits:** preserve a sample opaque engineering card or
    procedural-provider asset with provenance without falsely claiming the tool
    can evaluate it, translate every property, or render it in an arbitrary app.
23. **Slot round trip:** create a stable assignment, import into Rhino as a native
    proxy/metadata binding, save/export, and resolve it to the pinned native Blender
    graph through the adapter. Native names/indices may change without silently
    changing catalog identity. Missing region mappings are reported unresolved.
24. **Latest resolution:** a working slot can follow a new provider graph; recorded
    snapshots/assemblies still load their original pinned revisions. An explicit
    update creates a derived result and records both its source and new material.
25. **Monad theme:** pinned source tokens propagate to dark/light Qt controls and
    viewport chrome; theme changes leave material values unchanged. Keyboard focus,
    status labels, resizing, fallback fonts, and reduced motion remain usable.
26. **Display/source separation:** a source n-gon/subtree is triangulated or split
    for display; picking still returns its correct source selection and assembly
    export retains original USD. Unsupported shader/volume features remain stored
    and visibly marked rather than silently discarded.
27. **Packaged Python runtime:** a clean supported macOS environment can launch
    CLI/UI, compose USD, pick PyVista actors, and reconnect to both app adapters
    using locked dependencies without injecting packages into either native app.
28. **Headless parity:** CLI/MCP history, recipe, and verification operations work
    without a Qt window or GPU context; workers can fail without damaging history.

29. **Direct print export:** with Rhino/Blender closed, export a selected historical
    USD part and an assembly part to STL from UI/CLI. Reopen the outputs, verify
    triangle geometry/bounds, and trace each artifact to exact selected inputs.
30. **Print scale:** equivalent meter/millimeter source fixtures produce the same
    intended STL dimensions in the configured numeric units. Instance transforms,
    negative scale, and origin options are applied once and recorded.
31. **Mesh/fidelity reporting:** invalid indices/nonfinite geometry block export;
    open/nonmanifold meshes require explicit acknowledgement. Unsupported surface
    evaluation and renderer-only bump/displacement do not silently become claimed
    printable detail. A combined STL is not advertised as a Boolean union.

## 17. Implementation sequence

1. Prove save-triggered exact USD export in both reference apps, including rapid
   saves and failure/retry behavior, without changing native working paths.
2. Build the Python record store, source timeline, manifests, dependency inventories,
   and minimal CLI; retain the existing 20 mm exchange fixture as an early test.
3. Prove PyVista/Qt integration and source-aware picking. This is a first
   release gate, not a future UI task.
4. Implement selection recipes, context/dependency extraction, assembly preview,
   immutable output, and explicit main selection.
5. Complete the history/assembly UI, recovery tests, plugin SDK, and optional MCP.
6. Prove historical native shader reuse, independent material assignments, and
   source sub-branch/import lineage in the engine workflow.
7. Ship direct STL export, dimension/mesh reports, and artifact lineage from both
   historical source snapshots and saved assemblies without native-app access.

The tested release matrix starts with macOS, Rhino 8, and Blender 5.2 LTS. Exact
app/plugin/SDK builds must be recorded. Existing smoke tests observed Rhino
8.36.26296.17002 and Blender 5.2.3 LTS; these observations do not establish the save
hooks, history, or UI implementation. OpenUSD/PyVista/Qt packaging choices
require executable qualification before release.

## 18. Research and relationship to earlier designs

This revision selects Python, PySide6/PyVista, and Monad System, and supersedes
earlier Rust-first/Hydra-required assumptions as well as permanent native-save history,
automatic native application, per-part/vertex merge tracking, and mandatory Git-like
main commit graphs. The durable unit is a USD snapshot; the core user action is
selecting pieces into a reusable USD assembly with lineage. Earlier repository
fixtures remain unchanged and do not imply that the new product is implemented.

- [Historical USD/Rust assessment](USD_ARCHITECTURE.md): earlier candidate
  research. Python with reference OpenUSD is now selected; Rust recommendations
  and native-history assumptions in that assessment are superseded.
- [Related systems](RELATED_SYSTEMS.md): Prism, Speckle, FreeCAD History Workbench,
  AYON, and OpenAssetIO; use them as reuse/workflow comparisons, not evidence of
  unique Git CAD capability.
- [Materials and lineage](MATERIALS_AND_LINEAGE.md): native graph preservation,
  portable materials, engineering facets, and future Substance/Ansys integration.
- [OpenUSD glossary](https://openusd.org/release/glossary.html): composition,
  references/payloads, paths, and stage/layer semantics.
- [OpenUSD toolset](https://openusd.org/release/toolset.html): viewer, validation,
  and export tools; none automatically supplies Git CAD's snapshot/assembly ledger.
- [PyVistaQt integration](https://qt.pyvista.org/usage.html) and
  [PyVista picking](https://docs.pyvista.org/api/plotting/_autosummary/pyvista.plotter.enable_mesh_picking):
  selected viewport integration references.
- [Monad System](https://github.com/range-et/monad_system/tree/358d0559da407897957a5817b24f9ebd8774b791):
  reviewed theme source and pinned design-token revision.
- [PySide6](https://doc.qt.io/qtforpython-6/), [Typer](https://typer.tiangolo.com/),
  [Pydantic](https://docs.pydantic.dev/latest/), [uv](https://docs.astral.sh/uv/),
  and [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk):
  implementation dependencies to pin and qualify before release.

## 19. Review summary and remaining engineering gates

This draft commits to Python with reference OpenUSD, PySide6/PyVista inspection,
Monad theme tokens, local immutable USD history, independent source branches,
explicit main selection, reusable assembly recipes, versioned material slots and
provider assets, and optional AI integration. The UI is required in v1.
Direct STL export from historical snapshots and assemblies is also required in v1.

It deliberately excludes feature/vertex merging, automatic native geometry sync,
full native scene history, renderer equivalence, cloud collaboration, and execution
of FEA/CFD/FEM solvers. Engineering cards can be preserved and assigned before a
provider can evaluate them. Native material-only assets are retained when required
for the declared Blender graph-fidelity workflow.

The remaining implementation gates are executable evidence, not permission to
silently weaken the contract: exact-save hooks; a clean Python/OpenUSD/Qt/VTK build;
dependency-aware selection extraction; slot round trips; historical shader restore;
and a packaged UI with correct picking and lineage. Unsupported features require
explicit capability reports and must not be marketed as completed functionality.

The first reviewable vertical slice is: initialize a folder, save in both apps,
browse their USD snapshots, pick pieces in the Monad-themed PyVista UI, bind an old
material, save an assembly, set main, and explicitly import it into Blender with
the supported native graph. No agent must be needed at any step.
