# CAD-GIT v0.1 Specification

Status: proposed implementation contract. Date: 2026-11-07.

This specification defines the first local Rust release, including its CLI and
required visual comparison/resolution UI. Requirements marked MUST are
release requirements; SHOULD identifies a preferred implementation with a
documented reason required for deviation; MAY identifies optional behavior.
Examples describe intended interfaces, not software already implemented.

## 1. Mission and product promise

CAD-GIT is a fully local versioning tool for CAD and 3D work, implemented around a
Rust core with OpenUSD as its scene description, composition, and interchange
model. It captures native states, records shape changes and immutable ancestry,
reconciles supported edits, and serves selected revisions to native applications.
It starts from the command line and includes a local 3D comparison and conflict
resolution UI. It MUST operate without an AI agent, account, or remote service.
Rhino and Blender are the first test adapters, not the boundary of the product.

OpenUSD is not a programming language for recording modeling actions. CAD-GIT
uses it to parse and compose observable scene states; its own versioned data model
records history, changes, conflicts, and synchronization outcomes. Native files
remain authoritative for app-specific data that USD does not express.

The product promise is: **Every successfully captured version remains recoverable,
and switching versions never silently discards current work.**

The bridge MUST distinguish a native application save from successful bridge
capture. It cannot preserve intermediate edits that were never saved or captured,
saves made while capture was unavailable, or data lost through disk failure.
Capture failures MUST be visible and MUST NOT be reported as successful history.
No automatic pruning or history rewriting is permitted in v0.1.

Git compatibility is secondary. Git, a hosting account, an AI agent, and a network
connection MUST NOT be required for normal operation. Local history is not an
off-device backup. The repository license continues to govern the project;
agent-agnostic interfaces do not imply a different software license.

## 2. Users and principal interactions

The initial user works in an existing project folder with Rhino and Blender on one
workstation. They run `cad-git begin`, save normally or enable CAD-GIT snapshots,
inspect changes visually, resolve conflicts, name checkpoints, and revisit earlier
states. `rhino-blender-bridge` and `rbb` MAY remain compatibility aliases; new
documentation and public APIs MUST use the application-independent CAD-GIT name.

The reference workflow is an engine assembly: Rhino models mechanical parts,
Blender animates their operation and sculpts an organic housing, and both apps
can publish revised shapes. A native CAD body and a derived sculpt mesh can
coexist. Documentation, render setups, and animation remain recoverable in native
files even when they cannot be exchanged through USD.

Automatic behavior MUST be predictable: capture saves, publish valid exchange
data, and apply compatible nonconflicting updates. Conflicting or unsupported
updates remain pending. Historical inspection MUST NOT secretly advance the
current editing branch.

## 3. v0.1 scope

### 3.1 Required

- One local project service and one explicitly bound document per connected app.
- Complete native save captures, immutable manifests, revision ancestry, and
  dependency inventories.
- Native save notifications with an exact-save capture mechanism.
- Configurable tool-initiated snapshots of current in-memory native state.
- Versioned recovery Save Copy/Save As snapshots of all participating documents
  before a synchronization transaction can modify any native application.
- Bidirectional static mesh exchange, including Blender sculpt meshes into Rhino.
- Rhino BRep preservation in `.3dm` plus a tessellated USD representation.
- Stable logical part and instance identity across rename, move, and refresh.
- Part-level change inspection; conservative three-way conflict detection.
- Explicit saved-state deltas and an immutable record of each resolved synced state.
- A local 3D comparison UI with changed-part/property highlighting and explicit
  keep-local, keep-incoming, keep-both, and deletion decisions.
- Named project checkpoints, branches, and selected-revision serving.
- Crash recovery, integrity verification, machine-readable status, and diagnostics.
- A CLI, MCP interface, and an agent-agnostic skill using one domain API.
- A documented, versioned out-of-process plugin protocol and adapter SDK examples.

### 3.2 Deferred

Remote collaboration, hosted repositories, a full GUI project manager, feature-level CAD
merging, automatic surface/vertex merging, mesh-to-BRep reconstruction, general
rigging interchange, bidirectional procedural shader interchange, parametric
constraint interchange, distributed locking, custom USD asset resolvers, storage
delta compression, and automatic storage reclamation are outside v0.1.

The basic visual comparison/resolution UI is required in v0.1; a general CAD
editor, elaborate graphical branch explorer, and cloud collaboration are not.
Full native history MUST be preserved even for deferred exchange features.
Blender edits MUST NOT be treated as view-only merely because they originate in
Blender. Capability limits apply to representations and properties, not app roles.

### 3.3 Initial compatibility

The first reference platform is macOS, Rhino 8, and Blender 5.2 LTS. Exact tested
application builds, bridge adapter versions, USD library versions, and community
integration versions MUST be recorded in a release compatibility matrix. Current
smoke-test observations are Rhino 8.36.26296.17002 and Blender 5.2.3 LTS; they are
observations, not an existing support certification. Other platforms are not
supported until their save, filesystem, and recovery tests pass.

## 4. Domain model

| Entity | Meaning |
| --- | --- |
| Project | Portable project ID, configuration, history, branches, and dependencies. |
| Document | Persistent logical document identity, independent of file path and process. |
| Part | Logical designed component, identified independently of its name. |
| Instance | Placement of a part in an assembly; distinct identity from the part. |
| Representation | A part's native BRep, mesh, sculpt mesh, render mesh, or other realization. |
| Capture | Immutable native save snapshot and its provenance; a history node. |
| Publication | Immutable validated USD exchange package derived from a capture. |
| Checkpoint | Immutable project manifest pinning exact captures, publications, configuration, and dependencies. |
| Branch | Named durable reference to a line of checkpoints. |
| Workspace | The current app binding, editing base, branch, local changes, and applied content. |
| Served state | Exact content acknowledged as applied by an app; may be a preview or a mixed working state. |
| Conflict | Recorded incompatible changes relative to a known shared base. |
| Artifact | Derived deliverable with inputs, settings, hashes, units, and tool versions. |
| Change set | Typed, base-relative observable changes between captured scene states. |
| Sync transaction | Recovery snapshots, change sets, decisions, result composition, and per-app receipts for one reconciliation attempt. |
| Synced state | An immutable resolved composition plus its inputs and application outcomes; never a synonym for an unacknowledged export. |

Captures, publications, checkpoints, conflict records, and resolution records MUST
have separate typed IDs. Parent and input links MUST be explicit. Modification
times and filename numbering MUST NOT determine ancestry. Human-readable labels
are optional aliases; short IDs MUST resolve unambiguously or fail.

