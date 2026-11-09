# Issues and planned work

Canonical list of open bugs, investigations, ideas and deferred improvements.
Last reviewed: **2026-11-09**. Implemented capabilities and completed work belong
in [features.md](features.md); detailed experiments and reviews belong in `docs/`.
An entry is not a delivery commitment. Keep IDs stable; never recycle them.

Statuses: **Investigating**, **Planned**, **Deferred**, **Watch**.
Priorities follow [build gates](docs/BUILD_GATES.md); ideas without a reproduced
defect use **Roadmap**, not a fabricated bug severity. On completion, move the
entry's outcome and evidence to features.md History, retaining its ID there.

## Scope and priorities

Git CAD focuses on history, lineage, materials, assembly and artifact management.
Reconstruction is an optional external provider, not a core release requirement.
Issues #1, #3 and #4 preserve provider research findings; future implementation
belongs in the [DualBrep fork](https://github.com/range-et/DualBrep). Issue #2 tracks
the eventual thin Git CAD adapter. Core workflow improvements remain in #5–#10.

## #1 — DualBrep can return valid shells without a closed solid

**Status:** Deferred to provider · **Priority:** P1 before that provider accepts
solid results; not a Git CAD release blocker.

On C110P, upstream `9707b4b4e531943f38e83092ff7ad833cc60b2cb`, sample
`00013293`, resolution 256, rotation 3 produced 53 faces, six shells, zero solids.
A general BRepCheck passed, so that check alone cannot establish reconstruction
success. Sample `00030157` at the same settings produced one valid solid, one
shell and 25 faces after independent STEP re-import. CUDA inference works.

**Finding:** rotations 0 and 7 on the same AE output both produced closed valid
solids with 53 faces and zero free boundary edges. Rotation 3 failed to trim faces
49 and 50, then failed sewing and hole filling. This is candidate-sensitive;
the exact trim failure mechanism remains unisolated. Recomputed edge gaps of
0.0105–0.0136 normalized units remain material for precision use; see #3.
**Next:** implement bounded candidate search and independent output/fidelity
validation in the future backend. Preserve failures; never hide them by increasing
tolerances solely to obtain a solid.
**Acceptance:** report explicit solid count, closure, validity, volume and source
comparison; explain partial/failed results and never publish them as a successful
solid. See [CUDA investigation](docs/DUALBREP_CUDA_INVESTIGATION.md).

## #2 — Optional Docker reconstruction-provider adapter

**Status:** Deferred · **Priority:** Roadmap.

Git CAD currently prepares immutable jobs only. The separate
[DualBrep fork](https://github.com/range-et/DualBrep) is intended to become an
independently versioned Docker service. Native CUDA smoke tests passed for selected
candidates; no service image, Docker execution or Apple GPU support is qualified.

**Acceptance:** probe Docker/provider/protocol/device compatibility; submit jobs
on request; support logs, timeout and cancellation; verify result manifests and
record derived artifacts with provenance. Missing or unsupported runtime reports
reconstruction unavailable and does not block ordinary Git CAD workflows. Keep
Torch, weights and OCC outside Git CAD. Platform-independent protocol does not
imply every host supports the accelerator. No mandatory Mac backend port.
See [service boundary](docs/DUALBREP.md).

## #3 — Reconstructed STEP scale and fidelity are not qualified

**Status:** Deferred to provider · **Priority:** P1 before the provider claims
manufacturing-scale output; not a Git CAD release blocker.

Upstream outputs normalized coordinates. Job preparation records an inverse
transform, but runtime application and manufacturing-unit STEP re-import are not
implemented. A sealed solid need not closely match the input.
**Acceptance:** apply recorded inverse normalization and declared STEP units;
check re-imported bounds/volume and measured surface deviation against the source;
retain per-part provenance, report tolerance and require review of approximations.

## #4 — Windows DualBrep dependency and DLL compatibility

**Status:** Deferred to provider · **Priority:** P2 for the optional backend.

C110P has no matching libigl wheel in the tested Python environment and no C++
compiler; the default point-cloud smoke path ran without libigl. Importing
`lightning.pytorch` before OpenCASCADE STEP support reproduced a DLL failure.
Separate pipeline processes worked. This does not establish support for all
upstream modes or for Git CAD's Windows native adapters.
**Acceptance:** reproducible platform dependencies and fresh-process import tests;
run reconstruction/OCC stages independently or demonstrate a verified alternative.
See [CUDA evidence](docs/DUALBREP_CUDA_INVESTIGATION.md).

## #5 — Native capture status and historical branching workflow

**Status:** Planned · **Priority:** Roadmap.

Add persistent per-app binding/branch/latest-save/queue/failure/retry/Stop controls,
a guided branch-from-history handoff, and stable native document IDs distinct
from software lanes. Make assigning future saves visibly different from opening
old contents. Add a structured application-target editor and stale-draft preview
indicators. Acceptance: a user can identify the capture destination, recover a
failed save, and resume an old revision without ambiguity or overwriting sources.

## #6 — Large scenes and long histories

**Status:** Watch / planned · **Priority:** Roadmap.

Background CPU preparation and batched actors are implemented; final GPU upload,
individual actor operations and rendered frames can still block interaction.
Investigate LOD/streaming, history-index caching and graph virtualization against
measured workloads. Acceptance: record event-loop gaps, memory, scene size and
hardware; avoid universal responsiveness claims. See [loading evidence](docs/VIEWPORT_LOADING.md).

## #7 — Native editability and optional native archives

**Status:** Deferred · **Priority:** Roadmap.

USD mesh round-trips cannot recover NURBS control points, constraints or feature
history. Explore optional native snapshots, exact restoration of unchanged parts,
and explicit approximate reconstruction. A DualBrep result is not recovery of
original parametric history. See the [design question](docs/FUTURE_FEATURES_AND_OPEN_QUESTIONS.md).

## #8 — Materials, renderer fidelity and engineering representations

**Status:** Planned · **Priority:** Roadmap.

Extend the existing project library with per-face native graph restoration,
explicit override-fidelity labels, additional solver/material representations
(Substance, Ansys, OpenFOAM/FreeFEM), and optional provider-assisted asset import.
Normal/displacement maps, UDIMs and arbitrary Cycles graphs are not evaluated by
the manager preview. Keep native graphs, portable appearance and sourced physical
properties separate and revision-pinned. Provider integration must retain asset
provenance/licenses; physical data needs units and sources, not invented defaults.

## #9 — Accessibility, layout and local timestamps

**Status:** Planned · **Priority:** Roadmap.

Review dense minimum-size layouts, expand screen-reader support and display
history times in the user's timezone while retaining durable UTC timestamps.
Acceptance: keyboard and narrow-window workflows remain usable; dates are unambiguous.

## #10 — Extensible adapters and recovery tooling

**Status:** Planned · **Priority:** Roadmap.

Formalize a third-party plugin contract/registry beyond bundled hooks and external
commands. Add explicit cache/staging cleanup and recovery tools that preserve
pending captures and diagnostics. Qualify each supported native app/OS separately;
the current reference service uses POSIX locking. Add MCP protocol smoke coverage
when changing that interface. Do not treat CUDA Windows success as Git CAD portability.

## #11 — Collaboration and deeper merge semantics

**Status:** Deferred · **Priority:** Roadmap.

Local-first snapshot bookkeeping remains the scope. Multi-user collaboration,
automatic geometry merging and per-vertex history are not current guarantees.
Revisit only with explicit product scope and a compatible additive data contract.

## #12 — Complete remaining UX/native action-state coverage

**Status:** Planned · **Priority:** Roadmap / test coverage.

The [64-row UX catalog](docs/UX_TEST_MATRIX.md) maps existing tests, finite generated
combinations and untested transitions. Automated passing cases do not close partial
rows. Remaining work includes live save-hook/native renderer round trips, OS file
dialogs, keyboard/accessibility/visual sweeps, and explicitly listed GUI transitions
not covered by core tests. Acceptance: each row has executable evidence or a named
manual procedure with a recorded result; no blanket exhaustive-coverage claim.

## #13 — Broaden layered verification beyond the compatibility boundary

**Status:** Planned · **Priority:** Roadmap / test coverage.

The scoped static/property/snapshot/mutation delivery is recorded in
[features History](features.md) and the [verification guide](docs/TEST_VERIFICATION.md).
This is remaining coverage work, not a reproduced product defect.
**Next:** expand strict typing incrementally; add generated real-project operation
sequences for immutable history, failure/recovery and pinned dependencies; extend
mutation targets and reviewed serialization snapshots to storage/library boundaries.
**Acceptance:** each added boundary has a bounded reproducible domain, independent
oracle, measured mutation outcomes and explicit limits. Keep native/manual gaps
under #12; do not represent this expansion as already delivered.

## #16 — Entire-project line and mutation verification

**Status:** Investigating · **Priority:** Roadmap / test quality.

User requests 100% production Python line coverage and mutation verification for
the entire project, starting with storage/history loss, links and failed saves.
**Next:** inventory every production module, measure missing lines and mutants,
add independent failure/invariant tests, fix reproduced defects, and audit every
survivor without counting equivalent mutations or timeouts as kills.
**Acceptance:** reproducible whole-source coverage and mutation reports, explicit
native/environment boundaries, no untested lines hidden by exclusions, and tests
that demonstrably reject destructive writes, broken links and false save success.
Issue #13 tracks earlier incremental verification scope; this requested campaign
is authoritative for the whole-project target.

## #17 — Main selection reports failure after publishing a new pointer

**Status:** Implemented; final review reconciliation pending · **Priority:** P1.

Independent temporary-project probe: fail the second main-directory fsync during
set_main. The call raises, current.json names the new assembly, and scene.usda is
rolled back to the old assembly. **Next:** test pre/post-publication failures and
make the returned outcome agree with the authoritative pointer. **Acceptance:**
failed prepublication selection preserves old state; published selection returns
its exact ID with a durability warning and a matching/recoverable projection.

## #18 — Library verification ignores pinned parent links

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Move the previous revision archive out of a temporary library after a real second
revision is saved: verify(second) still returns ok=True. **Next:** verify parents
as well as dependencies and test missing/corrupt/cyclic links. **Acceptance:** all
pinned lineage links are checked with role-qualified errors and immutable payloads.

## #19 — Library validation failure leaves stale enabled controls

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Independent real-Qt probe: select a valid material, inject an OSError from verify,
and reselect. _valid_selection becomes false but Use/Revise remain enabled;
use_material does not check validity. **Next:** fail closed and test recovery.
**Acceptance:** failed validation disables selection actions, emits no material
assignment, and revalidation restores usable controls without modifying history.

## #20 — Configuration events can claim changes that failed to save

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Inject a prepublication cadgit.json write failure in branch/name_version: the call
raises and config is unchanged, but a branch_selected/version_named event remains.
**Next:** publish config before its success event and classify postpublication
sync/event failures. **Acceptance:** failed saves leave no success event; published
changes return explicit outcome/warnings and keep extension fields intact.

## #21 — Native material provenance can reference an uncommitted capture

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Fail snapshot commit after native material commit, then retry: reused material's
snapshot_id names the failed attempt, which never existed in committed history.
**Next:** record attempt provenance without asserting future snapshot existence;
preserve existing manifests. **Acceptance:** new material manifests distinguish
capture attempts from committed snapshot links; retries pin correct material IDs.

## #22 — Record sync failure reports an already published save as failed

**Status:** Implemented; final review reconciliation pending · **Priority:** P1.

Inject fsync_dir failure after record-directory rename: library import raises but
the revision is present and verifies. **Next:** return exact committed ID with an
explicit durability warning after the publication point. **Acceptance:** before
publication failures preserve originals; after publication results expose committed
state and retries do not silently invent a replacement for a failed-save report.

## #23 — GUI completion handlers hide publication durability warnings

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Real Qt library probe: a committed material returns a directory-sync warning but
changed_record shows only success. Config, context-main, ingestion, STL and B-rep
handlers also discard warnings; assembly event failure can overwrite one.
**Next:** retain successful IDs and show accumulated warnings. **Acceptance:**
postpublication faults remain visibly distinct from uncommitted saves across
completion/recovery paths, without duplicate retries or overwritten history.

## #24 — Assembly manifest can disagree with its hashed recipe

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Change a real assembly manifest's selection to another existing snapshot while
leaving recipe.json intact: verification previously returned ok=True. **Next:**
compare known recipe fields when the recipe is inventoried, while preserving
legacy absence and unrelated additive fields. **Acceptance:** ID/transform/
material/unknown-selection-data mismatches fail without rewriting either file.

## #25 — Native handoff removes lineage after a published-file sync failure

**Status:** Implemented; final review reconciliation pending · **Priority:** P1.

Independent temporary-project probe fails destination-directory sync after the
native output hard link. The output exists but create_native removes its lineage
sidecar and raises. **Next:** tag publication errors with their exact destination,
preserve sidecars once output exists, and test sidecar/output/event failure stages.
**Acceptance:** returned publication warnings retain exact source lineage and
existing output bytes; prepublication failures leave no orphan handoff files.

## #27 — Ingestion succeeds with already corrupt parent history

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Corrupt a real saved snapshot payload then ingest a fresh valid source on its
branch: the returned child reports success but immediately fails verification.
**Next:** validate branch tip/base before publication and reject damaged duplicate
capture IDs without creating replacement history. **Acceptance:** failed lineage
validation preserves the incoming source and existing records, emits no success
event, and publishes no child linked to known damaged history.

## #28 — Native image sidecars silently omit missing dependencies

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

A real capture with a declared image path that no longer exists succeeds and
archives an empty image map. Regression initially failed because no error was
raised. **Next:** reject missing declared inputs before committing the material;
retain the incoming source. **Acceptance:** all declared image bytes are archived
or capture fails visibly; later archive loss fails verification.

## #29 — Corrupt branch config permits a cross-source save parent

**Status:** Implemented; final review reconciliation pending · **Priority:** P2.

Independent probe changes a real Rhino branch base to an existing Blender snapshot;
Rhino ingestion and verification both succeed. **Next:** enforce same-source
snapshot parents at ingest and verify, preserving cross-source imported_from.
**Acceptance:** invalid save relationships fail without altering existing history;
valid explicit imported provenance remains accepted.

## #30 — Receipt recovery deletes frozen native input despite archive corruption

**Status:** Implemented; final review reconciliation pending · **Priority:** P1.

Real inbox capture committed before receipt, then its archive payload is damaged.
process_inbox previously wrote a success receipt and deleted native_capture.3dm.
Regression reproduced FileNotFoundError on the preserved-source assertion.
**Next:** require healthy committed history before receipt recovery or deletion,
verify retry behavior and independently audit. **Acceptance:** corrupt recovered
captures retain native/USD inputs, publish no success receipt and report an error.

## #39 — Intermittent GUI robustness failure remains unisolated

**Status:** Watch · **Priority:** P2 verification gap.

Full gate `20261109T221931.509389Z` exited1 in ui_robustness with only a font
message; its sys.excepthook stored exceptions without printing them. **Next:**
traceback reporting is fixed; standalone recheck and full gate
`20261109T222731.086473Z` passed. Retain the watch entry and investigate any
recurrence using its now-visible traceback; the original assertion is unisolated. **Acceptance:** failures retain actionable
tracebacks, and the real GUI workflow passes with its relevant regression.
