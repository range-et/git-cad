# Review: finite user-workflow coverage — 2026-11-09

Scope: map supported user actions/states, extend deterministic workflow tests, run
all automated suites and fix reproduced defects. Infinite repeated sequences,
every input model and every application/platform are not a finite test promise.
The [UX matrix](UX_TEST_MATRIX.md) distinguishes mapped, partial, missing and
native/manual coverage; unexecuted obligations remain open in issue #12.

Base HEAD: `97b81437a5142bcb9dba4cdee71a97eb93bab12c` plus the local working tree.
The final runner records tracked/untracked source fingerprint, OS, Python, exact
commands, results and per-suite logs under ignored `build/qa/<timestamp>/`.
No native user documents were modified by this work.

## Independent reviews

- `ux_test_matrix`: read-only action/state review of UI/core suites and new tests;
  owns the 64-row catalog and its scope/gap annotations.
- `workflow_tests`: implemented and exercised the finite viewport/tab/draft suite;
  subsequently implemented the print-ID verification regression and fix.
- `protocol_qa`: exercised the real stdio MCP workflow, independently audited the
  artifact lookup fix and adversarial duplicate-ID/symlink/corruption probes.
  No reproduced P0/P1 remained in that scoped fix; this is not global certification.
- Parent: dialog/material/settings/async-context suite, runner integration,
  documentation and final full automated run.

## Reproduced finding and resolution

| Finding | Fix | Verification |
| --- | --- | --- |
| Export returns a `print_…` ID but `verify(ID)` rejected it through CLI/MCP's shared core. | Exact print IDs resolve only in verification, leaving scene resolution unchanged; reject ambiguous IDs and unsafe archive directories. No schema or archive writes. | Dedicated artifact tests; real MCP export → verify → corrupt one archived byte → verify failure → restore → verify success. Independent duplicate-ID and collection/root symlink probes. |

Development test corrections: the test fixture's external target needed the
supported `.usdz` extension; draft comparisons needed JSON-normalized tuple/list
values. These were test-oracle/fixture defects, not product fixes.

## Automated scope

- Existing core/compatibility, CLI, distribution/install and six GUI suites.
- `workflow_combinations.py`: **78 cases**, including all 64 ordered mode-pair ×
  edge-state × none/single-mesh-selection combinations with A→B→A tab switching;
  14 additional hierarchy/draft/tab lifecycle and immutable-source cases. Group
  selection is checked separately, not multiplied into the 64-case product.
- `dialog_workflows.py`: **46 cases**. File/dialog cancellation, overwrite refusal,
  invalid/valid target settings, material create/revise/derive/recombine with pinned
  donors, all seven library filter kinds × three queries, frozen async save/export
  context, committed-ID reporting on export failure, empty project and simultaneous
  project isolation. Uses real Qt dialogs but scripted native file-picker responses.
- `mcp_workflow_smoke.py`: **15 named scenarios across all 17 exposed tools** via
  real stdio, including invalid input recovery, stale revisions, exact dependency
  lineage, non-overwrite, print verification and source hash invariants.

## Reproduction and result authority

```sh
uv sync --extra dev --extra mcp
uv run python scripts/check.py --build --ui --mcp
```

The integrated run `build/qa/20261109T061130.391264Z/report.json` passed all selected
checks on a stable source tree: 158 core tests, CLI, build/install, eight GUI suites
(including 78 combination and 46 dialog cases), and 15 MCP scenarios across all
17 tools. Documentation-only publication/status notes were updated afterward;
no runtime or test code changed. Future implementation changes require rerunning
affected checks; this result does not certify the remaining manual/native gaps.

## Explicit limits

This does not run live Rhino/Blender save hooks, rendering fidelity, external
application launch behavior, hosted CI, OS file-dialog accessibility or screen-reader
checks. Existing tests simulate selected failures; not every filesystem/device
failure is injected. Remaining GUI sequences listed Partial/Gap in the matrix
remain untested in full. Docker reconstruction is outside scope; preparation-only
regressions continue to exercise the already-present feature.
