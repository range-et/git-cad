# Features and implementation history

Inventory of implemented capabilities, with limits and evidence. Last reviewed:
**2026-11-09**. [GitHub Issues](https://github.com/range-et/git-cad/issues) owns all open bugs and future work.
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
| App identity | Git CAD application name, icon assets and launcher | [README](README.md) |

## November 9 implementation update

These additions follow baseline commit `97b81437a5142bcb9dba4cdee71a97eb93bab12c`.
A checkout pinned to that baseline does not include them. Publication does not
imply that deferred native/manual release gates have passed.

- **Responsive loading:** bounded CPU scene workers, background normals/texture
  preparation, batched actor installation and cancellation. GPU rendering remains
  synchronous. [Evidence](docs/VIEWPORT_LOADING.md).
- **B-rep job preparation:** immutable per-part inputs, lineage, unit/normalization
  metadata, explicit component splitting, verification, CLI/UI preparation and
  CUDA prerequisite diagnostics. **No inference or STEP export in Git CAD yet.**
  [Scope and audit](docs/REVIEW_DUALBREP_PREPARATION.md).
- **Engineering gates:** repeatable core/CLI/wheel/GUI runner, source-drift checks,
  scoped independent review requirements and CI definition. Hosted CI and native
  qualification are separate from local checks. [Gates](docs/BUILD_GATES.md).

## History

Older entries retain former local ledger IDs; they are not GitHub issue numbers.
Use the [migration map](docs/ISSUE_MIGRATION.md) for imported open items and explicit
GitHub links for current work.

### 2026-11-09 — GitHub becomes the open-work tracker ([#30](https://github.com/range-et/git-cad/issues/30))

All 28 former open ledger entries are tracked in GitHub issues #2–#29, retaining
scope, priority, acceptance criteria and cross-references. GitHub is now the sole
open-work authority; the local issues.md file is retired. AGENTS.md requires
GitHub triage, implementation and verification, a linked features.md completion
entry, then issue closure with evidence. Imported GitHub bodies and current docs
follow that policy. [Historical ID map](docs/ISSUE_MIGRATION.md).

Implementation scope: repository workflow/documentation changes and removal
of the retired file from mutation-runner inputs. Validation: 47 affected campaign
tests passed (`uv run pytest -q tests/test_verification_campaign.py
tests/test_verification_campaign_cache.py tests/test_verification_campaign_runtime.py`);
Ruff, whitespace, Markdown links and all 28 remote issue-policy updates verified.
This migration is not a product release or completion of the still-open
coverage/native roadmap.


### 2026-11-09 — Open-work ledger linked to GitHub

Created 28 GitHub issues from the former local ledger,
including deferred/provider work and implemented fixes awaiting final review.
Statuses, scoped priorities, evidence and acceptance criteria were retained;
GitHub cross-references point to the corresponding imported issues. Stable ledger
IDs remain distinct from GitHub numbers. [GitHub backlog](https://github.com/range-et/git-cad/issues).

### 2026-11-09 — PR #1 publication warnings and skill mutation identity (#40, #41)

- **#40:** snapshot ingest now returns every new native-material publication
  warning with its revision ID alongside any snapshot warning. Completion warnings
  remain transient; committed manifests and inputs are unchanged. Clean captures
  and reuse of existing material archives omit the warning field.
- **#41:** the onboarding loader registers `cadgit_skill.inspect_folder` before
  executing the exact helper file. Real generated baseline and killed-mutant probes
  now work; wrong-source checks remain strict. A selected actual runner candidate
  was killed;325 unselected skill candidates remain pending, not credited.

Validation:467 core tests/four snapshots, CLI and wheel/build gates passed;
independent architecture80-case and QA53-case rechecks passed. These close the two
specified PR findings; whole-project coverage and earlier native/GUI limits remain.
[Reproduction, review and gate evidence](docs/REVIEW_PR1_MERGE_FIXES.md).

### 2026-11-09 — Verified traversal, recovery and save outcomes

Local working-tree fixes with independent scoped rechecks and full selected gate
`20261109T222731.086473Z`:461 core tests/four snapshots, CLI/wheel, nine graphical
suites, MCP and scoped compatibility mutations passed. [Evidence](docs/REVIEW_FULL_VERIFICATION.md).

- **#26:** iterative verification checks shared ancestors once and handles80 real
  snapshots under constrained recursion; duplicate and corrupt dependencies stay
  visible. This is bounded evidence, not arbitrary-size performance qualification.
- **#31–#34:** receipt recovery uses exact source/capture identity, verifies input
  digests before cleanup, preserves legacy inputs without fabricated hashes,
  tolerates malformed legacy IDs and rejects symlinked inbox escape paths.
  Both original P1 probes independently passed; producers must cooperate with
  the immutable-ready contract.
- **#35:** autosnapshot CLI and application-target settings use shared locked
  publication outcomes, preserve additive config fields and expose committed-save
  warnings. Real dialog failure/retry checks passed.
- **#36:** external runtime diagnostics validate JSON shape and cannot enable
  inference by overriding execution support. Nine focused runtime cases passed.
- **#38:** legacy UI freezes queued recipes, keeps publication warnings visible
  after asynchronous loads and rejects stale preview completions. Real Qt/VTK
  regression and independent handler rechecks passed.

Whole-project line/mutation completion remains [#15](https://github.com/range-et/git-cad/issues/15); intermittent GUI investigation
remains [#29](https://github.com/range-et/git-cad/issues/29). These results do not qualify live Rhino or constitute publication.

### 2026-11-09 — Git CAD naming alignment (#37)

Public branding, distribution and canonical command now match `range-et/git-cad`:
**Git CAD / `git-cad`**. Added `Open Git CAD.command`; the old launcher and `cad-git`
command remain compatible. Internal package/archive identifiers, saved settings,
Git-rule sentinels and resource paths remain unchanged. Actual wheel entrypoint,
identity, CLI and MCP checks passed; independent QA/UX naming rechecks passed.
This records local working-tree changes, not publication. [Evidence](docs/REVIEW_FULL_VERIFICATION.md#git-cad-naming-and-legacy-ui-follow-up).

### 2026-11-09 — Executable survivor assessment (#15)

Added six meta-tests comparing the exact two surviving compatibility edits with
the baseline, checking strict typing, and proving the existing oracle rejects
three behavior-changing controls. The cast edit is rejected by mypy but is
runtime-neutral; the missing-minor default edit remains equivalent for ordinary
JSON records. Independent CI/deep runs passed; final core run passed 214 tests.
Mutmut's runtime score remains honestly 55/57. See
[scope](docs/TEST_VERIFICATION.md#testing-the-survivor-assessment-15) and
[review evidence](docs/REVIEW_TEST_VERIFICATION.md#follow-up-survivor-audit-15).

### 2026-11-09 — Dialog test-process cleanup (#14)

A full gate exposed an intermittent Qt abort after all 46 dialog assertions.
The harness now drains workers and explicitly destroys retained windows before
Python shutdown; its success marker follows cleanup. Added a gate regression for
success output followed by native abort. Parent and independent architecture
standalone rechecks passed; final full-run status is recorded in
[verification evidence](docs/REVIEW_TEST_VERIFICATION.md). No product UI behavior
changed and no universal shutdown-reliability claim is made.

### 2026-11-09 — Scoped layered verification (#13)

Added scoped Ruff and strict mypy checks, generated compatibility/model contract
cases, two legacy serialization snapshots, coverage diagnostics and an isolated
compatibility mutation gate (95% floor). CI also runs the real MCP smoke. This is
local source capability; hosted results and repository-wide strictness are not
claimed. [Scope/commands](docs/TEST_VERIFICATION.md),
[review and gate evidence](docs/REVIEW_TEST_VERIFICATION.md). Broader adoption
remains open as #13; native/manual workflow coverage remains #12.

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
as a Docker service. Git CAD may later submit jobs and track results through a
thin adapter; an unsupported runtime reports unavailable. Neither the service nor
Docker integration is implemented. Apple acceleration and reconstruction research
are not Git CAD release gates. See [scope contract](docs/DUALBREP.md).

### 2026-11-09 — Tracking documents and CUDA evidence

Originally added issues/features ledgers and document-maintenance rules. The local
open-work ledger was subsequently retired in favor of GitHub Issues (see migration
entry above); this entry preserves the original historical context. The former
future-features document remains a linked design note, not a second backlog.

Upstream DualBrep was exercised separately on C110P (RTX 5070 Ti): CUDA operations,
AE reconstruction and parametrization passed; sample `00030157` produced an
independently re-imported valid solid (one shell, 25 faces). Sample `00013293` at
resolution 256/rotation 3 produced six shells and zero solids. This is backend
research, **not an enabled Git CAD feature or a general success-rate estimate**.
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
