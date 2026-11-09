# Layered test verification

Implemented locally on 2026-11-09 under former ledger L13. This is a bounded starting
scope, not repository-wide strict typing, exhaustive fuzzing or a correctness
proof. Existing example-based, graphical and native checks remain necessary.

## Run the gates

```sh
uv sync --frozen --extra dev --extra mcp
uv run python scripts/check.py --build --mcp --mutation
# In an active graphical session:
uv run python scripts/check.py --build --ui --mcp --mutation
# Longer exploratory generated-input run (not a release gate):
uv run pytest tests/test_verification_compatibility.py tests/test_verification_models.py --hypothesis-profile=deep
```

The default runner adds scoped Ruff lint/format and strict mypy checks before
pytest. Core pytest uses the reproducible `ci` Hypothesis profile and emits
coverage XML in its report directory. Coverage is diagnostic, with no arbitrary
repository-wide percentage threshold. The opt-in `--mutation` gate is enabled
in hosted CI alongside build and real stdio MCP smoke. Hosted GUI/native gates
remain separate; branch protection is an administrator setting.

| Layer | Executable scope | Boundary |
| --- | --- | --- |
| Static | Ruff E4/E7/E9/F/B/C4/I and formatting for compatibility/errors, new verification tests/conftest and mutation runner; strict mypy for compatibility/errors | Existing untyped UI, storage and native modules are not claimed strict. Explicit files are in pyproject.toml. |
| Runtime contracts | Existing Pydantic Selection validation, finite three-coordinate translation, independent defaults, exact revision strings and additive-data preservation | No new runtime decorators or changes to durable schema/coercion. |
| Generated cases | JSON trees up to 20 leaves, list/dict children up to 5, feature lists up to 8; arbitrary integers, finite floats and Unicode; translation lengths 0–6 | CI permits up to 100 examples per property plus explicit examples; deep permits 1000. Not an exhaustive domain or storage state machine. |
| Mutation | Mutmut 3.8.1, compatibility function only, dedicated compatibility tests; fresh temporary copy, two workers, 95% killed/total floor | Empty/incomplete/malformed reports, uncovered/skipped/suspicious/timeout/interrupted/crashed mutants fail. Equivalent survivors stay in denominator. Module-level constants and other modules are outside this audit. |
| Regression | Two Syrupy snapshots of existing V1 Snapshot/Assembly fixture serialization, including unknown nested fields | No timestamp or ID scrubbing; no native renderer or HTTP recording claims. |