A checkpoint MUST distinguish recorded native state from unsaved, applied working
state. A native Blender save taken before a Rhino update MUST NOT be described as
containing that update. Until Blender is saved again, the checkpoint can pin the
native capture plus the applied exchange inputs needed to describe its mixed
state. Exact native restoration uses the native capture; exchange reconstruction
is a separately identified operation with a capability report.

### 4.1 Shape change history

Every comparison MUST record its base and target IDs, normalizer version, units,
comparison tolerance, and per-entity/property changes. Required categories are
add, delete, geometry replacement, geometry deformation where correspondence is
known, topology change, transform change, hierarchy change, name change, and
supported appearance/property change. Geometry change records MUST retain before
and after representation references; summaries MUST not substitute for payloads.

When topology correspondence exists, a change set SHOULD include changed vertex
indices, displacement bounds, and triangle connectivity changes. When it does not,
the result MUST be described as a topology/representation replacement, not an
invented vertex correspondence. Optional approximate surface-distance overlays
MUST be labelled approximate. A bounds change alone is insufficient evidence for
the shape of the edit; unchanged bounds do not establish unchanged geometry.

The bridge records how observable saved states differ. Exported snapshots cannot
reconstruct an unobserved sequence of sculpt strokes, feature operations, or user
intent. Plugins MAY supply native operation history as additional provenance,
clearly distinguishing reported operations from inferred state differences.

Each successful reconciliation MUST create an immutable synced-state checkpoint
pinning the selected representation/property revisions, decisions, and app
acknowledgements. A computed candidate can exist before application, but MUST be
labelled candidate or partially applied until the declared target set acknowledges
it. Native post-apply recovery snapshots SHOULD then record the resulting native
state; failure leaves a degraded receipt rather than erasing the pre-apply backups.

## 5. Architecture

```text
Native save hooks                  CLI / MCP / local 3D UI
   Rhino adapter                         |
   Blender adapter                       v
          |                      Shared domain API
          +------------------------------|
                                         v
                              Local Rust project service
                              - capture/publication queue
                              - history and ancestry
                              - conflict plans
                              - served-state acknowledgements
                                         |
                                         v
                              Immutable history on disk
                              Native files + USD + manifests
```

The project service is stateful. The MCP server is a thin control interface.
There MUST be one service writer per project. Core versioning MUST NOT live in
prompt instructions, an LLM conversation, or third-party MCP-specific code.

Application adapters MUST use native application APIs and main-thread dispatch
for document operations. Community MCP integrations SHOULD be reused for suitable
discovery, inspection, and execution capabilities, behind versioned adapter
interfaces. A community MCP server alone MUST NOT be assumed to provide exact
save capture, stable identity, or transactional application.

The service MUST persist enough intent and outcomes to resume without an agent.
Long operations MUST return operation IDs and expose progress. Rendering or
exporting MUST NOT run inside the MCP request thread indefinitely.

### 5.1 Rust implementation boundary

The history engine, transaction coordinator, semantic diff model, plugin host,
CLI, service, MCP facade, and comparison UI MUST be implemented in Rust. Thin
native-app hooks MAY use the application's supported Python or .NET runtime;
requiring Rust inside Rhino or Blender would increase connector complexity.

The preferred USD backend for v0.1 is the reference OpenUSD SDK, isolated in a
local worker behind a versioned request/response boundary. OpenUSD is principally
a C++ SDK; Rust interfaces and alternative parsers require capability evaluation.
The worker MAY use a small C++ shim or validated Rust bindings. This native
dependency does not change the Rust ownership of history and synchronization.
CAD-GIT MUST NOT implement an ad hoc USDA parser and claim full OpenUSD support.
Binary USDC, composition, instancing, payloads, relative assets, and invalid input
handling MUST pass the reference fixture suite before a backend is accepted.

Worker crashes MUST not take down the history writer or native applications.
The Rust process MUST validate worker outputs before using them. Scene extraction
SHOULD return indexed triangle meshes, transforms, identities, typed properties,
dependency inventories, and capability warnings through a bounded interchange
format. Render buffers are derived caches, not authoritative history. A release
MUST document how the USD SDK is bundled and pin its ABI/build compatibility.

Suggested workspace boundaries are `cadgit-core`, `cadgit-store`, `cadgit-diff`,
`cadgit-sync`, `cadgit-plugin`, `cadgit-usd`, `cadgit-cli`, `cadgit-ui`, and
`cadgit-mcp`. These are responsibility boundaries, not a requirement to create
nine crates before the first end-to-end prototype. Errors MUST be typed; unsafe
FFI MUST remain confined to the USD boundary. No remote database or message broker
is required. SQLite MAY index history; immutable files remain authoritative.

### 5.2 Extensible plugins and minimal connectors

A plugin is a local executable/bridge adapter with a versioned manifest, protocol
version, application/version range, capabilities, and entry point. It communicates
out of process, avoiding a dependency on Rust's unstable native library ABI.
Plugin authors MAY use any language supported by their target application.
Installation is explicit; unknown project files MUST NOT execute plugins.

Required protocol operations are `handshake`, `enumerate_documents`,
`get_document_state`, `snapshot_native`, and `export_usd`, with optional
`subscribe_saves`, `apply_plan`, `restore_native`, and `inspect_managed_state`.
Operations MUST return typed document identity, operation IDs, errors, and
capability limitations. Save subscriptions MUST supply deduplicable event IDs.
`snapshot_native` MUST state whether document path, dirty flag, selection, and undo
state are preserved. The SDK MUST provide a conformance harness and one minimal
example rather than requiring contributors to understand the entire core.

Native hooks perform save notifications, snapshot/export/import, metadata
persistence, and main-thread dispatch. History, diffing, merge decisions, UI, and
retention MUST stay in the core. Existing community MCP integrations MAY transport
these operations but are not required to run CAD-GIT.

Any application that exports supported USD can contribute an exchange snapshot.
An export-only adapter is an ingest plugin, not a full bidirectional connector.
Exact native recovery requires a native snapshot capability; applying back into
an application requires an apply/import capability. Without stable identity,
ingested scenes are opaque replacements or require user-assisted mapping; they
MUST NOT silently receive full automatic part-level synchronization support.
The Rhino and Blender reference adapters MUST meet the complete v0.1 contract.

### 5.3 Local visual comparison and resolution

`cad-git ui` opens a native local window; `cad-git diff A B --visual` opens a
comparison, and `cad-git resolve ID --visual` opens a three-way resolution. The
daemon MUST operate without a window. When auto-application encounters a conflict,
it leaves the transaction pending and exposes the local viewer action. In an
interactive session it MAY open that viewer automatically when configured; a
headless session MUST remain pending without inventing a decision.

