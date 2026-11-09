# Review: layered verification / 2026-11-09

Status: scoped implementation and applicable automated gates validated; not a release qualification.

- Scope: scoped static checks, existing model contracts, bounded JSON properties,
  two legacy serialization snapshots, fresh compatibility mutation audit, CI and
  coverage reporting. Acceptance and limits: [verification guide](TEST_VERIFICATION.md).
- Source: HEAD `a5c1c7ed9c209b5edf76c4463d92dc923525525a` plus local working-tree
  changes including untracked verification tests, snapshots, mutation script and
  documentation; no commit/publication. Reports include diff fingerprints.
- Runtime: macOS 27.0.1 arm64, Python 3.12.4, USD 26.11, PySide6 6.12.0,
  VTK 9.7.2; Hypothesis 6.170.15, Mutmut 3.8.1, mypy 1.20.2, Ruff 0.17.4.
- Architecture: independent read-only agent inspected compatibility semantics,
  mutation isolation/report failures and tests; 51 focused tests, two snapshots,
  lint/format/types passed. No actionable P0–P2 in scoped feature audit.
- UI/UX: separate product UX audit not applicable; no product workflow or viewport
  implementation changes. Test-only teardown was architecture-reviewed and
  independently exercised in the real graphical environment.
- QA: independent read-only agent passed static gates, 51 focused tests/two
  snapshots and fresh mutation run (55/57); no actionable feature findings.
  Added runner-abort regression recheck: 17 gate tests plus 35 compatibility/model
  tests and two snapshots passed; no new findings.

| Priority | Finding / reproduction | Fix or disposition | Regression / recheck |
| --- | --- | --- | --- |
| Informational | 2/57 mutation survivors | Equivalent cast and nonpersisted minor-default changes; included in score | Parent + independent QA reproduced 55 killed, 96.49%, no unresolved outcomes |
| P2, #14 | Dialog suite completed 46 assertions then exited -6 during Qt finalization | Harness closes both windows, bounded worker waits, explicit deferred destruction; marker after cleanup | Parent + independent architecture standalone rechecks exited 0; runner regression preserves failure on banner + abort; full recheck passed (all eight GUI suites) |

## Gate results and failure evidence

Initial full command: `uv run python scripts/check.py --build --ui --mcp --mutation`.
Report: `build/qa/20261109T194043.306440Z/report.json` (ignored machine-local evidence).
Static checks, **207 core tests / 2 snapshots**, CLI, mutation, wheel/build/install
and the first seven GUI suites passed. Dialog suite emitted 46 case markers then
aborted (exit -6), so the runner correctly marked failure and MCP pending. Never
count that dialog run as passed. Standalone MCP subsequently passed all 15 cases
and 17 tools; standalone pre-fix dialog rerun passed, demonstrating intermittency.

Matching native crash report (kept outside the repo) was
`~/Library/Logs/DiagnosticReports/python3.12-2026-11-09-144144.ips`, captured at
14:41:38 -0500. Main-thread stack: pure virtual call → QObject/QWidget destructor
→ QPushButtonWrapper destructor → PySide destruction visitor → Shiboken wrapper
iteration → destroyQCoreApplication → module shutdown → Python finalization.
This supports retained test-widget teardown as the boundary; it does not establish
a product worker defect. Closing a window alone does not delete its retained Qt
children. See [Qt event-loop documentation](https://doc.qt.io/qt-6/qcoreapplication.html#processEvents).

Post-fix parent and independent architecture standalone runs passed all 46 cases,
including explicit cleanup, with clean process exit. Independent regression and
full-code run results will be appended below. Intermittent failures cannot be
proven absent by a finite number of passing executions.

## Remaining limits

Generated domains and static/mutation scopes are bounded as described in the
guide. Coverage is diagnostic only (initial core run reported 43%; GUI suites
run separately and are not included). Issue #13 tracks broader static and
persistent-history property/mutation coverage; #12 retains native/manual gaps.
Native roundtrips are not applicable to this annotation/test change and are not
claimed passed. Hosted CI and branch protection remain unverified. The portbook's
product commands/setup are unchanged; development instructions changed in README
and BUILD_GATES. No release-readiness claim follows from this test infrastructure.

## Final-code verification

`uv run python scripts/check.py --build --ui --mcp --mutation` exited 0 on the
final executable code. Report: `build/qa/20261109T194401.200630Z/report.json`.
All **19 selected automated gates** passed with no pending checks and matching
start/end source fingerprints. Tested diff SHA-256: `99d439a781ac510f5e5cccf153c6f0c91a69ac280c0f35f1b59ea828d6d07431`.
Only evidence-document text was finalized after this run; no executable code,
configuration, lockfile, fixtures or snapshots changed afterward.

| Gate | Final result |
| --- | --- |
| Ruff lint/format, strict mypy | Passed within the configured file scopes |
| Core | 208 passed, including 50 added test cases; 2 snapshots passed |
| CLI | Passed |
| Mutation | 55/57 killed (96.49%), 2 reviewed equivalent survivors, zero unresolved outcomes |
| Distribution build / installed wheel | Passed |
| Graphical suites | All 8 passed, including 46 dialog cases and explicit clean teardown |
| MCP protocol | 15 scenarios / 17 tools passed |
| Independent architecture / QA | Passed scoped review and fix rechecks; see above |
| Markdown / whitespace | Changed local link targets exist; git diff --check passed |
| Live native / hosted CI | Not run; not inferred from automated local results |

The #14 fix has parent standalone, independent architecture standalone and final
full-run clean-exit evidence. Original failed evidence remains recorded above.
No known P0/P1 or undisposed P2/P3 was found in this scoped delivery. Broader
coverage remains #13 and native/manual workflow gaps #12.

## Follow-up survivor audit (#15)

User requested executable verification of the two survivor assessments. Added
six collected meta-tests in `tests/test_verification_survivors.py`; no product
code, mutation threshold or selection changed. Initial focused CI-profile run:
6 passed. Runtime differential properties preserve inputs and compare rejection
messages as well as accept/reject results. Independent behavioral controls fail
the existing oracle as intended; mypy rejects the cast mutation while accepting
the original and minor-default variant.

Independent architecture reviewer ran both CI and deep profiles (6 passed each),
reviewed the control faults and isolated mypy checks, and found no actionable
issues. Ruff lint/format passed. Equivalence is scoped to ordinary JSON records;
exotic Python dict subclasses, introspection and timing are outside the contract.

Final follow-up command `uv run python scripts/check.py --build --mcp --mutation`
passed: **214 core tests**, two snapshots, scoped static checks, CLI, wheel/build,
MCP and 55/57 mutation kills. Report:
`build/qa/20261109T194849.287261Z/report.json`; matching start/end tested diff:
`8bc9739d9bf2a3fa10227d347e45c1942d8d8ba8a9e30b21fe34e029e2d9b5ef`.
No pending selected checks. Only ledger/evidence text changed afterward; no
executable changes. GUI/native were not rerun for this test-only follow-up;
the previous eight-suite GUI result above remains dated evidence. Changed local
Markdown links and git diff whitespace passed. #15 is closed with bounded
executable evidence; #13 retains broader verification work.
