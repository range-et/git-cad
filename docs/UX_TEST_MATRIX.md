# UX workflow coverage matrix

Defined 2026-11-09 from the current UI, CLI/MCP interfaces and existing tests by an
independent UX reviewer. This is a **finite model of supported actions and states**,
not proof of every possible repeated user sequence, model, platform or native app.

**Execution status:** mappings below describe source coverage. Final gate execution
and its source fingerprint must be recorded separately by the main agent. A test
existing, or an earlier development run passing, does not certify the final tree.

## Coverage language

- **Mapped:** a concrete automated assertion covers the stated behavior.
- **Partial:** only some actions/states are covered, or core behavior is checked
  without its complete UI workflow. The remaining obligation is named.
- **Gap:** no mapped automated coverage found; not a defect claim.
- **Native/manual:** requires the stated live environment or human/visual check;
  never implied by handler mocks or a passing core test.

Stable case IDs belong to this catalog. Generated test-case counts are separate:
one catalog row can map to many cases and one sequence can cover several rows.
All tests use disposable projects; immutable archive/source hashes, revision
pinning, deliberate main selection, non-overwrite and actionable failures are
cross-cutting oracles. Dialog suites script OS file-picker responses; they do not
certify native file-dialog accessibility. Most GUI suites mix real Qt widgets with
handler calls, rather than driving every step through mouse/keyboard input.

## Suite key

Paths below are relative to the repository root.

| Key | Test source | Scope |
| --- | --- | --- |
| UI | [ui_smoke.py](../tests/integration/ui_smoke.py) | Main geometry journey, actual graph/viewport/splitter input |
| UR | [ui_robustness.py](../tests/integration/ui_robustness.py) | Retry, late callbacks, stale previews, save guard and recovery |
| ML | [material_library_smoke.py](../tests/integration/material_library_smoke.py) | Browser state, material assignment, editor fidelity and partial imports |
| TP | [texture_preview_smoke.py](../tests/integration/texture_preview_smoke.py) | Pixel assertions, UVs, opacity and ORM maps |
| VR | [viewport_responsiveness.py](../tests/integration/viewport_responsiveness.py) | CPU workers, batched upload, heartbeats, close during upload |
| BP | [brep_preparation_smoke.py](../tests/integration/brep_preparation_smoke.py) | Optional preparation only; no reconstruction |
| WC | [workflow_combinations.py](../tests/integration/workflow_combinations.py) | 64 mode/edge/selection transition cases plus 14 draft/tab/invariant cases |
| DW | [dialog_workflows.py](../tests/integration/dialog_workflows.py) | Cancellation, settings, material dialogs and kind/query combinations |
| MCP | [mcp_workflow_smoke.py](../tests/integration/mcp_workflow_smoke.py) | Real stdio initialization/discovery and all 17 exposed tools; 15 workflow groups |
| CLI | [cli_smoke.py](../tests/integration/cli_smoke.py) | Init in existing folder, ingest/compose/main/export/handoff/verify |

WC's explicit product is **4 start modes × 4 destination modes × 2 edge states ×
2 selection states (none/one mesh) = 64**. Every generated case includes A→B→A
switching and checks actor properties, controls and selection. Group selection is
covered separately for parent/child deduplication, **not** crossed through all
64 cases. Long action sequences and all combinations of data fixtures remain
outside that exhaustive-within-domain statement.

## Project lifecycle and compatibility

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| PR-01 | Init in existing folder → source files/Git rules preserved | Mapped: CLI; `test_review_round2.py::test_init_preserves_exact_original_git_rule_bytes`. |
| PR-02 | Init conflicting paths or inject publication failure → no falsely initialized project | Mapped: `test_init_preflights_user_paths_before_publication`, `test_failed_init_restores_git_rules_and_existing_native_files`. |
| PR-03 | Open genuinely empty project → empty graph/tabs/library and disabled actions | Mapped: DW `empty-project-and-cross-project-isolation` checks empty tabs/draft/library and disabled Add/Save; WC closes all tabs/reopens. |
| PR-04 | Close/reopen with draft, chosen workspace and resized panes → scoped state restored | Partial: UI checks persisted splitter state; full reopen/draft/workspace journey missing. |
| PR-05 | Open corrupt draft → original bytes preserved, visible recovery, good history usable | Mapped: UR recovery assertions. |
| PR-06 | Open old-format records and compose → originals and optional fields preserved | Mapped: `test_compatibility.py::test_original_v1_records_open_without_rewriting_and_can_be_reused`; additive-field regressions. |
| PR-07 | External required-schema change while app open → reject mutation safely | Partial: `test_project_mutations_recheck_compatibility_after_external_update`; GUI message path untested. |
| PR-08 | Switch between independent projects → no draft/library/layout leakage | Partial: DW opens two projects and checks second-project draft/library emptiness and original main/draft preservation; layout isolation/reopen not covered. |

