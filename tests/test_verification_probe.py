"""Fresh-process probe evidence distinguishes real kills from infrastructure failures."""

import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
from mutmut.mutation.file_mutation import mutate_file_contents

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "scenario",
    ["baseline", "killed", "uncovered", "collection", "internal", "wrong-source"],
)
def test_real_probe_accounts_for_target_hits_and_failure_kind(tmp_path, scenario):
    generated = mutate_file_contents(
        "probe_target.py", "def accepts(value):\n    return value >= 0\n"
    )
    tree = ast.parse(generated.code)
    candidate = next(
        node.name
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and "__mutmut_" in node.name
        and not node.name.endswith("orig")
        and any(isinstance(part, ast.Gt) for part in ast.walk(node))
    )
    target = tmp_path / "probe_target.py"
    target.write_text(generated.code)
    conftest = 'from hypothesis import settings\nsettings.register_profile("ci",max_examples=1)\n'
    if scenario == "internal":
        conftest += 'def pytest_sessionstart(session):\n    raise RuntimeError("Injected pytest infrastructure error")\n'
    (tmp_path / "conftest.py").write_text(conftest)
    test = "import probe_target\ndef test_boundary():\n    assert probe_target.accepts(0)\n"
    if scenario == "uncovered":
        test = "import probe_target\ndef test_unrelated():\n    assert True\n"
    elif scenario == "collection":
        test = 'raise RuntimeError("Injected collection failure")\n'
    elif scenario == "wrong-source":
        outside = tmp_path / "outside.py"
        outside.write_text("def accepts(value):return True\n")
        test = (
            'import importlib.util,sys\nspec=importlib.util.spec_from_file_location("probe_target",'
            + repr(str(outside))
            + ')\nmodule=importlib.util.module_from_spec(spec)\nsys.modules["probe_target"]=module\nspec.loader.exec_module(module)\ndef test_outside():\n    assert module.accepts(0)\n'
        )
    tests = tmp_path / "test_boundary.py"
    tests.write_text(test)
    report = tmp_path / "report.json"
    mutant = "" if scenario == "baseline" else "probe_target." + candidate
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/mutation_probe.py"),
            "--source",
            str(target),
            "--module",
            "probe_target",
            "--mutant",
            mutant,
            "--report",
            str(report),
            str(tests),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert report.exists(), result.stderr
    evidence = json.loads(report.read_text())
    expected_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    assert evidence["source_sha256"] == evidence["final_source_sha256"] == expected_hash
    assert evidence["exit_code"] == result.returncode
    assert evidence["mutant"] == mutant and evidence["source"] == str(target)
    if scenario == "baseline":
        assert result.returncode == 0 and not evidence["failed_tests"]
        assert evidence["tests_by_function"] and evidence["test_durations"]
    elif scenario == "killed":
        assert result.returncode == 1 and evidence["hits"] > 0
        assert evidence["failed_tests"][0]["phase"] == "call"
        assert "assert" in evidence["failed_tests"][0]["error"]
        assert not evidence["internal_errors"] and not evidence["collection_errors"]
    elif scenario == "uncovered":
        assert result.returncode == 0 and evidence["hits"] == 0
    elif scenario == "collection":
        assert evidence["collection_errors"] and not evidence["failed_tests"]
    elif scenario == "internal":
        assert evidence["internal_errors"] and result.returncode == 3
    else:
        assert evidence["imported_source"] == str(tmp_path / "outside.py")
        assert (
            "Target imported outside isolated generated source"
            in evidence["internal_errors"]
        )
        assert evidence["hits"] == 0


@pytest.mark.parametrize("mutated", [False, True], ids=["baseline", "candidate"])
def test_onboarding_loader_supplies_exact_skill_module_to_real_probe(tmp_path, mutated):
    module = "cadgit_skill.inspect_folder"
    relative = Path("skills/cad-git/scripts/inspect_folder.py")
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    generated = mutate_file_contents(str(relative), (ROOT / relative).read_text())
    target.write_text(generated.code)
    tests = tmp_path / "tests"
    tests.mkdir()
    for filename in ("test_skill_onboarding.py", "test_history.py"):
        (tests / filename).write_bytes((ROOT / "tests" / filename).read_bytes())
    (tests / "conftest.py").write_text(
        'from hypothesis import settings\nsettings.register_profile("ci", max_examples=1)\n'
    )
    broken_input = re.search(
        r"^def (x_inspect_folder__mutmut_\d+)\([^\n]*\):\n    root=Path\(None\)",
        generated.code,
        re.MULTILINE,
    )
    assert broken_input, (
        "Expected a generated mutation that discards the selected folder"
    )
    mutant = module + "." + broken_input.group(1) if mutated else ""
    report = tmp_path / "report.json"
    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/mutation_probe.py"),
            "--source",
            str(target),
            "--module",
            module,
            "--mutant",
            mutant,
            "--report",
            str(report),
            str(tests / "test_skill_onboarding.py"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert report.exists(), process.stdout + process.stderr
    evidence = json.loads(report.read_text())
    from test_verification_campaign import campaign

    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    status = campaign.classify(
        evidence, process.returncode, digest, mutant, str(target)
    )
    assert evidence["imported_source"] == str(target)
    if mutated:
        assert evidence["hits"] > 0
        assert status == "killed", evidence
    else:
        assert status == "baseline-passed", evidence
        assert any(
            name.startswith(module + ".") for name in evidence["tests_by_function"]
        )
