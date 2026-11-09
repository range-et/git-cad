"""Whole-source inventory and fresh-process mutation reports must fail closed."""

import importlib.util
import sys
from pathlib import Path

import pytest
from hypothesis import given
from test_verification_compatibility import JSON


def script(name):
    path = Path(__file__).resolve().parents[1] / "scripts" / (name + ".py")
    spec = importlib.util.spec_from_file_location("scripts." + name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


campaign = script("mutation_campaign")
coverage_gate = script("check_coverage")


def evidence(**changes):
    return {
        "source_sha256": "expected",
        "final_source_sha256": "expected",
        "mutant": "candidate",
        "source": "/sandbox/source.py",
        "imported_source": "/sandbox/source.py",
        "exit_code": 1,
        "hits": 1,
        "failed_tests": [
            {
                "nodeid": "tests/test_sample.py::test_loss",
                "phase": "call",
                "error": "assert original == current",
            }
        ],
        "collection_errors": [],
        "internal_errors": [],
        **changes,
    }


@pytest.mark.parametrize(
    "report,code",
    [
        (None, 1),
        ({}, 1),
        (evidence(source_sha256="wrong"), 1),
        (evidence(final_source_sha256="wrong"), 1),
        (evidence(mutant="wrong"), 1),
        (evidence(imported_source="/outside.py"), 1),
        (evidence(source="/outside.py"), 1),
        (evidence(exit_code=0), 1),
        (evidence(hits=0), 1),
        (evidence(hits=-1), 1),
        (evidence(hits=True), 1),
        (evidence(failed_tests=["invalid"]), 1),
        (evidence(failed_tests=[]), 1),
        (evidence(collection_errors=["collect failed"]), 1),
        (evidence(internal_errors=["internal error"]), 1),
        (evidence(exit_code=3), 3),
        (evidence(exit_code=-6), -6),
        (evidence(exit_code=True), True),
        (evidence(failed_tests=None), 1),
    ],
)
def test_mutation_gate_never_credits_unreliable_evidence(report, code):
    assert (
        campaign.classify(report, code, "expected", "candidate", "/sandbox/source.py")
        != "killed"
    )


def test_actual_hit_and_failed_runtime_assertion_can_earn_kill():
    assert (
        campaign.classify(evidence(), 1, "expected", "candidate", "/sandbox/source.py")
        == "killed"
    )
    assert (
        campaign.classify(
            evidence(exit_code=0, failed_tests=[]),
            0,
            "expected",
            "candidate",
            "/sandbox/source.py",
        )
        == "survived"
    )
    assert (
        campaign.classify(
            evidence(exit_code=0, hits=0, failed_tests=[]),
            0,
            "expected",
            "candidate",
            "/sandbox/source.py",
        )
        == "uncovered"
    )


@given(value=JSON)
def test_arbitrary_json_cannot_crash_mutation_report_parser(value):
    assert isinstance(
        campaign.classify(value, 1, "expected", "candidate", "/sandbox/source.py"), str
    )


@pytest.mark.parametrize("changes", [{"missing_lines": [4]}, {"excluded_lines": [4]}])
def test_coverage_gate_does_not_round_up_or_hide_lines(changes):
    data = {"missing_lines": [], "excluded_lines": [], **changes}
    with pytest.raises(ValueError):
        coverage_gate.validate_report(
            {"files": {"module.py": data}, "totals": {"covered_lines": 9999}},
            ["module.py"],
        )


def test_coverage_gate_requires_unimported_files_in_its_inventory():
    report = coverage_report()
    with pytest.raises(ValueError, match="inventory"):
        coverage_gate.validate_report(report, ["module.py", "unimported.py"])
    assert coverage_gate.validate_report(report, ["module.py"]) == 1


def test_production_inventory_includes_native_hooks_and_tools(tmp_path):
    names = [
        "src/cadgit/main.py",
        "src/cadgit/resources/hook.py",
        "scripts/check.py",
        "skills/cad-git/scripts/inspect.py",
    ]
    for name in names:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("pass\n")
    assert coverage_gate.production_files(tmp_path) == sorted(names)


def coverage_report():
    counts = {
        "covered_lines": 1,
        "num_statements": 1,
        "missing_lines": 0,
        "excluded_lines": 0,
    }
    return {
        "files": {
            "module.py": {
                "executed_lines": [1],
                "missing_lines": [],
                "excluded_lines": [],
                "summary": counts.copy(),
            }
        },
        "totals": counts.copy(),
    }


@pytest.mark.parametrize(
    "field,value",
    [
        ("executed_lines", None),
        ("executed_lines", [True]),
        ("executed_lines", [1, 1]),
        ("missing_lines", None),
        ("excluded_lines", False),
        ("summary", {}),
        ("summary", None),
    ],
)
def test_coverage_schema_rejects_missing_or_forged_counts(field, value):
    report = coverage_report()
    report["files"]["module.py"][field] = value
    with pytest.raises(ValueError):
        coverage_gate.validate_report(report, ["module.py"])


def test_coverage_totals_cannot_claim_unmeasured_lines():
    report = coverage_report()
    report["totals"]["covered_lines"] = 100
    with pytest.raises(ValueError):
        coverage_gate.validate_report(report, ["module.py"])


def test_coverage_fingerprint_detects_content_and_inventory_changes(tmp_path):
    source = tmp_path / "src/cadgit/core.py"
    source.parent.mkdir(parents=True)
    source.write_text("value=1")
    before = coverage_gate.source_fingerprint(tmp_path)
    source.write_text("value=2")
    assert coverage_gate.source_fingerprint(tmp_path) != before
    before = coverage_gate.source_fingerprint(tmp_path)
    (source.parent / "new.py").write_text("pass")
    assert coverage_gate.source_fingerprint(tmp_path) != before


def test_clean_baseline_requires_exact_source_and_no_failures():
    clean = evidence(mutant="", exit_code=0, failed_tests=[], hits=0)
    assert (
        campaign.classify(clean, 0, "expected", "", "/sandbox/source.py")
        == "baseline-passed"
    )
    assert (
        campaign.classify(
            {
                **clean,
                "failed_tests": [{"nodeid": "a", "phase": "call", "error": "failure"}],
            },
            0,
            "expected",
            "",
            "/sandbox/source.py",
        )
        != "baseline-passed"
    )


def test_coverage_fingerprint_includes_runtime_assets(tmp_path):
    asset = tmp_path / "src/cadgit/resources/colors.json"
    asset.parent.mkdir(parents=True)
    asset.write_text("{}")
    before = coverage_gate.source_fingerprint(tmp_path)
    asset.write_text('{"background":"black"}')
    assert coverage_gate.source_fingerprint(tmp_path) != before


@pytest.mark.parametrize("scenario", ["complete", "gap", "failure", "drift"])
def test_coverage_runner_measures_real_isolated_sources_and_rejects_false_success(
    tmp_path, monkeypatch, scenario
):
    import json
    import sys

    package = tmp_path / "src/cadgit"
    package.mkdir(parents=True)
    source = package / "sample.py"
    source.write_text(
        "value = 42\n" + ("if False:\n    value = 0\n" if scenario == "gap" else "")
    )
    # A runtime-false branch remains executable in coverage's static inventory.
    if scenario == "gap":
        source.write_text("value = 42\nif value == 0:\n    value = 1\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "conftest.py").write_text(
        'from hypothesis import settings\nsettings.register_profile("ci", max_examples=1)\n'
    )
    (tests / "test_sample.py").write_text(
        'import runpy\ndef test_value():\n    assert runpy.run_path("src/cadgit/sample.py")["value"] == '
        + ("0" if scenario == "failure" else "42")
        + "\n"
    )
    integration = tests / "integration"
    integration.mkdir()
    (integration / "cli_smoke.py").write_text(
        'import runpy\nrunpy.run_path("src/cadgit/sample.py")\n'
        + (
            'from pathlib import Path\nPath("src/cadgit/sample.py").write_text("value = 43\\n")\n'
            if scenario == "drift"
            else ""
        )
    )
    output = tmp_path / "build/report"
    monkeypatch.setattr(coverage_gate, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_coverage.py", "--output", str(output)])
    if scenario == "complete":
        assert coverage_gate.main() == 0
        report = json.loads((output / "coverage.json").read_text())
        assert (
            report["totals"]["covered_lines"] == report["totals"]["num_statements"] == 1
        )
    else:
        with pytest.raises(
            (ValueError, RuntimeError),
            match={
                "gap": "Uncovered",
                "failure": "measured suites failed",
                "drift": "Source changed",
            }[scenario],
        ):
            coverage_gate.main()
    assert (output / "coverage.json").is_file()
