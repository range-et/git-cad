# Adversarial architecture and UI/UX review

Reviewed 2026-11-07 by two independent agents. The architecture reviewer ran
throwaway-project failure probes and an isolated Blender process. The UX reviewer
exercised real Qt/VTK windows against temporary projects. The parent implemented
core fixes, integrated adapter/UI fixes, and added failure-injection regressions.
Live native document geometry was not edited by these reviews.

The review found a useful prototype architecture—one shared core behind CLI, GUI
and optional MCP—but weak failure boundaries around file publication, capture
recovery and asynchronous UI work. Those boundaries were the priority for fixes.
This report is a scoped engineering review, not a claim that every possible crash,
filesystem failure, native application version or model type has been certified.

## Architecture findings and disposition

| Finding | Resolution |
| --- | --- |
| Init could overwrite an existing `main/scene.usda` and published config before scaffolding completed. | Refuses conflicting reserved paths, prepares scaffolding first, and publishes config last. Existing native files and Git rules are retained. |
| `captured_at` could create nested paths and an invisible committed record. | Validates timezone-aware ISO timestamps and normalizes UTC before staging. Discovery also recognizes committed legacy nested records. |
| Clock rollback or delayed capture produced incorrect parents and heads. | Uses parent relationships and monotonically increasing commit sequence; ambiguous branch tips are rejected. History offsets walk recorded parents. |
| `entry_layer` could escape the archive despite a successful hash check. | Requires contained paths, inventoried entry layers, matching commit markers and consistent payload inventories. Known material dependencies are verified too. |
| Main's JSON pointer and convenience USD could disagree after publication failure. | JSON pointer is authoritative, projection writes precede pointer publication, immediate failure rolls back the projection, and reopening repairs interrupted projections. Success events follow publication. |
| A crash between capture commit and inbox receipt could duplicate history. | Durable capture identifiers make ingestion idempotent; the inbox restores missing receipts from committed records. |
| Event-log failure after commit was reported as an uncommitted capture. | Preserves committed results and returns an explicit publication warning. |
| Long imports made a live daemon appear stopped and impossible to stop. | Separates liveness from heartbeat freshness; process command and service lock establish ownership. Busy live services remain stoppable. |
| Exports/native handoff used check-then-overwrite and could leave partial files or false lineage. | Shared destination-local staging plus exclusive atomic publication prevents overwrite races. Handoff cleans its own unpublished sidecar on failure; committed artifact IDs are surfaced on partial external publication. |
| Two parts sharing a Blender material could not be restored. | Disposable import USD carries exact per-mesh identity; graph assets are loaded once per revision and assigned independently. Nested graph images are remapped recursively. |
| Reattaching Rhino lost queued exact-save captures. | Pending queues survive reattachment and recover from durable pending markers/staging copies after runtime restart. |
| Switching projects could write a save into two histories or let an old daemon reclaim an app. | One CAD-GIT project owns an application binding. Detach respects ownership; background capture cannot switch another project's binding. |
| A malformed manifest blocked access to unrelated history. | Read-only enumeration isolates and reports unreadable records. Valid records remain inspectable/exportable. Ancestry-changing capture remains blocked rather than guessing past damaged history. |

Original architecture reviewer evidence and remaining adapter limitations are in
[the raw audit report](research/architecture-audit-2026-11-07.json). Entries marked
“Parent-owned fix” there are resolved in the table above; the raw findings are
retained for provenance.

## UI/UX findings and disposition

| Finding | Resolution |
| --- | --- |
| Malformed drafts were silently replaced with an empty list on startup. | Original bytes remain in place, a separate recovery copy is attempted, and a visible warning explains recovery. |
| Failed snapshot loads became permanently empty cached tabs. | Explicit loading/error/ready states, retry on reopening the same version, and context-sensitive action enablement. |
| Closing tabs/windows during work caused late callbacks into destroyed renderers. | Closed-widget guards suppress late UI work; callback exceptions use the normal error path. |
| Identical prim paths from different snapshots selected multiple unrelated preview pieces. | Each draft piece has a unique preview namespace, with a populated object tree. |
| Controls clipped when sidebars/window narrowed. | Overflow-capable view toolbars retain access to modes and framing actions; existing splitters remain draggable. |
| STL/Main actions appeared inside the draft tray but operated on another file. | Actions now live beside the active saved file with explicit target labels. |
| Repeated Save clicks could create duplicate assemblies. | Save is disabled while publication is in progress, with a duplicate-operation guard. |
| Graph required a mouse and search could not navigate matches. | Up/Down navigation, Enter to open, match counts, jump-to-match and visible ancestry warnings. |
| Draft pieces accumulated without an obvious reset. | Explicit New assembly action with a clear-draft confirmation; saved history is retained. |
| Imported files displayed invented software filenames. | Uses known import/native paths or the actual record label. |

The existing shaded/rendered/wireframe/X-ray modes, mesh-edge selection feedback,
background-click deselection, no default ground plane, resizeable panes and saved
layout remain in place. Native shader overrides are restored by their application;
the manager's inspection preview does not evaluate native renderer graphs.

## Verification

- **57 core tests passed**, including adapter recovery and publication fault
  injection. Tests cover invalid timestamps, clock rollback, archive escapes,
  commit markers, corrupt material dependencies, main projection/pointer failures,
  missing receipts, existing outputs, competing publications, interrupted copying,
  service liveness/ownership, and old-format compatibility.
- `tests/integration/ui_smoke.py` passed: four viewport modes, actual divider
  drags, graph clicks, mesh/background clicks, camera drags, assembly composition
  and persisted layout.
- `tests/integration/ui_robustness.py` passed: failed-load retry, independent preview
  selection, closed-tab/window callbacks, callback exceptions, keyboard/search,
  preserved malformed drafts, duplicate-save prevention and actual UI assembly
  export/lineage publication.
- `tests/integration/cli_smoke.py` passed in an unrelated existing repo folder:
  init, ingestion, composition, main selection, STL/USD exports, native Rhino file
  creation with lineage, and verification. Existing files were preserved.
- Isolated Blender 5.2.3 probe passed: two meshes share one restored native
  material datablock containing the four-node procedural shader graph.

## Remaining work

The highest-value next improvements are a persistent per-app capture/status/retry
panel; a guided historical-branch handoff; document IDs distinct from application
lanes; stale-preview indicators; graph/index scaling for very long histories; and
local-timezone/screen-reader polish. These are tracked in
[future features and open questions](FUTURE_FEATURES_AND_OPEN_QUESTIONS.md).

Native NURBS reconstruction remains explicitly deferred. The general plugin
registry and per-face native material restoration are still unsupported. Failed
native captures and interrupted handoff staging are retained for diagnosis; Rhino
pending-copy export requires an attached runtime to recover.

## Repository rename

The working repository is now `/Users/r2d2/Desktop/git-cad`, with origin
`https://github.com/range-et/git-cad.git`. An old-name filesystem symlink remains
for open native documents and this chat's original working directory. It points
to the same repository and is not a second checkout. Generated local launcher/MCP
paths were updated; immutable history provenance was not rewritten.