## History and branches

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| HI-01 | Click/Enter history node, reopen same node → correct record, no duplicate tab | Partial: UI click and UR Enter; explicit repeat-open tab-count assertion missing. |
| HI-02 | Search match/no-match/clear; navigate forward/backward → ancestry remains visible | Mapped: UR graph/search assertions; keyboard plus handler navigation. |
| HI-03 | Branch historical snapshot, activate, capture → pinned parent, main unchanged | Partial: `test_history.py::test_branch_parent_is_pinned_without_moving_main`; DW cancellation only, GUI accepted branch not covered. |
| HI-04 | Name version: cancel/blank/duplicate/accept → immutable bookmark or no mutation | Partial: DW cancellation and `test_history_graph.py::test_named_versions_are_immutable_bookmarks_and_empty_branches_are_visible`; GUI invalid/accepted naming missing. |
| HI-05 | Follow snapshot/assembly lineage donor link → exact ancestor opens | Gap: actual lineage dialog navigation. |
| HI-06 | Refresh while capture arrives and tab selected → context preserved | Gap: asynchronous history-refresh transition. |
| HI-07 | Corrupt one record → other history usable, warning, no invented ancestry | Mapped: UR; `test_robustness.py::test_bad_record_is_isolated_for_reading_but_cannot_poison_new_ancestry`. |
| HI-08 | Context-menu action on B while A active → intended clicked-node target | Gap: Copy ID/branch/Set Main context-menu target matrix. |

## Viewport and tabs

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| VP-01 | All ordered mode pairs → correct representation and source data unchanged | Mapped: WC 16 ordered mode pairs, actor representation/SSAO; immutable source bytes. |
| VP-02 | Mode × edges × selection → correct highlighting/overlay | Partial: WC exhausts none/mesh selection; group selection crossed with modes remains missing. |
| VP-03 | Pick mesh, click background, drag orbit → click clears, orbit preserves selection | Mapped: actual Qt mouse input in UI. |
| VP-04 | Select parent and child, Add → no duplicated subtree | Mapped: WC `DRAFT-parent-child-deduplicated`. |
| VP-05 | A→B→A with distinct mode/edges/selection → toolbar/tree/actors agree with tab | Mapped: WC includes this in all 64 generated cases. |
| VP-06 | Reorder, close active/nonactive/last, reopen → coherent current inspector/actions | Mapped: WC tab lifecycle and UR last-tab warning cleanup; not every arbitrary tab count/order. |
| VP-07 | Change mode/edges/frame during queued/loading states → correct completion and action gates | Partial: earlier independent UX probes; complete durable loading-state product missing. |
| VP-08 | Large load, close during upload, failure/retry → heartbeats and no late renderer access | Mapped: VR; UR load retry/closed callbacks. |

## Assembly lifecycle

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| AS-01 | Add same prim path from A and B, preview → distinct pieces/selection | Mapped: UR unique preview namespaces and selected actor count. |
| AS-02 | Add identical selection twice → independent movable pieces, same donor | Mapped: WC duplicate selection, unique preview paths and first-piece movement. |
| AS-03 | Move: cancel/text/NaN/Inf/wrong arity/valid meters → only valid input changes draft/disk | Mapped: WC five invalid/cancel cases plus valid movement. |
| AS-04 | Edit draft after preview, refresh → old marked stale, new placement/material matches | Mapped: WC move/clear and UR material-change previews; every add/remove permutation not exhausted. |
| AS-05 | Remove first/middle/last → correct survivors and immutable source | Partial: WC removes sole/second row and verifies survivor; explicit middle of 3+ case missing. |
| AS-06 | New assembly Cancel/Yes → preserve or clear draft only | Mapped: WC clear cancellation/confirmation and immutable history. |
| AS-07 | Save cancel/existing/success/repeated click → no overwrite, one accepted publication | Mapped: DW cancellation/existing output; UR actual success/double-save guard. Existing-sidecar-only UI variant remains core/preflight coverage. |
| AS-08 | Save then edit draft/switch/close source → frozen recipe saved | Mapped: DW `save-freezes-recipe-across-edit-and-close` blocks worker, edits draft and closes source, then checks saved recipe versus surviving current draft. |

