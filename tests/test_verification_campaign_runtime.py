"""Exercise actual fresh-process mutation orchestration on a tiny temporary project."""

import json
import sys
from pathlib import Path

import pytest
from test_verification_campaign import script


@pytest.mark.parametrize(
    "mode", ["killed", "survived", "uncovered", "baseline-failed", "limited"]
)
def test_real_campaign_accounts_for_every_candidate(tmp_path, monkeypatch, mode):
    runner = script("mutation_campaign")
    root = tmp_path / "project"
    for directory in ["src/cadgit", "tests", "scripts", "skills", "docs"]:
        (root / directory).mkdir(parents=True)
    (root / "src/cadgit/__init__.py").write_text("")
    (root / "tests/conftest.py").write_text(
        "from hypothesis import settings\nsettings.register_profile('ci', max_examples=5)\n"
    )
    (root / "src/cadgit/tiny.py").write_text("def value(x):\n    return x + 1\n")
    (root / "tests/test_tiny.py").write_text(
        "from cadgit.tiny import value\ndef test_value():\n    assert value(3) == 4\n    assert value(0) == 1\n"
    )
    if mode == "survived":
        (root / "tests/test_tiny.py").write_text(
            "from cadgit.tiny import value\ndef test_value():\n    value(3)\n"
        )
    elif mode == "uncovered":
        (root / "tests/test_tiny.py").write_text(
            "from cadgit.tiny import value\ndef test_value():\n    assert callable(value)\n"
        )
    elif mode == "baseline-failed":
        (root / "tests/test_tiny.py").write_text(
            "from cadgit.tiny import value\ndef test_value():\n    assert value(3) == 999\n"
        )
    (root / "scripts/mutation_probe.py").write_bytes(
        (Path(__file__).resolve().parents[1] / "scripts/mutation_probe.py").read_bytes()
    )
    (root / "pyproject.toml").write_text("[tool.pytest.ini_options]\n")
    output = tmp_path / "result"
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mutation_campaign.py",
            "--module",
            "cadgit.tiny",
            "--tests",
            "tests/test_tiny.py",
            "--output",
            str(output),
            "--timeout",
            "20",
            "--baseline-timeout",
            "20",
        ],
    )
    if mode == "limited":
        sys.argv.extend(["--limit", "1"])
    if mode == "baseline-failed":
        with pytest.raises(RuntimeError, match="baseline failed"):
            runner.main()
        report = json.loads((output / "report.json").read_text())
        assert report["result"] == "baseline failed" and not report["results"]
        assert report["baseline_runs"][0]["exit_code"] == 1
        return
    result = runner.main()
    report = json.loads((output / "report.json").read_text())
    assert result == (0 if mode == "killed" else 1), report
    assert report["generated_candidates"] > 0
    assert (
        len(report["results"]) + len(report["pending_candidates"])
        == report["generated_candidates"]
    )
    if mode == "limited":
        assert len(report["results"]) == 1 and report["pending_candidates"]
    else:
        assert report["pending_candidates"] == []
    assert {r["status"] for r in report["results"]} == {
        "killed" if mode == "limited" else mode
    }
    assert report["baseline_timeout_seconds"] == 20
    assert all(run["exit_code"] == 0 for run in report["baseline_runs"])
    assert report["source_unchanged"] and report["workspace_unchanged"]