The preferred UI stack is `egui`/`eframe` with `wgpu` for a small mesh viewer. This
is a proposed engineering choice subject to a macOS rendering, picking, and
large-mesh prototype, not a claim that these libraries provide USD conflict
resolution themselves. Bevy or Rerun MAY be evaluated, but a game engine, a full
Hydra integration, and photorealistic rendering are not required for v0.1.

The viewer MUST provide:

- Base, local, incoming, and proposed-result views with linked cameras.
- Overlay and side-by-side comparison, orbit/pan/zoom, fit selection, object
  picking, isolation, visibility toggles, and a scale/unit indicator.
- A changed-part list and property panel showing exact before/after values and
  source application/revision. Deletion MUST remain visible as a ghost of the
  removed object; added/changed/deleted/conflicting states use labelled styles
  as well as colors so color is not the only indicator.
- Geometry deformation highlighting where correspondence is known, full-part
  highlighting for topology replacement, and explicit unknown/unsupported labels.
- Keep-local, take-incoming, keep-both, and explicit deletion controls at the
  supported part/property-group granularity. It MUST show dependency effects and
  block combinations the core declares incompatible.
- A result preview, remaining-conflict count, and explicit confirmation to apply.
  Closing the window or cancelling MUST preserve all versions and apply nothing.

Changing a resolution in the UI only edits a candidate plan. On confirmation, the
core MUST revalidate expected bases and document fingerprints before application.
If the user edited an app while reviewing, the stale plan MUST be invalidated or
recomputed. Keep-both assigns distinct alternative/instance identities without
erasing ancestry. Choosing deletion removes content from the served result,
never from retained history. The viewer MUST not execute native modeling code.

If GPU initialization or scene rendering fails, the CLI and history service MUST
remain usable. A textual diff/exported diagnostic MUST remain available; the
visual conflict stays unresolved unless the user explicitly resolves it through
the CLI. Static triangle meshes, basic appearance, wireframes, transforms, and
bounding boxes are the required render subset. Unsupported USD features MUST be
listed rather than silently presented as a complete visual reproduction.

## 6. Project layout and authoritative state

```text
project/
├── cadgit.json
├── source/                         # Suggested working native-file location
│   ├── model.3dm
│   └── scene.blend
├── assets/                         # Working dependencies
├── usd/
│   └── scene.usda                  # Regenerated current exchange entry point
├── history/
│   ├── project.json                # Project identity and format versions
│   ├── captures/<capture-id>/
│   │   ├── manifest.json
│   │   ├── native/<saved-file>
│   │   └── dependencies/...
│   ├── publications/<publication-id>/
│   │   ├── manifest.json
│   │   ├── scene.usda
│   │   ├── parts/...
│   │   └── assets/...
│   ├── checkpoints/<checkpoint-id>/manifest.json
│   ├── conflicts/<conflict-id>/manifest.json
│   ├── resolutions/<resolution-id>/manifest.json
│   └── events/<sequence>-<event-id>.json
├── artifacts/<kind>/<artifact-id>/
│   ├── manifest.json
│   └── outputs/...
└── .cadgit/
    ├── connections.local.json
    ├── index.sqlite                # Rebuildable query index
    ├── staging/
    ├── locks/
    └── logs/
```

Working files MAY remain in their existing project locations. `begin` MUST NOT
move them without an explicit command. Portable manifest paths MUST be relative
to their documented root; persisted paths MUST NOT escape that root. External
dependencies have an original locator plus a captured project-local copy or an
explicit unresolved status.

`history/` and recorded `artifacts/` are durable. They MUST NOT be placed solely
inside `.cadgit/`. Events form the authoritative ordered record of branch updates,
document bindings, publication outcomes, and successful application receipts.
Mutable query caches and connection locations are rebuildable. Events MUST NOT
contain credentials. A signed or tamper-proof audit trail is not a v0.1 claim.

The filesystem layout is intentionally simple and may duplicate large files.
Deduplication MAY reuse byte-identical immutable payloads, but MUST NOT use
writable hard links to native working files. Future optimization MUST preserve
logical captures and their recorded ancestry.

## 7. Identity and representations

The bridge MUST persist project, document, part, instance, and representation IDs.
Rhino object GUIDs and Blender object custom properties are adapter mappings to
these identities, not interchangeable global identities. Multiple native objects
can realize one representation; assembly instances reference a shared part.

Bridge-managed USD paths SHOULD use immutable identifiers, for example:

```text
/World/Parts/p_<part-id>/Representations/r_<representation-id>
/World/Assembly/Instances/i_<instance-id>
```

Names and layer/collection organization are editable metadata. Identity MUST
survive renaming and moving. Duplicate objects MUST receive new instance or part
identities according to whether they are instances or independent copies. If an
adapter cannot establish that distinction, it MUST report ambiguity and avoid
automatic reconciliation. Copy/paste across projects and copied project folders
require identity validation; creating an independent project requires an explicit
fork operation.

Representations record `derived_from`, conversion settings, and source revision.
A Blender sculpt derived from a Rhino tessellation MUST NOT replace or erase the
native BRep. A newer BRep may make the sculpt out of date; it does not establish
that the sculpt is unwanted. Promotion of an alternate representation as the
served shape is an explicit recorded resolution.

## 8. Save capture contract

### 8.0 Snapshot before synchronization

The first data operation of every apply-capable synchronization transaction MUST
be a versioned native recovery snapshot of every participating bound document:
both Rhino and Blender in the reference workflow. This MUST capture current
in-memory state, including unsaved edits, through Save Copy/Save As semantics.
Copying the last native file on disk is insufficient when the app is dirty.
The snapshot MUST be written to a unique versioned location, verified, and
committed to history before diff/reconciliation proceeds or any target is changed.
The active working file path SHOULD remain stable; if only Save As is available,
the adapter MUST restore the working binding without dropping dirty state or
changing the user's editing lineage. If it cannot do so safely, it is unsupported.

The triggering save can satisfy the source snapshot only when its document token
proves no subsequent in-memory edits occurred. Otherwise a new recovery snapshot
is required. Recovery snapshots are retained but MUST NOT recursively trigger new
sync transactions. Save events MUST distinguish user save, tool autosnapshot,
pre-sync recovery, and post-apply snapshot origins.

Snapshots across apps are not simultaneous. Their document tokens and capture
times MUST be recorded and rechecked before apply. If either app changes during
capture/review, replan from protected inputs; no stale result can be applied.
If either participating app cannot snapshot, stop the transaction before mutation
and show the reason. Independent source capture/publication MAY continue while a
target is closed; it MUST not be called a successful two-app sync. All previously
captured files remain intact when the pair snapshot is incomplete.

### 8.1 Sources and defaults

