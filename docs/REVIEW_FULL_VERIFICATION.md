# Entire-project verification campaign — 2026-11-09

Status: fixes and verification in progress. Not a validated candidate.

## Scope and acceptance

Issue #16 requests 100% production Python line coverage across package code,
bundled native hooks and tools, plus honest complete mutation accounting. Tests
must reject data loss, broken exact revision links and false failed-save reports.
Equivalent mutations, unavailable native environments, crashes and timeouts must
remain explicit rather than count as kills. Tests use disposable real projects;
corruption probes never alter user archives.

Source scope: local working tree, including untracked tests/runners, based on HEAD
`a5c1c7ed9c209b5edf76c4463d92dc923525525a`. Ongoing edits invalidate earlier runs
as final-candidate evidence. Runtime: macOS 27.0.1 arm64, Python 3.12.4, Mutmut3.8.1.

## Independent review and findings

Architecture, UX and QA subagents reviewed implementation and exercised failures.
The implementer owns integration and final verification.

| Issue | Finding | Current disposition and evidence |
| --- | --- | --- |
| #17 P1 | Postpublication main-pointer sync error rolled back the matching scene | Destination-tagged publication outcome; unreadable outcomes fail explicitly without unsafe rollback. Regression includes first selection/previous main and readback failure. |
| #18 P2 | Missing pinned parents still verified | Verify scene parents/imports/assembly pins and library parents. Preserve opaque additive snapshot fields; reject uncommitted imported_from before publication. |
| #19 P2 | Failed library validation retained enabled actions | Invalidate controls before validation and block material use. Independent real-Qt recheck passed. |
| #20 P2 | Config event recorded before failed config write | Publish config before success event; explicit warning for published sync/event failures. |
| #21 P2 | Failed native capture left material pointing at nonexistent snapshot | New material provenance distinguishes capture_attempt_id; retry retains immutable material and pins its committed ID. Existing manifests untouched. |
| #22 P1 | Record sync failure reported published archive as failed | Return exact committed record and durability warning after rename. |
| #23 P2 | UI discarded durability warnings or replaced them after background load | Shared completion status retains warnings. Independent 55-case dialog run passed; additional real-Qt ingest/STL/B-rep warning and B-rep failure/retry probe passed. Durable expansion ongoing. |
| #24 P2 | Manifest selections could differ from hashed recipe | Compare inventoried recipe's known fields using JSON serialization semantics; preserve tuple/list API equivalence and legacy recipe absence. |
| #25 P1 | Handoff output sync failure deleted already-published file's sidecar | Publish errors identify destination. Handoff retains output+lineage and returns warning. Independent original repro recheck passed; export/UI propagation added, final gates pending. |
| #26 P2 | Shared ancestry verified exponentially | Eight legitimate material revisions caused 255 checks in 2.433 seconds. Shared iterative traversal implemented; real eight-revision DAG and 80-snapshot limited-recursion tests pass; independent three-test traversal recheck passed; bounded80-save evidence, not arbitrary-size performance qualification. |

## Diagnostic measurements

- Explicit initial inventory: 1,576/4,131 production lines (38.15%) from core tests.
  Default package coverage had omitted resource hooks; the complete inventory
  explicitly includes unimported files.
- First combined core/CLI/eight GUI/MCP diagnostic: 3,176/4,225 lines (75.17%),
  1,049 missing, zero exclusions. Runtime thread/subprocess instrumentation was
  incomplete; follow-up uses Python monitoring and forwards coverage env into
  the MCP stdio server. This is not a 100% result.
- Follow-up complete-inventory run:3,526/4,669 lines (75.52%),1,143 missing,
  zero exclusions; all measured suites passed. Source fingerprint matched. This
  predates iterative traversal changes and is diagnostic, not final evidence.