## Export, main and artifacts

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| EX-01 | Set Main from saved assembly; reject source/draft → intentional main only | Mapped: DW accepted GUI Set Main; CLI/MCP main workflow; WC snapshot/draft gates. |
| EX-02 | STL whole/subtree/multiple selection → correct scope or clear unsupported-selection rejection | Partial: CLI/MCP whole-file and core export; complete UI selection-scope matrix missing. |
| EX-03 | Cancel picker or reject STL confirmation → no artifact/history writes | Mapped: DW picker cancellation plus `stl-confirmation-no`. |
| EX-04 | Existing output/race/disk failure → preserve original, no partial publication | Mapped core: `test_existing_stl_output_is_rejected_before_creating_artifacts`, `test_publication_race_never_overwrites_competing_file`, `test_failed_copy_leaves_no_partial_output`; MCP overwrite; UI feedback partial. |
| EX-05 | Start export then switch/close tab → frozen source/subtree | Mapped: DW `stl-freezes-source-across-tab-close` blocks worker and checks worker input ID/subtree and output existence. |
| EX-06 | Open/nonmanifold/empty/subdivision mesh export → rejection or honest supported-base disclosure | Partial: core topology tests including `test_stl_rejects_meshes_with_no_exportable_faces`; GUI disclosure matrix missing. |
| EX-07 | Export USD, re-ingest, compose → geometry/material/dependency lineage preserved | Partial: CLI and `test_library.py::test_resolved_capture_tags_survive_export_and_reingestion`; combined GUI journey missing. |
| EX-08 | Commit assembly then fail external file/sidecar export → committed ID reported accurately | Partial: DW `save-partial-publication-surfaces-committed-id` injects export failure after commit and checks reported ID, no output and unchanged main; sidecar-only failure and explicit retry remain missing. |

## Material and asset library

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| LI-01 | Every kind × empty/matching/no-match query; switch revision → coherent selection/actions | Partial: DW filter/query product, ML selection clearing; explicit historical revision navigation missing. |
| LI-02 | Import one/multiple, cancel provenance, partially fail → preserve originals, identify successful IDs | Partial: ML partial batch, MCP document import; GUI import success/cancel matrix missing. |
| LI-03 | Folder import with generated archives/runtime dirs/symlinks/empty/>200 files → skip/reject correctly | Gap: UI folder boundary matrix. |
| LI-04 | Create material; invalid fields/duplicates; cancel/accept → no invalid revision | Partial: DW actual Create/cancel, ML duplicate property/losslessness, core validation; complete invalid-dialog field product missing. |
| LI-05 | Edit material while another revision advances → stale write rejected, no overwrite | Partial: MCP real-protocol stale revision rejection and core test; stale open-editor UI recovery missing. |
| LI-06 | Revise/derive/recombine with pinned donors; cancel → identities and parents correct | Mapped: DW real dialogs create/revise/derive/recombine and all four cancellations; core facet-value checks and MCP recombination. Non-material derivation GUI remains untested. |
| LI-07 | Follow history/parent/dependency links, inspect Used by → exact historical revision | Partial: MCP library history/revision/used-by; GUI link navigation missing. |
| LI-08 | Corrupt selected asset after valid selection → mutation actions disabled, no stale context | Partial: core integrity tests; GUI selection-to-corruption transition missing. |

## Material/geometry combinations and appearance

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| MA-01 | Choose library material then Add geometry → only new piece uses chosen revision | Mapped: ML material selection switches workspace and preserves existing pieces. |
| MA-02 | Revise chosen material then add → old piece pinned, explicit revision controls new piece | Gap: combined UI revision/add sequence; core pinning already covered. |
| MA-03 | Preview override, save/reopen → authored portable values/maps retained | Partial: UR preview values; core `test_library_texture_preview_matches_saved_assembly`; full GUI save/reopen missing. |
| MA-04 | Packaged/indexed UV images, shaded→rendered→shaded → expected pixels, unchanged source | Mapped: TP pixel/UV/material-map checks; WC source immutable byte check. |
| MA-05 | Bad texture/UV, select mesh, open warnings → usable geometry and complete diagnostics | Mapped: UR persistent preview notes; core `test_bad_texture_or_uv_is_visible_without_losing_geometry`. |
| MA-06 | Resize inspector with extreme image aspect ratios → fit/no overlap/nonzero thumbnail | Partial: ML skinny images and resize fit; all portrait/landscape sizes and visual readability not exhausted. |
| MA-07 | Physical-only/native-only/texture-only material → honest preview label and no inferred properties | Partial: ML texture-only checks; full representation/action-state matrix missing. |
| MA-08 | Blender graph roundtrip with shared graph/nested images → intended native appearance/identity | Native/manual: historical isolated Blender evidence and mocked adapter test; no new live-native qualification implied. |