Normal native Save and Save As are capture triggers while monitoring is active.
The adapter MUST distinguish these from bridge-generated exports, temporary save
copies, autosaves, and recovery writes. Autosaves are excluded by default and can
be enabled as a separately labelled capture class. Save As preserves logical
document identity unless the user explicitly forks the document.

CAD-GIT's own timed snapshots are separate from native autosave files. They MUST
use a non-destructive snapshot API and MUST NOT overwrite the working native file.
The default configuration enables a 300-second interval; users can disable or
change it. Unchanged documents MAY reuse payload bytes while retaining the
snapshot event. Busy native operations MAY postpone capture to a safe main-thread
boundary, with overdue status visible. A tool autosnapshot is an authoring capture
and can trigger synchronization; a pre-sync recovery copy is not another trigger.

Native events are authoritative; directory watching is a diagnostic/recovery
fallback. A watcher MUST NOT claim that it captured every save merely because it
observed a final file modification. The service MUST report monitoring gaps.

### 8.2 Exact-save capture

On completed native save, the adapter MUST secure the exact saved bytes into an
immutable staging copy before a subsequent managed save can overwrite those
bytes. This may require a short synchronous copy or a verified native snapshot
mechanism. Async export alone does not satisfy native capture.

Native-document mutations and saves MUST be serialized appropriately in the app.
If exact capture cannot be guaranteed by an integration, its capability is
`best_effort`, automatic exact-save mode MUST be disabled, and status MUST explain
the limitation. External programs simultaneously rewriting the same native file
are unsupported and MUST cause verification failure when detected.

Each capture records event ID, app/document IDs, native file hash and size, UTC
time, source branch/base, last applied exchange inputs, versions, and dependency
inventory. Native capture completion is independent from publication completion.
Two unchanged saves MAY reference identical bytes but MUST retain distinct save
events. Debouncing exports MUST NOT erase save captures.

### 8.3 Dependency completeness

The bridge MUST inventory file references supported by its adapters, including
textures and linked native assets. It MUST preserve required external files for
self-contained recovery or mark the capture incomplete. Missing or opaque
dependencies MUST be reported; the tool MUST NOT promise complete recovery while
ignoring them. Captured dependency bytes describe capture-time contents, not an
unprovable earlier state of an independently modified external asset.

Executable dependencies, add-ons, fonts, and application versions MUST be
recorded where detectable; they are not automatically redistributed. Exact
re-rendering across different application versions is not guaranteed.

### 8.4 Capture failure

A native save can succeed while capture fails. The user MUST see that distinction
through app feedback where available, CLI status, and an error event. Disk-full,
permission, hash, or copy failures MUST leave the previous history intact. The
service MUST NOT silently drop earlier saves to relieve backpressure. It SHOULD
allow native editing to continue while clearly reporting that capture is degraded.

## 9. Publication and OpenUSD contract

Each captured version MUST have a publication attempt or an explicit unsupported
or deferred status. By default, all supported captures are exported; rapid saves
MAY be processed later, but each export MUST read its exact capture rather than
whatever happens to be current in the app. If a runtime cannot export an older
capture safely, it MUST use an isolated native document/process or preserve an
exact exchange snapshot at capture time. Reopening an old capture over the
user's working document is prohibited.

Publication stages are:

```text
CAPTURED → EXPORT_QUEUED → EXPORTING → VALIDATING → PUBLISHED
                                   ↘ FAILED / UNSUPPORTED
```

A publication MUST include a root stage, all required layers/assets, a source
capture ID, per-part identity mappings, exporter settings and versions, file
hashes, coordinate metadata, and a capability/loss report. Failed attempts remain
recorded; retries produce new outcome records/publications without mutating the
original capture.

### 9.1 Coordinates

Canonical bridge publications MUST use Z-up, right-handed coordinates and
`metersPerUnit = 1.0`. Rhino millimeter geometry MUST be converted explicitly.
Exporter-native Y-up data MUST be transformed or wrapped with a tested basis
conversion; changing `upAxis` metadata alone is invalid. Conversion MUST happen
exactly once. Reflections, normals, winding, negative scales, transforms, and
instance placements require validation.

Historical native units and tolerances MUST be retained. Existing smoke-test USD
files use native Y-up millimeter output and are not yet canonical publications.

### 9.2 Composition

Publications SHOULD separate reusable part definitions, assembly placements,
geometry, and portable appearance opinions. The native `.blend` retains full
animation, lighting, cameras, modifiers, and shaders; `.3dm` retains native CAD
and documentation. Only declared supported properties participate in exchange.

The root SHOULD provide a `/World` default prim. Binary `.usdc` SHOULD hold heavy
geometry; `.usda` SHOULD hold readable composition and overrides. v0.1 SHOULD use
ordinary relative references and pinned revision paths. A custom asset resolver
and a VariantSet containing every historical revision are not required.

Layers MUST NOT be used to hide a same-property conflict by strength ordering.
Full exports MUST NOT be placed as competing whole-scene sublayers and described
as a merge. A reconciled project composition references selected per-part inputs
and recorded resolutions. Flattened exports MAY be generated as artifacts but
MUST NOT replace the authoritative layer graph or native history.

### 9.3 Validation

Validation MUST check composition opens, dependency resolution, identity
uniqueness, supported prim types, finite geometry/transforms, declared units and
axis, and source-to-output bounds within configured tolerance. A calibration
test MUST verify asymmetric shape placement and orientation as well as size.
Unsupported objects and omitted properties MUST be listed. A partial publication
MUST NOT be auto-applied as if omitted objects were deleted.

## 10. Change detection and reconciliation

### 10.1 Shared base

Independent editing creates divergence from a common base; it does not by itself
establish a conflict. Different parts or compatible property changes can reconcile
automatically. A conflict means incompatible edits or a dependency violation,
not merely two independently saved files. Unsaved target edits also count: the
mandatory pre-sync snapshot preserves them and reveals divergence before any
overwrite. File timestamps and whether the user pressed Save are not merge rules.

Reconciliation compares base, local, and incoming values for a known part,
representation, instance, and property group. Base is the exact applied source
recorded in the target workspace, not the last global save or newest timestamp.
Targets can contain mixed part revisions; the bridge MUST retain that mapping.

Managed groups are geometry, placement, hierarchy, display metadata, and declared
portable appearance properties. Adapter-native animation and other unexchanged
data remain protected local state. Local dirty detection MUST inspect managed
in-memory state before application, even if the native file has not been saved.
A broad app dirty flag alone does not identify which part changed; uncertainty
MUST block automatic application for the affected scope.

Exact file hashes establish byte identity, not geometric equivalence. Semantic
fingerprints MUST use a versioned normalization algorithm and declared numerical
tolerances. Unknown or nondeterministic differences are conservatively treated as
changes; approximate matching MUST NOT silently reassign identity.

