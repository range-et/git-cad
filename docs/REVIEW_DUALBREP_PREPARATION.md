# Review: optional DualBrep input preparation

Scope: the user chose preparing jobs now and configuring a reconstruction runtime
later. Additional investigation covers optional CUDA gating and an Apple Silicon
port. No inference, STEP result, NURBS recovery or MPS execution is claimed.
The implementation contract and primary-source research are in [DUALBREP.md](DUALBREP.md).

Independent architecture/UX scoping preceded implementation. The same reviewers
audited the result, with an independent QA reviewer checking CLI/artifact/runtime
failure paths. Reviews were read-only; probes used temporary projects.

| Priority | Finding | Resolution / recheck |
| --- | --- | --- |
| P1 | Vertex-connected component detection joined solids that touch only at a point; upstream could then discard one body. | Match shared-edge face adjacency, including nonmanifold edge handling. Independent separated/vertex-touching/shared-edge probes retain two bodies; regression added. |
| P1 | A committed job directory replaced by an external symlink was still listed and verified. | Reject job-directory and metadata symlinks and enforce collection containment. Independent escape probe rejected. |
| P2 | Non-object request JSON raised an uncaught exception. | Validate shape and return structured verification errors; regression added. |
| P2 | Pinned HEAD could hide modified upstream source in readiness diagnostics. | Reject tracked modifications in CUDA preflight; independent simulated-device probe passes. |
| P2 | VTK PLY reading downcast double positions used for normalization. | Custom float64 mesh writer; derive normalization from the exact float64 values written. Binary payload regression and upstream Trimesh 4.11.0 readback preserve a 2 mm part at a 1,000 km offset. |
| P2 | Many selected paths made preparation buttons offscreen; first fix clipped explanation. | Scrollable bounded paths and minimum-height wrapped explanation. Independent 151-selection screenshot rechecked; durable UI regression. |

All reported findings were fixed and independently rechecked. No proven P0/P1
remains in the reviewed preparation-only scope. Raw UX and QA reports are retained
in `docs/research/dualbrep-*`.

## Evidence

- Eight focused B-rep tests pass: units/inverse normalization, explicit component
  splitting, cancellation, corruption, collection ownership/symlinks, optional
  runtime state and far-origin precision.
- Actual CLI init/ingest/prepare/list/show/verify workflow passed in a temporary
  project; no STEP was produced.
- GUI checks cover frozen version/selection, background preparation, closing the
  source tab, unchanged source hashes, no-STEP success, cancellation, failure and
  a large selection dialog. The reusable runner includes preparation UI checks.
- A lightweight temporary environment using upstream's Trimesh 4.11.0 parsed the
  generated double PLY and reproduced the recorded center/scale correctly.
- Final full automated gates are recorded by
  `uv run python scripts/check.py --build --ui` under ignored `build/qa/` with a
  source fingerprint. Earlier viewport/gate changes remain in this working tree.

## Explicitly pending

CUDA model/checkpoint inference, restored STEP precision, STEP/Rhino reopening,
checkpoint provenance/hash qualification and a Metal port are pending. Hardware
availability is not backend validation. The doctor reports preparation available,
CUDA prerequisite diagnostics, and execution unavailable in this release. There
are no new native-adapter or MCP protocol changes. Torch/OCC/model assets are not
installed into CAD-GIT. Progress during preparation is currently indeterminate.

## Later evidence (2026-11-09)

The pending list above describes this preparation-only review. A subsequent
[external CUDA investigation](DUALBREP_CUDA_INVESTIGATION.md) exercised upstream
model inference and independently re-imported one successful normalized STEP
solid. CAD-GIT integration, restored manufacturing scale, Rhino reopening and MPS
qualification remain pending. This does not retroactively expand this audit.