- Focused library measurement reached 243/243 lines. Later edits require remeasure.
- Fresh-process history-graph campaign: 351 generated candidates; first run
  268 killed, 81 survived, 2 timed out. Strengthened contracts caught59 of the83
  unresolved candidates on a diagnostic retest;24 survived. Neither run is final
  full-source evidence; source changed during diagnosis.
- Native Mutmut fork workers aborted in this host's numerical/GUI environment;
  no crashes were credited as kills. Fresh-process runner requires exact mutant
  hit, ordinary pytest failure, matching clean baseline and source provenance.
- Mutmut omits some decorated/module-level code. Generated candidate coverage is
  not equivalent to testing every executable line; eligibility gaps stay explicit.

## Runner review

QA found and reproduced source-drift, zero-candidate false-success, weak report
schema and interrupted-worker cleanup defects in experimental runners. Fixes and
meta-tests are in progress. Reports must validate exact source/candidate identity,
start/end bytes, full inventory, line/count consistency and ordinary test outcomes.
Independent cleanup rechecks confirm interrupted child groups are reaped. All four remaining runner P2 findings (runtime assets, spawn cancellation race,
unsafe output paths and full generated-workspace integrity) passed independent
recheck; focused meta-tests:36 passed. This qualifies safeguards only.

## Gates and limits

Final whole-source line/mutation gates, core/CLI/wheel/GUI/MCP rerun, reviewer
rechecks, ledger closure and documentation/link checks remain pending. Live Rhino
roundtrips remain pending for this campaign; the bounded live Blender result is
recorded below. Real Qt tests and mocked native hook tests do not qualify native apps. No commit/publication made.

Earlier scoped compatibility results remain in
[the prior review](REVIEW_TEST_VERIFICATION.md); current open status is authoritative
in [issues.md](../issues.md). Do not use this progress record as release approval.

## Follow-up recovery and native evidence

The recovery audit additionally reproduced #30 (corrupt archived capture still
caused frozen-native deletion), #31 (capture ID collision across source apps),
#32 (changed/reused input and recovery timing), #33 (non-string identity blocking
the queue) and #34 (symlinked inbox escaping the project). Fixes and durable tests
now cover exact source+ID lookup, ambiguity rejection, healthy archives, recorded
input digests, conservative legacy retention and path checks before writes. Final
independent recheck remains pending; producer ready-directory immutability is an
explicit boundary, not arbitrary-writer synchronization.

A live Blender5.2.3 LTS roundtrip passed in disposable background processes using
`uv run python tests/integration/native_blender_roundtrip.py`: two automatic saves,
two material revisions, exact parent linkage, archived texture bytes, standalone
USD texture pixels after detaching the original image, one restored native mesh
with its graph/image, and unchanged original `.blend`/image bytes. OpenUSD emitted
nested-package localization warnings; explicit dependency and texture-pixel checks
passed. This is not a qualification of every renderer graph or a live Rhino gate.
The command is opt-in and is not silently substituted for GUI suites.

Latest complete history-graph diagnostic:338/349 runtime kills,11 survivors.
Crossing/shared-parent/corrupt-cycle regressions then caught8 of those11 in a
matched subset run. Three remain for explicit equivalent assessment. No timeout
or equivalent was counted as a kill; these counts are not a whole-project score.

## Git CAD naming and legacy UI follow-up

November 9, local uncommitted working tree based on the HEAD recorded above.
Origin `https://github.com/range-et/git-cad.git` verified read-only. #37 canonical
branding/distribution/command is Git CAD / git-cad. Legacy executable/launcher,
internal package, archive keys/paths, QSettings namespace and Git-rule sentinels
remain compatible. No client configuration, remote settings, commit or publication
was changed. Parent focused identity/icon/real-wheel/CLI/runtime suite:31 passed;
real MCP smoke:15 workflows passed. Independent QA:64 focused cases passed and
both installed entrypoints checked; independent UX naming scan found no residual
public mismatch in reviewed current instructions and UI. Historical reports keep
their original naming.