### 10.2 Default decisions

| Base-relative changes | Decision |
| --- | --- |
| Incoming changed; local managed state unchanged | Apply after compatibility checks. |
| Local changed; incoming unchanged | Keep local, record divergence. |
| Both changed to an identical supported value | Converge and record acknowledgement. |
| Both changed different parts | Combine if dependencies remain compatible. |
| Same part, distinct independent groups | Combine only when an explicit compatibility rule permits. |
| Same geometry changed on both sides | Record conflict; preserve both. |
| Delete versus modify | Record conflict. |
| Identity, ancestry, or completeness uncertain | Leave pending; require diagnosis/resolution. |

Geometric and placement edits are not automatically independent: altered part
origins or pivots can change the interpretation of a transform. Dependency checks
MUST consider these relationships. v0.1 MUST NOT claim surface-level or
vertex-level merging.

Conflicts record base/local/incoming IDs, affected groups, dependency impact, and
available resolutions. Resolutions include keep local, take incoming, keep both,
or supply a manually reconciled new representation. A resolution is immutable and
links all inputs. Any automatic or agent-requested resolution MUST be auditable.

### 10.3 Deletion and scope

Only explicit tombstones from a complete managed inventory can propagate deletion.
Selection-only export, hidden objects, filters, exporter failures, and missing
payloads MUST NOT imply deletion. The bridge MUST never delete unmanaged content.
Removed parts remain recoverable in history. Deleting a referenced part or
changing assembly structure requires dependency checks before application.

## 11. Applying updates and serving revisions

The end-to-end synchronization sequence is:

```text
SAVE / TIMED SNAPSHOT / EXPLICIT SYNC
  → VERSIONED NATIVE SNAPSHOTS OF ALL PARTICIPANTS
  → VERIFY SNAPSHOTS AND THEIR DOCUMENT TOKENS
  → PARSE EXACT USD STATES AND COMPUTE BASE-RELATIVE CHANGE SETS
  → RECONCILE OR RECORD CONFLICT
  → VISUAL REVIEW WHEN REQUIRED
  → COMMIT RESOLUTION AND CANDIDATE SYNCED STATE
  → RECHECK TARGET TOKENS
  → APPLY SUPPORTED RESULT
  → RECORD PER-APP ACKNOWLEDGEMENTS AND RESULT SNAPSHOTS
  → MARK SYNCED / PARTIALLY APPLIED / FAILED
```

Snapshots are the first data operation, before comparisons used to authorize a
sync. Lightweight connection/status inspection is permitted before snapshots.
Existing immutable USD publications MAY be reused only when they match the exact
protected native state. A diff from the last on-disk save MUST NOT conceal unsaved
in-memory edits. Before preview/native restore, the same protection applies to
all documents that the operation can mutate.

Application uses a durable plan with target workspace, expected base, incoming
inputs, affected IDs, compatibility checks, recovery capture, and operation ID.
Immediately before mutation the target MUST be rechecked; a stale plan MUST fail
or be recomputed. Applying an update MUST NOT trigger automatic native saving.
Native saves remain user actions unless explicitly requested by a command.

Blender SHOULD retain stable object containers for transforms and animation while
replacing compatible mesh data beneath them. It MUST NOT delete/recreate entire
collections on refresh. Topology-dependent modifiers, vertex groups, UVs,
material slots, shape keys, and rigging require adapter-specific checks. If their
preservation cannot be established, the update remains pending or is imported as
an explicit alternate representation. Retaining an object name is not a
compatibility guarantee.

Rhino MUST receive supported mesh representations without silently replacing a
native BRep with a mesh. Native object attributes and downstream references MUST
be preserved where supported; otherwise the plan MUST report the limitation.

Apply lifecycle:

```text
AVAILABLE → PLANNED → RECOVERY_CAPTURED → APPLYING → ACKNOWLEDGED
                 ↘ CONFLICT / BLOCKED          ↘ FAILED / UNKNOWN
```

An app acknowledgement MUST include applied inputs, resulting managed-state
fingerprint, and target document identity. The served reference advances only
after acknowledgement. A disconnected or crashed target remains failed/unknown
until inspection; the bridge MUST NOT infer success from sending a command.

`serve` applies a historical exchange state to bridge-managed content in a target
workspace. It does not move branch history or restore the whole native document.
Default serving creates a detached preview, pauses automatic incoming application
for that target, and reports the target as pinned. Editing/saving from preview
requires an explicit fork or return to the prior workspace; capture still
preserves the save while publication is held pending that decision.

`restore-native` opens an exact native capture after securing current work. It
does not pretend a mesh import can reconstruct native features or application
state. If recovery capture cannot be made, switching MUST stop. Applying changes
in both apps is a coordinated operation with individual receipts, not an atomic
cross-application transaction; partial success MUST be reported accurately.

## 12. History, branches, and checkpoints

Every capture remains addressable. Named checkpoints pin exact inputs and record
a message; they do not rewrite or squash automatic captures. A branch advances
through explicit checkpoint records and resolutions. History queries SHOULD
default to a readable checkpoint/session view while `--all` exposes every event.
Filters MUST support app, document, part, representation, branch, and time.

A checkpoint without `--save` records the latest available native captures and
known applied inputs, explicitly reporting unsaved app state. `checkpoint --save`
requests native saves from all selected apps and records their successful
captures. If one fails, it MUST NOT label a partial combination complete; an
explicit `--allow-incomplete` can record an incomplete checkpoint. No simultaneity
claim is made about saves taken at different times.

Storage growth MUST be visible through `status`/`storage`. v0.1 MUST NOT delete
captures automatically. Disk-full stops new history publication safely. Complete
project backup requires all durable files, including referenced dependencies;
copying only the current USD root or native working files is insufficient.

## 13. Artifact provenance

Artifacts are optional typed outputs under `artifacts/<kind>/<artifact-id>/`.
Kinds are extensible strings, such as `prints`, `renders`, `drawings`, or
`simulations`. No fixed directory per hypothetical output type is required.

Each recorded artifact MUST include its exact checkpoint/publication inputs,
source hashes, settings, units, relevant coordinate conventions, creator/tool
versions, output hashes, timestamp, and dependency inventory. A print export
SHOULD record tessellation and mesh validation settings. A render SHOULD record
camera, renderer, frame, resolution, and available color-management settings.
The bridge records provenance; it does not certify manufacturability or guarantee
identical rendering on another machine. Recorded outputs are immutable; retries
produce new artifacts. Arbitrary artifact registration is required; automated
print/render execution can be added by later exporters.

## 14. CLI contract

