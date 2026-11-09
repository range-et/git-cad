# Build and release gates

This is the recurring engineering workflow for Git CAD, effective November 8, 2026.
It turns the architecture → implementation → UX/QA → fixes → re-audit routine into
an explicit contract. Automated tests run without AI agents; reviewers can be
independent humans or, when working through an agent, delegated subagents.

## Gate selection

| Change | Required evidence |
| --- | --- |
| Documentation or small cosmetic change | Diff/link/command validation and relevant focused check. |
| Core behavior | Core tests, CLI smoke, wheel build/import check; meaningful regression for the changed behavior. |
| Storage, lineage, compatibility, native adapters or concurrency | Core gates plus independent adversarial architecture review. |
| Significant UI/workflow/viewport behavior | Core gates, graphical suites, independent UX review; inspect actual UI and failure/retry paths. |
| Native handoff/capture/material restoration | Above gates plus applicable isolated native-app roundtrip. Record app/OS version and file dependencies. |
| Release candidate or cross-cutting feature | Architecture, UX and independent QA review; core, build and graphical gates; native gates for affected adapters. |

## Working sequence

1. Read features.md and GitHub Issues; find or create and triage the relevant issue. Define scope and observable acceptance criteria. Name data invariants and
   compatibility risks. Use an existing project only for read-only investigation;
   create temporary projects for mutation/failure probes.
2. For a new cross-cutting feature, ask architecture and UX reviewers to scope
   their concerns independently. Combine findings into a concrete implementation
   contract. Small fixes can proceed directly to implementation and audit.
3. Implement and run focused checks. Preserve old fixtures and source files.
   A bug regression should fail for the observed defect, not merely mirror code.
4. Delegate independent post-build audits. Architecture reviews failure boundaries,
   corruption/partial publication, lineage, concurrency and backward compatibility.
   UX walks user tasks, selection/context, progress, cancellation/retry, keyboard
   access, narrow layouts and honest preview limitations. QA independently checks
   gate results, packaging and cross-interface behavior.
5. Triage findings: P0 catastrophic loss/security; P1 wrong results, data loss or
   blocked core workflow; P2 significant bounded defect; P3 polish. Reproduce before
   fixing or rebutting. Record accepted/deferred findings with rationale.
6. Fix blockers and request a recheck from the reviewer who raised them. Run the
   impacted checks on the final code. A reviewer saying “no findings” is scoped
   evidence, not universal certification.
7. Update the GitHub issue, features.md and affected user documentation under the
   document-hygiene rules in AGENTS.md; validate changed links and claims.
   Attach the completed review record. A candidate is ready only when applicable
   automated/manual gates passed and no known P0/P1 remains. Skipped/unavailable
   gates stay pending. A local WIP commit is allowed if requested, but must not be
   represented as a validated release. Publication requires user authorization.

## Reusable commands

```sh
uv sync --frozen --extra dev --extra mcp
uv run python scripts/check.py --build
uv run python scripts/check.py --build --ui --mcp --mutation
```

The runner executes sequentially, stops on failure, and writes a JSON report plus
per-command logs to ignored `build/qa/<timestamp>/`. Reports identify the Git HEAD,
dirty state and diff digest, selected checks, elapsed times and explicit omissions.
The final source fingerprint must match the starting tree; concurrent source edits
invalidate the run. Failures leave the remaining planned checks explicitly pending.
On macOS/POSIX, timeouts and interrupts terminate the check's process group.
It runs scoped Ruff/mypy, core pytest (CI property profile and coverage XML) and CLI smoke; `--build` additionally builds the wheel/sdist,
installs the wheel to a disposable directory and checks the installed CLI/resources.
`--ui` adds geometry, failure/retry, materials, actual texture pixels, large-scene
responsiveness, optional B-rep preparation, finite viewport combinations and dialog workflows. GUI suites require a working display/OpenGL context.
Do not treat headless/offscreen success as evidence of native desktop interaction.

The GitHub Actions workflow runs static/core/build/MCP and compatibility mutation gates on macOS for pull requests
and pushes to main. It does not run live Rhino/Blender or interactive GUI checks.
Branch protection must be configured separately if the hosted status is to block
merges; this repository file does not change GitHub settings.

## Specific acceptance rules

- Old format fixtures open without rewriting history; unknown optional data
  survives updates; unknown required features reject with an actionable error.
- Failed writes preserve existing files and committed history; retries do not
  invent duplicate captures or silently choose conflicting heads.
- Material/image revisions pin exact dependencies; renderer validation is separate
  from archive/hash validation. Capture → compose → export → reopen must retain
  the intended lineage and supported appearance.
- UI errors, delayed callbacks, closed windows/tabs, partial imports and retry
  paths are tested. Large-scene checks measure event-loop progress, not just total
  throughput; record scene scale and hardware context rather than a universal FPS.
- The wheel contains hooks, theme/license and icon assets. CLI/MCP operations must
  remain usable independently of the GUI. Add an MCP protocol smoke gate when the
  server surface or SDK changes; importing its module alone is insufficient.
- Update the agent-agnostic skill/portbook whenever commands, setup, data meanings,
  compatibility boundaries or supported workflows change. Validate examples against
  actual commands; do not install skills globally as a side effect of testing.

Use [the review template](REVIEW_TEMPLATE.md) for evidence. Earlier examples include
[material audits](MATERIAL_LIBRARY_REVIEW.md) and the
[second November 8 review](REVIEW_2026-11-08_ROUND_2.md).

## UX action/state coverage

Use [the UX test matrix](UX_TEST_MATRIX.md) when changing user workflows. Enumerate
actions, valid/invalid states, cancellation, background context changes and
persistence invariants before claiming coverage. New supported actions need a
matrix entry and an automated regression where feasible; manual/native coverage
must be marked pending rather than inferred from mocks. AI reviewers design and
audit scenarios; deterministic tests run without an AI service.

`--ui` includes `workflow_combinations.py` (the declared finite viewport product
and draft/tab transitions) and `dialog_workflows.py` (dialog cancellation, invalid
settings, material revisions/filter combinations and frozen async targets).
`--mcp` adds `mcp_workflow_smoke.py`, a real stdio client/server workflow; install
the `mcp` extra first. The matrix maps coverage and gaps; it is not proof of every
arbitrarily long action sequence or every native app/OS combination.

## Layered verification

See [the verification guide](TEST_VERIFICATION.md) for exact static scope, bounded
generated inputs, existing runtime contracts, reviewed snapshots and the optional
`--mutation` audit. Mutation statistics must be complete and score at least 95%;
timeouts/crashes/uncovered outcomes are failures, not kills. CI enables this gate.
No global coverage percentage or repository-wide typing claim is implied.
