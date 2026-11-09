# Features and implementation history

Inventory of implemented capabilities, with limits and evidence. Last reviewed:
**2026-11-09**. [issues.md](issues.md) owns all open bugs and future work.
This is a prototype capability inventory, not a claim that the entire
[specification](docs/SPECIFICATION.md) has shipped.

## Implemented capabilities

| Area | Available behavior | Boundary / evidence |
| --- | --- | --- |
| Local snapshot history | Full-scene USD captures, independent source branches, named versions, ancestry, deliberate main selection | Native documents keep ordinary working files; no automatic cross-app merge. [Implementation](docs/V1_IMPLEMENTATION.md) |
| Scene assembly | Open saved scenes in tabs, select objects across versions, compose pinned recipes, save immutable USD results | Static polygon workflow; animation/complex instancing limitations. [README](README.md) |
| Native workflows | Reference Rhino/Blender save hooks, local inbox service, new native-file handoff with lineage sidecars; configurable external targets | Reference integration targets macOS; no generic plugin registry or NURBS recovery. [Hardening](docs/REVIEWS_AND_HARDENING.md) |
| Inspection UI | Git-style graph, wireframe/shaded/rendered-preview/X-ray modes, edge highlights, click-away deselection, resizable saved layouts, tooltips | PyVista inspection renderer, not Cycles. [UI review](docs/REVIEW_2026-11-08_ROUND_2.md) |
| Material and asset library | Project-wide material/image/shader/document revisions, provenance and pinned dependencies, native Blender graph archives, portable appearance and separate physical data | Native graph restoration is whole-object; arbitrary engineering/renderer formats are not interpreted. [Library](docs/MATERIAL_LIBRARY_V1.md) |
| Direct artifacts | USD and STL export from saved scenes/assemblies, unit conversion, topology diagnostics and lineage | No printability certification, boolean union or evaluated renderer displacement. [README](README.md) |
| Integrity and compatibility | Hash inventories, staged publication, local writer lock, recovery, additive optional fields and explicit required-feature rejection | USD alone does not guarantee application-schema compatibility. [Contract](docs/DATA_COMPATIBILITY.md) |
| CLI, optional MCP and onboarding | CLI works without AI; optional stdio MCP; agent-agnostic portbook covers scenes and materials | [Skill](skills/cad-git/SKILL.md), [tool contract](skills/cad-git/references/tool-contract.md) |
| App identity | CAD-GIT application name, icon assets and launcher | [README](README.md) |

## November 9 implementation update

These additions follow baseline commit `97b81437a5142bcb9dba4cdee71a97eb93bab12c`.
A checkout pinned to that baseline does not include them. Publication does not
imply that deferred native/manual release gates have passed.

- **Responsive loading:** bounded CPU scene workers, background normals/texture
  preparation, batched actor installation and cancellation. GPU rendering remains
  synchronous. [Evidence](docs/VIEWPORT_LOADING.md).
- **B-rep job preparation:** immutable per-part inputs, lineage, unit/normalization
  metadata, explicit component splitting, verification, CLI/UI preparation and
  CUDA prerequisite diagnostics. **No inference or STEP export in CAD-GIT yet.**
  [Scope and audit](docs/REVIEW_DUALBREP_PREPARATION.md).
- **Engineering gates:** repeatable core/CLI/wheel/GUI runner, source-drift checks,
  scoped independent review requirements and CI definition. Hosted CI and native
  qualification are separate from local checks. [Gates](docs/BUILD_GATES.md).

## History

### 2026-11-09 — Finite user-workflow test expansion

Added a UX-agent action/state catalog, deterministic viewport combinations,
dialog/material/filter and asynchronous-context sequences, and a real stdio MCP
workflow covering the exposed tools. The build runner now supports `--mcp` and
includes the two added GUI suites under `--ui`. Detailed scope and gaps live in
[the matrix](docs/UX_TEST_MATRIX.md); results in the
[review record](docs/REVIEW_WORKFLOW_COVERAGE.md). Native/manual gaps remain issue
#12. Fixed the reproduced export→verify inconsistency: exact returned print IDs
now verify through the shared core, with corruption and unsafe-path regressions. These are finite tests, not proof of all possible user action sequences.


### 2026-11-09 — Optional provider scope decision

B-rep reconstruction belongs in the separate DualBrep fork, potentially packaged
as a Docker service. CAD-GIT may later submit jobs and track results through a
thin adapter; an unsupported runtime reports unavailable. Neither the service nor
Docker integration is implemented. Apple acceleration and reconstruction research
are not CAD-GIT release gates. See [scope contract](docs/DUALBREP.md).

### 2026-11-09 — Tracking documents and CUDA evidence

Added issues/features ledgers and document-maintenance rules. Future ideas retain
stable IDs in issues.md; completed outcomes move here with evidence. The former
future-features document remains a linked design note, not a second backlog.

Upstream DualBrep was exercised separately on C110P (RTX 5070 Ti): CUDA operations,
AE reconstruction and parametrization passed; sample `00030157` produced an
independently re-imported valid solid (one shell, 25 faces). Sample `00013293` at
resolution 256/rotation 3 produced six shells and zero solids. This is backend
research, **not an enabled CAD-GIT feature or a general success-rate estimate**.
Follow-up rotations 0 and 7 sealed the first sample too; candidate selection and
fidelity qualification remain open. Units remain normalized. See [diagnostics](docs/DUALBREP_CUDA_INVESTIGATION.md),
issues #1–#4 for remaining work.

### 2026-11-08/09 — Viewport, job preparation and build gates

Local implementation and audits are recorded in
[viewport/gate review](docs/REVIEW_2026-11-08_VIEWPORT_AND_GATES.md) and
[B-rep preparation review](docs/REVIEW_DUALBREP_PREPARATION.md). The prior full
local run recorded 150 core tests, CLI/wheel checks and six GUI suites passing in
`build/qa/20261109T051134.881931Z/report.json` (ignored machine-local evidence).
That run predates this documentation update and does not qualify inference.

### 2026-11-07/08 — Integrity, material and UI hardening

Fixed staged-publication/recovery failures, ancestry and app-binding ambiguity,
archive containment, failed-load retry, material identity and texture/UV fidelity.
See [initial review](docs/REVIEWS_AND_HARDENING.md),
[material review](docs/MATERIAL_LIBRARY_REVIEW.md),
[November 8 review](docs/REVIEW_2026-11-08.md) and
[texture recheck](docs/REVIEW_2026-11-08_ROUND_2.md) for exact scope and evidence.
These historical reports retain their original results; later changes require
new validation rather than retroactively changing old test claims.