Canonical executable: `cad-git`. Legacy aliases MAY be `rhino-blender-bridge` and
`rbb`; no Git executable integration is implied by the name.

| Command | Required behavior |
| --- | --- |
| `begin [path]` | Initialize absent metadata, resume/start the service, discover apps, bind unambiguous documents, and enable monitoring. Idempotent. |
| `stop` | Stop monitoring cleanly after recording queue state; never close apps or discard history. |
| `status` | Report connection, capture coverage, dirty/pinned state, captured/published/applied IDs, queues, conflicts, and failures. |
| `bind --app APP --document ID` | Explicitly select a target; never choose arbitrarily among ambiguous documents. |
| `adopt --app APP --scope all\|selection` | Capture a baseline and enroll explicitly selected content in identity tracking and exchange. |
| `capture --app APP` | Request a native save/capture through the adapter. |
| `sync` | Snapshot all participants, compare, reconcile, and apply only a protected compatible result. |
| `autosave on\|off [--interval SECONDS]` | Configure non-destructive timed native snapshots. |
| `publish CAPTURE` | Queue/retry exchange publication from that exact capture. |
| `log [--all] [--part ID]` | Query immutable history and readable summaries. |
| `show ID` | Inspect a typed record, dependencies, and provenance. |
| `diff A B [--part ID] [--visual]` | Report semantic changes; optionally open the local 3D comparison. |
| `ui [--conflict ID]` | Open the local history/comparison/resolution window. |
| `checkpoint -m TEXT [--save]` | Record a pinned project combination; optionally request native saves first. |
| `branch NAME --from CHECKPOINT` | Create a durable history reference without mutating app documents. |
| `switch BRANCH --app APP` | Protect current work and move the target to the selected editing branch. |
| `serve CHECKPOINT --app APP` | Preview a selected historical exchange state without moving branch history. |
| `resume --app APP` | Leave preview/pinned mode through a protected transition. |
| `fork NAME --from ID --app APP` | Create and bind an editable branch from the selected state. |
| `restore-native CAPTURE --app APP` | Protect current work and reopen the exact native save. |
| `conflicts` | List unresolved conflicts and their three-way inputs. |
| `resolve ID --keep local\|incoming\|both` | Record and apply an explicit resolution plan where supported. |
| `resolve ID --visual` | Review base/local/incoming and confirm choices in the 3D UI. |
| `plugin list\|inspect\|register` | Inspect capabilities or explicitly register a local plugin manifest. |
| `artifact register PATH --kind KIND --from CHECKPOINT` | Preserve outputs and provenance. |
| `verify [ID]` | Check hashes, dependency closure, manifests, and USD validity. |
| `doctor` | Diagnose integration versions, missing hooks, identities, queues, and partial operations. |
| `storage` | Report retained bytes and projected pressure without pruning. |
| `operation ID` | Inspect a long-running operation and individual app receipts. |

`begin` MUST NOT open/close documents, overwrite existing configuration, adopt all
scene objects, initialize Git, or upgrade adapters silently. Ambiguous binding or
adoption leaves a clear pending setup action. Initial adoption captures a baseline
and assigns identity only within the explicitly selected scope. Existing
unmanaged content remains unmanaged until adopted.

Commands MUST support `--json`, return structured error codes, and keep diagnostic
text off JSON output. Suggested envelope:

```json
{
  "schema_version": 1,
  "ok": true,
  "operation_id": "op_...",
  "state": "queued",
  "result": {},
  "warnings": [],
  "error": null
}
```

Exit codes: 0 success/accepted queue operation; 1 operation failure; 2 invalid
arguments/configuration; 3 conflict or blocked transition; 4 unavailable service
or adapter; 5 integrity failure. Queued acceptance is not completion. `--wait`
MUST return the final operation result or a timeout with an operation ID; timeout
does not cancel the underlying operation.

## 15. Project configuration

`cadgit.json` is portable, versioned, validated, and captured with history.
Machine-local ports, process IDs, credentials, and absolute installation paths
belong outside it. Unknown required schema versions MUST fail clearly. Config
migrations MUST preserve the old bytes in history and be explicit.

Illustrative v1 configuration:

```json
{
  "schema_version": 1,
  "project": {"id": "<uuid>", "name": "engine"},
  "documents": [
    {"id": "<uuid>", "app": "rhino", "path": "source/model.3dm"},
    {"id": "<uuid>", "app": "blender", "path": "source/scene.blend"}
  ],
  "paths": {"history": "history", "artifacts": "artifacts", "runtime": ".cadgit"},
  "capture": {
    "on_save": true,
    "autosaves": false,
    "tool_snapshots": {"enabled": true, "interval_seconds": 300},
    "before_sync": "all_participants",
    "require_exact_snapshot": true,
    "dependencies": "capture_or_mark_incomplete"
  },
  "exchange": {
    "direction": "bidirectional",
    "trigger": "captured_save",
    "auto_apply": "compatible_nonconflicting",
    "publication_policy": "every_supported_capture",
    "canonical_up_axis": "Z",
    "meters_per_unit": 1.0,
    "comparison_tolerance_m": 0.000001
  },
  "history": {"retention": "all", "automatic_pruning": false},
  "ui": {"open_on_conflict": true, "renderer": "wgpu"},
  "git": {"required": false, "initialize": false}
}
```

Comparison tolerance is not a meshing or manufacturing tolerance. Meshing presets
MUST be adapter-specific, separately configured, and recorded per publication.
The earlier `test/bridge.json` is an obsolete prototype with one-way ownership;
it MUST NOT be treated as the schema or migrated by guessing missing values.

## 16. MCP and agent skill

MCP tools MUST call the same domain operations as the CLI. The default MCP
transport is stdio; it does not require a public HTTP port. Required tools are
`project_status`, `begin`, `bind_document`, `adopt_content`, `capture`, `publish`, `history`,
`show_record`, `diff`, `checkpoint`, `branch`, `switch`, `serve`, `resume`, `fork`,
`restore_native`, `list_conflicts`, `resolve_conflict`, `register_artifact`,
`verify`, `doctor`, `sync`, `configure_autosnapshot`, and `get_operation`.
Stop/storage/plugin inspection MAY also be exposed. UI, CLI, and MCP MUST use
the same resolution and pre-sync snapshot safeguards.

Mutations MUST accept idempotency keys and, where relevant, expected workspace
base IDs. Responses MUST include operation IDs, affected records, warnings,
capability/loss reports, and structured errors. Read operations SHOULD support
pagination and scope filters. Raw arbitrary Python/C# execution is not a public
bridge domain tool; internal adapter use is constrained to its declared work.

