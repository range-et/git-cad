# Git CAD engineering workflow

Read [docs/BUILD_GATES.md](docs/BUILD_GATES.md) before implementation or release.
The CLI, UI and optional MCP share a local immutable history model. Preserve
original files, exact revision dependencies, unknown additive fields and existing
meaning. Use temporary projects for tests; never fabricate historical records.

## Tracking documents and document hygiene

Read [features.md](features.md) and the relevant [GitHub Issues](https://github.com/range-et/git-cad/issues) before planning changes.
GitHub Issues is the sole authoritative tracker for open bugs, investigations,
roadmap ideas, priorities, status and next actions. Do not recreate issues.md or
maintain another local backlog. Use features.md for implemented capabilities and
dated completion history. Detailed designs, experiments and review evidence stay
in docs/ and are linked from GitHub issues and completion entries. The
specification records intent, not proof of implementation.

- Before work, search GitHub Issues for an existing item; create one if needed.
  Triage its status, priority, scope and next action. Distinguish reproduced defects
  from hypotheses, roadmap ideas and deferred scope. Include evidence/reproduction
  and observable acceptance criteria; avoid duplicates.
- Implement the issue's agreed scope and run the applicable checks and independent
  reviews. Update its GitHub status and evidence as work progresses. Partial fixes
  keep a narrowly scoped issue open and link completed work and remaining actions.
- Once the work is verified, add the implemented outcome to features.md History,
  linking the GitHub issue, implementation commit/PR and detailed evidence. Record
  limitations, test commands/results, source revision or local working-tree scope,
  and hardware/runtime where relevant. Then close the GitHub issue with completion
  evidence. Do not close an issue just because a handler test or partial fix passed.
- Update user-facing instructions in the same change. Do not claim planned,
  unpublished or separately tested backend work is an available product feature.
  Keep one authoritative open-work status on GitHub; link detailed design notes
  rather than duplicating backlogs. Preserve historical reports as dated evidence.
- Before handoff, check changed Markdown links and git diff whitespace, reconcile
  counts/claims with actual evidence, and state pending gates. Do not put large
  generated artifacts, model weights or machine-only logs in tracking documents.
- Use GitHub issue URLs/numbers for new references. Historical ledger IDs are
  distinct and remain traceable through [the migration map](docs/ISSUE_MIGRATION.md).

## User-workflow test coverage

For UI/workflow changes consult [docs/UX_TEST_MATRIX.md](docs/UX_TEST_MATRIX.md).
Extend its action/state model and durable tests for new actions and confirmed bugs.
Cover success, cancellation, rejection and recovery; when asynchronous, change or
close the initiating context and assert frozen targets and immutable history.
Report finite generated domains and remaining gaps explicitly. A human/AI UX audit
complements deterministic tests; it does not replace running them. Full automated
workflow validation: `uv run python scripts/check.py --build --ui --mcp` after
installing development and MCP extras. Never call partial/manual/native coverage
passed because a handler test or mocked adapter passed.

## Review and verification

- State acceptance criteria and affected workflows before a substantial change.
- For changes to persistence, lineage, compatibility, native adapters, threading
  or publication, delegate an independent architecture audit to a subagent.
- For substantial UI/workflow/viewport changes, delegate an independent UI/UX
  audit to a different subagent. Reviewers should inspect the implementation and
  exercise relevant failure paths; a spec review alone is not a code audit.
- For a release candidate or a cross-cutting feature, also use an independent QA
  reviewer to run the relevant build gates and inspect evidence. The implementer
  remains responsible for integrating fixes and final verification.
- Reviewers report findings with priority, reproduction, affected paths and
  suggested verification. Default to read-only review to avoid overlapping edits.
  Fix confirmed blockers, add meaningful regressions, and ask the originating
  reviewer to recheck their findings after fixes.
- No known P0/P1 may be called release-ready. Track P2/P3 disposition explicitly.
  Missing GUI/native environments mean an applicable gate is pending, not passed.
  If agents are unavailable, record the missing independent review honestly.
- Run `uv run python scripts/check.py --build` for a candidate build. Add `--ui`
  for UI/viewport changes and releases, using an active graphical session. Run
  native-app probes when adapter behavior changes; use isolated native processes
  and temporary files wherever possible.
- Save review/QA evidence using `docs/REVIEW_TEMPLATE.md`. Record the commit or
  diff under review, commands, results, fix/recheck status and limitations.
  Rerun affected gates after fixes; old green results do not validate new code.
- Small documentation or cosmetic changes need proportional checks, not an
  automatic multi-agent review. Do not require user confirmation for routine
  reviews, tests or reversible fixes already within the task.

The check runner reports automated checks only. Independent review and live-native
validation are separate release gates. Do not claim they passed because CI is green.
Do not commit, publish or modify client configuration unless the user authorizes it.