Hypothesis CI examples are reproducible for a fixed test source, Python and
lockfile. Local/default runs retain example discovery; `deep` is exploratory.
See [Hypothesis profiles](https://hypothesis.readthedocs.io/en/latest/settings.html)
and [Mutmut configuration](https://mutmut.readthedocs.io/en/latest/index.html).
The mutation gate uses the installed 3.x commands and structured statistics;
it does not use obsolete diff-path CLI options or count timeouts as kills.

## Reviewing regressions

A snapshot mismatch fails normal pytest. Only update after understanding the
contract change, then inspect the small checked-in `.ambr` diff:

```sh
uv run pytest tests/test_verification_models.py --snapshot-update
uv run python scripts/check_mutations.py
```

The runner never updates snapshots. The standalone mutation command also runs
clean tests and Mutmut's forced-failure probe, prints survivor IDs and statistics,
and removes its temporary workspace. To investigate individual mutation diffs:

```sh
uv run mutmut run --max-children 2
uv run mutmut results
uv run mutmut show cadgit.compatibility.x_check_compatibility__mutmut_7
```

Do not apply mutants to the working package. Local `mutants/`, coverage and tool
caches are ignored. The gate's fresh copy avoids stale mutation scores.

The first audit killed 55/57 mutants (96.49%). Two equivalent survivors were
inspected: `cast(dict[str, object], data)` → `cast(None, data)` is runtime-neutral;
missing `schema_minor` default 0 → 1 leaves acceptance unchanged and writes no
data. IDs 7 and 27 are version/source-specific. No semantic survivor was waived.
A future surviving mutation still needs review even if the numeric floor passes.

## Remaining work

[GitHub #14](https://github.com/range-et/git-cad/issues/14) tracks broader static adoption, persistent-history state-machine
properties and wider mutation/serialization coverage. Semgrep/Bandit, additional
contract frameworks, native fuzzing and network cassette tools are not installed
as placeholders: add them when a concrete boundary and failure oracle justify
them. No external HTTP API exists in this scoped contract to record.
See [review evidence](REVIEW_TEST_VERIFICATION.md) and [build gates](BUILD_GATES.md).

## Testing the survivor assessment (#15)

`tests/test_verification_survivors.py` exercises the exact two reviewed source
edits without altering the working package. It compares acceptance, complete
rejection messages and unchanged inputs against the baseline for bounded JSON
cases (CI: up to 100 per survivor plus explicit cases; deep: up to 1000).
The domain includes arbitrary JSON, valid records with unknown data, individually
malformed fields, missing minor versions and legacy defaults.

An isolated strict-mypy check accepts the baseline and minor-default variant but
rejects the cast-target variant (`None` has no attribute `get`). Thus the cast
survivor is runtime-equivalent but caught by the separate static layer. The
reported Mutmut score remains 55/57: it measures the runtime test selection only.

Three behavior-changing controls must fail the existing independent oracle:
missing minor default −1, accepting minor −1, and treating boolean major `True`
as integer version 1. A baseline pass is required first. These controls keep the
comparison from being a test that accepts every variant. Exact-source guards fail
if the relevant implementation changes; no persistent waiver uses numeric IDs.

```sh
uv run pytest -q tests/test_verification_survivors.py --hypothesis-profile=ci
```

The remaining minor-default variant changes no observable result for ordinary
JSON records: explicit minors are unaffected, both absent defaults are valid,
and the validator returns no value or modified record. The generated test is
bounded corroborating evidence, not an exhaustive proof. No implementation-detail
assertion was added solely to force a runtime-equivalent mutant to fail.

## Entire-project campaign ([GitHub #15](https://github.com/range-et/git-cad/issues/15), in progress)

The current target includes every production Python file under `src/cadgit`,
`scripts` and `skills/cad-git/scripts`, including native hooks and unimported files.
Measure the current gaps with:

```sh
uv run python scripts/check_coverage.py --ui --mcp --report-only
```

Omit `--report-only` to require exactly zero missing/excluded executable lines,
consistent raw counts and the complete file inventory. Reports live under ignored
`build/coverage/`; running suites must succeed and source/tests/runtime assets must
remain unchanged. A diagnostic report is not a passed 100% gate. GUI and native
qualification boundaries still apply.

Fresh-process mutation diagnostics avoid this host's native-library fork crashes:

```sh
uv run python scripts/mutation_campaign.py \
  --module cadgit.history_graph \
  --tests tests/test_history_graph.py tests/test_verification_history_sequences.py \
  --output build/mutation-history-graph --workers 3
```

Output must be a new directory outside input trees. Repeat `--module` for more
targets. `--limit` and `--candidate-list` are diagnostic subsets and retain all
unexecuted candidates in the denominator. A kill needs a matched clean baseline,
an exact executed mutant, an ordinary test failure, consistent source provenance,
and unchanged original/generated workspaces. Timeout, crash, missing coverage,
equivalent mutation and omitted Mutmut syntax are not kills. Zero candidates never
qualify as complete. This runner does not yet provide repository-wide completion;
see [current evidence and remaining work](REVIEW_FULL_VERIFICATION.md).

The icon builder now accepts `--resources PATH` for generating assets in a
disposable directory containing `cad-git.svg`; normal invocation uses bundled
resources. Tests render real PNG/ICNS outputs without replacing repository assets.