The agent-agnostic skill MUST document setup, status interpretation, recovery,
supported representations, conflict resolution, and the distinction between
serve and native restore. It MUST instruct agents to inspect status before
mutation, preserve recovery captures, and avoid resolving geometric conflicts
without a user-authorized strategy. The agent MUST NOT bypass safeguards or
silently delete alternate versions. Human-authored descriptions and agent
summaries MUST be attributable; an agent summary is not geometric proof.

## 17. Transport, capabilities, and security

No fixed app ports are required. Discovery records adapter instance, protocol
version, app version, document IDs, and capabilities. Existing Rhino router and
Blender community listener protocols remain separate adapters; neither is
assumed to implement the proposed bridge protocol.

The service control transport SHOULD use a user-scoped local socket. Loopback
TCP is acceptable with an unpredictable local token, bounded messages, and
restricted origin/path handling. Remote listening is disabled. Credentials MUST
NOT be written to portable history. Project paths and parameters are data, never
shell commands or concatenated native command scripts.

The internal protocol MUST define framing, request IDs, complete-message reads,
size limits, structured errors, deadlines, cancellation semantics, and bounded
queues. Repeated mutation requests MUST be idempotent. Long exports have
operation-specific deadlines, not one universal five-second timeout.

Cancellation MUST preserve committed captures and publications. Queued work can
be cancelled explicitly; an in-progress native operation can stop only at an
adapter-declared safe boundary. Abandoning an MCP connection or timing out MUST
NOT implicitly cancel work or roll back another client's operation.

Adapters MUST advertise capabilities such as `exact_save_capture`,
`native_restore`, `mesh_publish`, `mesh_apply`, `identity_persistence`,
`dependency_inventory`, `dirty_part_detection`, and supported property groups.
Unsupported combinations MUST be blocked or left pending, never advertised as
full round-trip support. Legacy community listeners that allow arbitrary code
execution MUST be identified in diagnostics and remain local trusted endpoints.

## 18. Durability, recovery, and observability

Record creation MUST stage bytes on the same filesystem, flush/fsync files as
supported, write and verify manifests, rename into final immutable locations, and
durably publish a commit event. Directory fsync SHOULD be used where supported.
A record is visible as committed only after its commit event. An interrupted
uncommitted directory is retained as recoverable staging/orphan data, not silently
invented as a complete revision. Network/cloud-synced folders are unsupported as
active stores until their rename and durability behavior is tested.

The event writer MUST serialize changes under a project lock. Branch reference
updates MUST use expected-parent checks. SQLite indexes and convenience USD roots
are updated after durable records and can be rebuilt. Deleting `.cadgit/` while
the service is stopped MUST NOT destroy committed history. Active staging and
unacknowledged recovery data MUST NOT be cleaned during operation.

On restart, the service MUST validate committed events, inspect interrupted
operations, reconnect by document identity, and compare actual managed app state
before replaying anything. If an app applied a change but its receipt was lost,
fingerprint inspection MUST prevent duplicate import. When outcome remains
uncertain, mark it unknown and require recovery rather than advancing references.
If application fails after partial mutation, the adapter MUST attempt a verified
rollback where supported; otherwise it MUST expose the recovery capture and the
partial state. Merely retaining a backup MUST NOT be reported as a successful
rollback. Native undo is a convenience, not the sole recovery mechanism.

Logs MUST include UTC timestamps, project/app/document IDs, operation IDs,
capture/publication IDs, durations, and structured failure reasons. UI clients can
localize timestamps. Status MUST distinguish capture pending, publication pending,
incoming pending, conflict, pinned preview, incomplete dependencies, missing
adapter, monitoring gap, and unknown apply outcome.

No hard latency or throughput claim is made before measurement. Release
benchmarks MUST report native-save capture delay, export duration, application
duration, storage growth, part count, and mesh size. Capture takes priority over
publication/application when resources are constrained. A stopped service MUST
not leave the apps frozen or their native save commands unusable.

History queries MUST use the rebuildable index rather than reparsing all USD.
Diffing MUST skip byte-identical immutable payloads, while still reporting native
file changes that are not exchangeable. Scene extraction, diff computation, and
render-buffer preparation MUST run off the UI event thread. Large models SHOULD
load progressively with cancellation and explicit preview detail levels; reduced
preview detail MUST NOT reduce the fidelity of retained data or resolution inputs.
Native snapshot latency MUST be measured separately from background work; the
tool MUST not promise zero-impact saving when it must copy a large native file.

## 19. Git interoperability

`begin` SHOULD create or append a clearly delimited bridge section to `.gitignore`
and `.gitattributes`, preserving unrelated rules. Existing files MUST NOT be
replaced wholesale. The default Git profile ignores runtime data, application
backup files, and large bridge history/artifact payloads; it retains working
source/config according to the user's repository policy. The CLI MUST explain
that ignored history is not backed up by a Git push.

If native files are tracked, `.gitattributes` SHOULD mark `.3dm`, `.blend`, and
`.usdc` as binary so text conversion and text merging are not used. Git LFS is an
optional explicit profile, not an automatic dependency. `.gitignore` neither
protects binary contents nor stops tracking files already committed. Git commands
MUST NOT be used as the bridge's native capture or reconciliation implementation.

## 20. Acceptance criteria

v0.1 is complete only when the following scenarios pass on the release matrix.
Tests MUST exercise real adapters as well as core storage logic; mocked socket
responses alone do not validate application behavior.

1. **Initialize/resume:** `begin` twice preserves existing project files and
   produces one writer. Ambiguous documents remain unbound with actionable status.
2. **Rapid saves:** several distinct saves produce recoverable native captures
   matching each saved version, even while export lags. Unchanged saves retain
   events without requiring duplicate payload bytes.
3. **Export failure:** native capture survives; the failed publication is visible;
   retry exports that exact historical capture.
4. **Rhino to Blender:** an asymmetric, multi-part millimeter assembly arrives at
   correct meter scale, orientation, origin, and instance placement. Repeat apply
   creates no duplicate parts.
5. **Blender to Rhino:** an edited/sculpted mesh arrives with identity and expected
   shape. Its originating BRep remains recoverable and is not silently erased.
6. **Rename/duplicate:** renames and moves retain identity; independent duplication
   creates distinct identity. Ambiguous copied identity is detected.
7. **Independent changes:** changes to different compatible parts combine, while
   current animation/object identity is retained for a supported geometry update.
8. **Topology-sensitive update:** a potentially broken rig/modifier/material
   mapping is blocked or imported as an explicit alternative, not silently lost.
9. **Conflict:** both apps reshape one part from a shared base. Both inputs and the
   base remain recoverable; no latest-writer-wins overwrite occurs. Keep-both and
   manual resolution create traceable new records.
10. **Delete versus modify:** explicit deletion conflicts correctly; selection-only
    and incomplete exports cannot delete omitted objects or unmanaged objects.
