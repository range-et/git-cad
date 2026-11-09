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

CAD-GIT focuses on history, lineage, materials, assembly and artifact management.
Reconstruction is an optional external provider, not a core release requirement.
Issues #1, #3 and #4 preserve provider research findings; future implementation
belongs in the [DualBrep fork](https://github.com/range-et/DualBrep). Issue #2 tracks
the eventual thin CAD-GIT adapter. Core workflow improvements remain in #5–#10.

## #1 — DualBrep can return valid shells without a closed solid

**Status:** Deferred to provider · **Priority:** P1 before that provider accepts
solid results; not a CAD-GIT release blocker.

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

CAD-GIT currently prepares immutable jobs only. The separate
[DualBrep fork](https://github.com/range-et/DualBrep) is intended to become an
independently versioned Docker service. Native CUDA smoke tests passed for selected
candidates; no service image, Docker execution or Apple GPU support is qualified.

**Acceptance:** probe Docker/provider/protocol/device compatibility; submit jobs
on request; support logs, timeout and cancellation; verify result manifests and
record derived artifacts with provenance. Missing or unsupported runtime reports
reconstruction unavailable and does not block ordinary CAD-GIT workflows. Keep
Torch, weights and OCC outside CAD-GIT. Platform-independent protocol does not
imply every host supports the accelerator. No mandatory Mac backend port.
See [service boundary](docs/DUALBREP.md).

## #3 — Reconstructed STEP scale and fidelity are not qualified

**Status:** Deferred to provider · **Priority:** P1 before the provider claims
manufacturing-scale output; not a CAD-GIT release blocker.

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
upstream modes or for CAD-GIT's Windows native adapters.
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
when changing that interface. Do not treat CUDA Windows success as CAD-GIT portability.

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