## Settings, external applications and failure boundaries

| ID | Actions → expected invariant | Source coverage and remaining scope |
| --- | --- | --- |
| SY-01 | Invalid settings JSON/shape/target, cancel → dialog stays open and config unchanged | Mapped: DW three invalid-target cases and Cancel. |
| SY-02 | Save target → menu updates, unknown config fields retained | Partial: DW accepted target/menu; compatibility core test covers fields; combined UI preservation/order case missing. |
| SY-03 | Handoff cancel/existing/launch failure/tab switch → correct new file and lineage | Partial: DW Cancel; `test_handoff.py` and publication-race tests; UI launch-failure/context-switch paths missing. |
| SY-04 | Watch twice, reconnect, rapid native saves → no duplicate hooks, exact-save ordering | Native/manual: adapter mock tests cover ownership/recovery/order; no fresh live save test implied. |
| SY-05 | Close during load/save/library import, reopen → no stale callbacks and coherent durable records | Partial: UR generic worker/window close and VR upload close; pending library/save publication plus reopen missing. |
| SY-06 | Minimum window, splitter extremes, light/dark themes → controls reachable/readable | Partial: UI splitter drag, UR overflow, WC minimum-size state; visual/theme/accessibility sweep remains manual. |
| SY-07 | Draft/target write denied, restore access and retry → visible failure, in-memory draft retained | Partial: core publication injection; GUI `update_tray` persistence-failure/retry missing. |
| SY-08 | Optional B-rep preparation Cancel/failure/runtime unavailable → honest no-STEP result and pinned source | Mapped: BP and `test_brep.py`. Reconstruction, Docker and MPS are outside core scope. |

## MCP protocol obligations

MCP adds 15 named workflow groups outside the 64 UX catalog rows: initialize;
discover tools; status/filtered history; inspect; invalid reference/schema recovery;
library browse/history/search; asset import; material revision/stale rejection;
recombine; USD ingest/assembly lineage; main/usage lookup; print export/overwrite;
artifact-ID corruption detection/recovery; failed assembly recovery; original archive immutability. All 17 expected tool
names must actually be called. This verifies real stdio transport, not merely an
import of the server module. It does not cover every argument or native app.

The print export group now verifies the returned artifact ID through MCP, corrupts
only its disposable archived STL, requires a failed integrity result, restores the
bytes and requires success. Print IDs remain separate from scene resolution.
This is source-mapped pending final execution evidence.

## Prioritized remaining test obligations

1. **SY-03:** extend the new frozen save/STL checks to native handoff context,
   launch failure and late completion. Do not launch user applications for mocks.
2. **EX-08 / SY-07:** extend the new post-commit export failure check to sidecar
   failure/retry and draft persistence failure; preserve in-memory edits.
3. **LI-05 / LI-08:** stale editor and corrupt selection after a good selection;
   avoid silently overwriting revisions or leaving stale enabled actions.
4. **PR-04 / PR-08 / SY-05:** reopen persistence and multi-project state isolation.
5. **LI-03 / LI-07 / MA-02:** bounded folder import, graphical lineage navigation,
   and historical material revision combined with geometry assembly.
6. **Native/manual:** live Rhino/Blender save roundtrips, OS file dialogs, screen
   reader/focus order and visual theme/readability. Record environment and evidence,
   or explicitly mark not run. Do not substitute mocked callbacks for these gates.

Before claiming completion, reconcile each row with the actual final report:
passed, failed, partial or not run; include command/test name and reviewed source
fingerprint. Unmapped rows remain open coverage gaps, not blanket release blockers
or requests for new product features. New proven defects belong in
[issues.md](../issues.md); implemented test capabilities belong in
[features.md](../features.md). Follow [build gates](BUILD_GATES.md).
