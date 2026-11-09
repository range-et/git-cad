# PR #1 merge findings — 2026-11-09

Status: both specified findings verified fixed; existing broader qualification limits remain.

- Scope: native-material completion warnings (#40) and canonical skill mutation
  loader identity (#41). Existing archives, input files and exact-file probe checks
  must remain unchanged. No new native renderer or GUI behavior is claimed.
- Base: `455f02d7abbc8b97ebccc73233c224525cf05ed1`, branch
  `codex/verification-hardening-git-cad`; local diff includes the two fixes,
  focused regressions and ledger/review updates.
- Runtime: macOS arm64, Python 3.12.4; existing development/MCP environment.
- Architecture reviewer: independent `full_architecture_audit`, publication
  warnings, combined sync/event faults and archive immutability.
- QA reviewer: independent `full_qa_audit`, real skill probe identity and strict
  provenance. UI/UX review is not applicable to this focused diff (no widget or
  interaction changes).

| Priority | Finding and reproduction | Fix | Regression |
| --- | --- | --- | --- |
| P2 / #40 | Native material commit results were discarded; three failure-injection cases lost warnings while one clean control passed. | Collect warnings with material revision IDs, then combine with the snapshot's completion warning after its commit. Only the returned result is augmented. | Two real material archives, material sync/event failures, snapshot sync failure, clean capture/reuse, unchanged source and manifest bytes, and no warnings persisted in manifests. |
| P2 / #41 | Canonical skill probe baseline and candidate both observed imported_source=None with the actual onboarding test loader. | Register cadgit_skill.inspect_folder in sys.modules before executing that exact file. The probe and classifier are unchanged. | Fresh-process actual generated skill baseline plus Path(None) mutant; copied real onboarding tests; existing wrong-source rejection regression. |

## Gate results

- Red regressions: material cases 3 failed/1 passed; skill cases 2 failed.
- Fixed focused suite: `uv run pytest -q tests/test_verification_storage.py
  tests/test_skill_onboarding.py tests/test_verification_probe.py` —80 passed.
- Actual runner: `uv run python scripts/mutation_campaign.py --module
  cadgit_skill.inspect_folder --tests tests/test_skill_onboarding.py
  --candidate-list /tmp/git-cad-pr1-skill-candidate.json --output
  build/mutation-pr1-skill-fix --workers 1 --timeout 30 --baseline-timeout 60`.
  Candidate list selects `cadgit_skill.inspect_folder.x_inspect_folder__mutmut_4`
  (selected folder replaced by None). Initial and matched baselines passed;
  selected candidate killed; source/workspace hashes stable. Exit1 is expected:
  one of326 candidates selected,325 remain pending. This is not a complete skill
  mutation score.
- `uv run python scripts/check.py --build`: all9 selected checks passed in
  `build/qa/20261109T224643.588321Z/report.json`, with stable source state:
  467 core tests/four snapshots, scoped lint/format/types, CLI smoke, distribution
  build, isolated wheel install and both executable entrypoints.
- Independent architecture:80 focused tests passed plus a stricter real-project
  combined fault probe. Both sync/event failures for each of two materials and
  both snapshot sync/event failures retained all six messages; no manifest/input
  rewriting and no stale warning on clean reuse. No actionable finding remained.
- Independent QA:53 tests passed across probe/onboarding/campaign cases; canonical
  source identity, hash stability, call-phase killed-mutant failure and wrong-source
  rejection verified. No actionable finding remained in the scoped fix.
- Native applications, GUI suites and MCP protocol were not rerun for this diff:
  no native adapter, widget, renderer or MCP interface changed; the warning test
  uses temporary opaque material payloads and does not qualify native appearance.
- Final whitespace and changed Markdown link checks passed. Ledger/review updates
  after the build run are documentation-only.

## Remaining limits

This fixes the two specified PR findings only. Project-wide 100% coverage/mutation
completion (#16), the earlier intermittent GUI investigation (#39), and previously
recorded native qualification limits remain open. No merge or release is authorized
by this review. The user authorized committing and pushing these fixes to PR #1.
