"""Independent runner-control probes; mocked subprocess results are not mutation evidence."""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from test_verification_campaign import script


def project(tmp_path):
    root = (tmp_path / "project").resolve()
    for folder in ["src/cadgit", "tests", "scripts", "skills", "docs"]:
        (root / folder).mkdir(parents=True, exist_ok=True)
    (root / "src/cadgit/probe.py").write_text(
        "def first():\n    return 1\n\ndef second():\n    return 2\n"
    )
    return root


def arguments(output):
    return [
        "campaign",
        "--module",
        "cadgit.probe",
        "--tests",
        "tests/test_probe.py",
        "--output",
        str(output),
        "--timeout",
        "2",
        "--baseline-timeout",
        "9",
    ]


def test_baseline_cache_reuses_identical_scope_and_preserves_budgets(
    tmp_path, monkeypatch
):
    runner = script("mutation_campaign")
    root = project(tmp_path)
    output = tmp_path / "output"
    calls = []

    def probe(workspace, arguments, log, timeout, stop=None):
        def arg(name):
            return arguments[arguments.index(name) + 1]

        target = Path(arg("--source"))
        name = arg("--mutant")
        report = Path(arg("--report"))
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        calls.append((name, timeout, "--inventory" in arguments))
        data = {
            "mutant": name,
            "source": str(target),
            "imported_source": str(target),
            "source_sha256": digest,
            "final_source_sha256": digest,
            "exit_code": 1 if name else 0,
            "hits": 1 if name else 0,
            "failed_tests": [
                {
                    "nodeid": "tests/test_probe.py::test_both",
                    "phase": "call",
                    "error": "controlled assertion",
                }
            ]
            if name
            else [],
            "collection_errors": [],
            "internal_errors": [],
        }
        if "--inventory" in arguments:
            ids = json.loads((output / "report.json").read_text())["candidate_ids"]
            data["tests_by_function"] = {
                i.rsplit("__mutmut_", 1)[0] + "__mutmut_": [
                    "tests/test_probe.py::test_both"
                ]
                for i in ids
            }
            data["test_durations"] = {"tests/test_probe.py::test_both": 0.01}
        report.write_text(json.dumps(data))
        return data["exit_code"], 7.0

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "run_probe", probe)
    monkeypatch.setattr(sys, "argv", arguments(output))
    assert runner.main() == 0
    baselines = [c for c in calls if not c[0]]
    mutants = [c for c in calls if c[0]]
    assert len(baselines) == 2
    assert all(c[1] == 9 for c in baselines)
    assert mutants and all(c[1] == 21 for c in mutants)
    reused = [
        p
        for p in output.glob("*/baseline.json")
        if "reused_from" in json.loads(p.read_text())
    ]
    assert len(reused) == 1
    report = json.loads((output / "report.json").read_text())
    assert report["workers"] == 2
    assert report["timeout_seconds"] == 2
    assert report["baseline_timeout_seconds"] == 9
    assert len(report["baseline_runs"]) == 2
    assert all(
        r["exit_code"] == 0 and r["seconds"] == 7.0 and r["timeout_seconds"] == 9
        for r in report["baseline_runs"]
    )


def test_timed_out_baseline_retains_budget_and_no_kills(tmp_path, monkeypatch):
    runner = script("mutation_campaign")
    root = project(tmp_path)
    output = tmp_path / "output"
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "run_probe", lambda *args: (None, 9.01))
    monkeypatch.setattr(sys, "argv", arguments(output))
    with pytest.raises(RuntimeError, match="baseline failed"):
        runner.main()
    report = json.loads((output / "report.json").read_text())
    assert report["result"] == "baseline failed"
    assert report["results"] == []
    assert report["baseline_runs"] == [
        {
            "log": str(output / "baseline.log"),
            "exit_code": None,
            "seconds": 9.01,
            "timeout_seconds": 9,
        }
    ]