#38 legacy UI regressions reproduced mutable queued selections, hidden publication
warnings and stale preview completion replacing a newer selection. Deep recipe
copy, persistent publication notice and load-generation check fix these cases.
Real Qt/VTK `uv run python tests/integration/legacy_workflows.py` passed, including
immutable archives; independent deferred-handler rechecks passed. No live-native
claim follows from these UI tests.

Complete inventory diagnostic `20261109T221424.009028Z`:4,275/4,830 lines (88.51%),
555 missing, zero exclusions, stable source. All nine GUI suites, CLI and MCP
passed. Core:440 passed, one stale runner-test expectation failed because the new
legacy suite correctly appeared in the pending list after a simulated Qt abort.
The assertion was updated; focused runner/protocol/real tiny mutation-campaign
checks then passed18 cases. The combined result remains diagnostic, not green.

Independent recovery recheck:46 tests passed, plus both original P1 probes rerun
separately. Changed input during archive verification retained bytes/no receipt;
symlinked capture left external bytes and directory entries unchanged. The last
two recovery P1 findings are closed in this reviewed scope; final campaign gates
and ledger reconciliation remain pending. Cooperative immutable-ready semantics
remain the concurrency boundary.

Runner QA independently verified matched-baseline cache reuse and timeout scaling.
Its P3 evidence request was implemented: configured timeouts/workers and each
baseline's exit/elapsed/log/budget are persisted. A real tiny Mutmut/fresh-process
campaign is now tested end-to-end; this validates runner mechanics, not the full
project mutation score. Storage/library/verifier campaign remains diagnostic and
in progress; source edits during it prevent a final current-source claim.


Independent graph-survivor review classified the three remaining edits as
runtime-equivalent for accepted ordinary graph inputs: save-first edge construction
makes both changed sort predicates stable no-ops; changing `<` to `<=` only changes
the unique zero-distance candidate's secondary key. All three variants independently
passed13 graph tests/two snapshots;10,230 finite index-set/column combinations also
agreed. These are reviewed equivalents, never credited as kills. A frozen full
current-source campaign and executable disposition accounting remain pending.

Full selected gate `20261109T221931.509389Z`:457 core tests/four snapshots, CLI,
compatibility mutation, real distribution build/install/dual CLI and ui_smoke passed.
It stopped at ui_robustness exit1 with suppressed traceback; remaining eight checks
are pending. #39 tracks actionable exception reporting and reproduction. This is
not a successful full gate. Storage diagnostic was interrupted after26/4,263
candidates (18 killed,8 survived); earlier source edits mean no current-source
score. All unexecuted candidates remain unqualified. New nested-output and UTC
format regressions passed independently and are now durable tests.


## Final selected-gate recheck for this working-tree stage

`uv run python scripts/check.py --build --ui --mcp --mutation` passed all selected
checks in `build/qa/20261109T222731.086473Z/report.json`, with matching starting and
ending source state:461 core tests/four snapshots, CLI, actual git-cad wheel build/
install/both entrypoints, all nine GUI suites, real MCP, and compatibility mutation
55/57 kills (96.49%; two previously reviewed equivalents). No pending automated
checks in that selected gate. This is **not** the entire-project mutation score or
100% line coverage. The last complete-inventory diagnostic remains88.51%; newer
runner/protocol tests have not yet been remeasured in the combined inventory.

The prior ui_robustness exit1 did not reproduce standalone or in the full rerun.
Its hook now prints tracebacks as well as retaining callback failures. #39 remains
Watch because the original failure is unisolated. Closure of selected verified
issues in the ledgers reflects scoped outcomes, not release qualification.

Independent runner recheck:47 tests passed, including real miniature campaigns and
controlled baseline-timeout/cache probes. Durable tests now include the two control
probes plus nested publication-directory and UTC timestamp regressions. Final
ledger/report additions after the gate are documentation-only; whitespace/local
Markdown links checked separately. No commit, publication or client config edit.