11. **Historical serving:** serving a checkpoint protects dirty target state,
    acknowledges exact applied content, pins the preview, and leaves branch
    history unchanged. Failure to capture recovery prevents switching.
12. **Native restore:** each saved `.3dm`/`.blend` opens from history with its
    captured dependencies and declared limitations. Restoring creates no mutation
    of the historical files.
13. **Partial checkpoint:** one app save fails; status and manifest do not claim a
    complete coordinated native checkpoint.
14. **Crash injection:** crashes during staging, manifest commit, branch update,
    export, and apply do not corrupt previous history or cause duplicate replay.
15. **Integrity/storage:** missing dependency, hash corruption, disk full, and
    unavailable target produce distinct failures without pruning history.
16. **Rebuild:** with the service stopped and no in-flight capture, runtime index
    deletion followed by rebuild recovers history, refs, and operation receipts.
17. **No feedback loop:** applying incoming geometry does not create endless
    export/import cycles. Subsequent unchanged user saves are distinguishable from
    new local geometry edits.
18. **Interface parity:** CLI and MCP produce the same domain effects, safeguards,
    and error semantics, including retries with the same idempotency key.
19. **Artifact recovery:** a registered render or print output remains linked to
    exact sources and verifies byte-for-byte after later geometry changes.
20. **Agent-free operation:** capture and safe auto-application continue with no
    MCP client or AI agent connected.
21. **Snapshot-first transaction:** unsaved edits exist in both apps. A sync first
    commits recovery Save Copy snapshots of both, then computes changes. Failure
    to snapshot either app prevents mutation of both. Recovery snapshots cannot
    cause recursive synchronization.
22. **Visual resolution:** the local viewer shows base/local/incoming/result,
    identifies changed parts/properties, distinguishes replacement from known
    deformation, and previews keep-both/deletion. Cancel makes no changes; confirm
    rechecks bases. Editing during review invalidates stale plans.
23. **Timed snapshots:** the configured interval captures dirty in-memory state
    without changing the active native path. Busy-app postponement, disabling,
    restart, and snapshot failure are visible and do not erase history.
24. **Plugin extensibility:** a third export-only test plugin ingests a supported
    USD scene through the documented protocol without changing core code. Its
    missing identity/apply/native-recovery capabilities are reported accurately.
    Malformed messages or plugin/worker crashes cannot corrupt history.
25. **Synced-state provenance:** every successful sync has an immutable result
    checkpoint linking protected inputs, typed deltas, resolution choices, and
    per-app receipts. A failed or partial apply is never shown as fully synced.

## 21. Delivery sequence and release gate

1. Implement history records, durable commit/recovery, manifests, and verification.
2. Prove exact native save capture and dependency inventories in both apps.
3. Implement canonical mesh publication, stable identity, and repeatable one-way
   application in each direction, then combine into bidirectional operation.
4. Add dirty-state comparison, conflict preservation, and compatibility plans.
5. Add checkpoints, protected historical serving/native restore, and branches.
6. Deliver the local 3D comparison/resolution UI, CLI/MCP parity, plugin SDK, and
   agent-agnostic skill; run the full engine scenario without an agent.

Exact-save capture is the first feasibility gate. If the available community
integrations cannot meet it, implement the minimal native hooks rather than
weakening the history promise. Geometry reconciliation is the second gate:
conservative pending conflicts are acceptable; silent overwrite is not.

The release MUST include a tested compatibility matrix, storage format version,
capability table, recovery instructions, known-loss report, and measured reference
benchmarks. It MUST describe itself as a local Rust CAD versioning tool with visual
resolution and supported USD exchange, not a universally lossless CAD translator or general geometric merger.

## 22. Research basis

These sources informed the design. Product claims are not treated as independent
evidence of reliability; repository features require evaluation before reuse.

- [OpenUSD introduction](https://openusd.org/release/intro.html): composition,
  extensibility, path-based identity limitations, and scope of interchange.
- [Onshape merging documentation](https://cad.onshape.com/help/Content/Document/merging.htm):
  common-base merges, incompatible changes, and document-type limitations.
- [Blender Studio SVN](https://studio.blender.org/tools/addons/blender_svn):
  application-visible history/status and outdated-file awareness.
- [Anchorpoint Blender version control](https://www.anchorpoint.app/tools/blender-version-control):
  binary storage and specialized lock visibility trade-offs.
- [Omniverse Live sessions](https://docs.omniverse.nvidia.com/extensions/latest/ext_core/ext_live/sessions.html):
  separate sessions and explicit destructive merge boundaries.
- [Updating nested USD asset paths](https://forum.aousd.org/t/updating-nested-asset-paths-recommended-workflow/1334):
  version pinning, nested references, resolvers, and version VariantSet trade-offs.
- [User Perspectives on Branching in Computer-Aided Design](https://arxiv.org/html/2307.02583v1):
  qualitative evidence on navigation, branch granularity, and contextual history.
- [Untangling the Timeline](https://arxiv.org/html/2602.09236v1): qualitative
  evidence on version management, continuity, scope, and distribution challenges.
- [GitCAD](https://github.com/Desktop-CNC/GitCAD) and
  [cadvcs](https://github.com/EroPerez/cadvcs): implementation references for
  dependency pinning and representation-specific versioning.
- [Git attributes](https://git-scm.com/docs/gitattributes): binary conversion and
  merge behavior; Git compatibility remains separate from history semantics.
- [Reference OpenUSD SDK](https://github.com/PixarAnimationStudios/OpenUSD) and
  [OpenUSD API documentation](https://openusd.org/dev/apiDocs.html): native USD
  evaluation; an isolated SDK worker is a proposed CAD-GIT architecture choice.
- [egui](https://github.com/emilk/egui) and [wgpu](https://wgpu.rs/): proposed
  native UI and rendering stack, subject to a picking/performance prototype.
- [Rerun Mesh3D](https://docs.rs/rerun/latest/rerun/archetypes/struct.Mesh3D.html),
  [pxr_rs](https://github.com/AndrejOrsula/pxr_rs), and
  [openusd-rs](https://github.com/FloatyMonkey/openusd-rs): alternatives to evaluate,
  without assuming their capabilities or compatibility are equivalent to the SDK.

## 23. Relationship to existing prototype files

`test/source/model.3dm`, `test/source/scene.blend`, and `test/usd/` establish only a
native-export/composition/import smoke test with a 20 mm calibration cube. They
do not establish exact-save capture, automatic identity mapping, repeated sync,
material write-back, conflict reconciliation, or recoverable history. The
prototype's one-way config is superseded by this specification. Existing fixture
files remain unchanged as evidence of the earlier experiment.
