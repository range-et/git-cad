"""External runtime diagnostics cannot claim enabled inference or crash on bad JSON."""

import json
import subprocess
from types import SimpleNamespace

import pytest

import cadgit.brep as brep


def checkout(tmp_path):
    root = tmp_path / "provider"
    root.mkdir()
    for name in (
        "ae_reconstruct.py",
        "rebuild.py",
        "postprocess.py",
        "config_pc.yaml",
        "checkpoints/pc_vae.ckpt",
        "checkpoints/parametrizer.ckpt",
    ):
        path = root / name
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(b"diagnostic presence fixture; not a working provider")
    return root


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        3,
        {"cuda": "yes", "mps": False, "missing": []},
        {"cuda": True, "mps": False, "missing": "invalid"},
    ],
)
def test_bad_external_runtime_report_is_actionable_and_cannot_enable_execution(
    tmp_path, monkeypatch, payload
):
    monkeypatch.setattr(
        brep.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=0, stdout="CADGIT_RUNTIME=" + json.dumps(payload), stderr=""
        ),
    )
    result = brep.runtime_status(tmp_path / "python", None)
    assert not result["execution_available"] and not result["cuda_prerequisites_ready"]
    assert any("Invalid runtime probe report" in error for error in result["missing"])


def test_ready_cuda_prerequisites_are_not_an_enabled_inference_adapter(
    tmp_path, monkeypatch
):
    root = checkout(tmp_path)

    def run(command, **kwargs):
        if command[0] == "git":
            return SimpleNamespace(returncode=0)
        return SimpleNamespace(
            returncode=0,
            stdout="noise\nCADGIT_RUNTIME="
            + json.dumps(
                {
                    "cuda": True,
                    "mps": False,
                    "missing": [],
                    "torch": "fixture",
                    "execution_available": True,
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(brep.subprocess, "run", run)
    monkeypatch.setattr(
        brep.subprocess, "check_output", lambda *args, **kwargs: brep.REVISION + "\n"
    )
    result = brep.runtime_status(tmp_path / "python", root)
    assert result["cuda_prerequisites_ready"] and result["cuda"]
    assert not result["execution_available"]
    assert result["checkout_revision"] == brep.REVISION and result["missing"] == []


@pytest.mark.parametrize(
    "failure",
    [OSError("Interpreter missing"), subprocess.TimeoutExpired("probe", 45), None],
)
def test_failed_runtime_or_checkout_probes_report_missing_prerequisites(
    tmp_path, monkeypatch, failure
):
    root = checkout(tmp_path)
    (root / "config_pc.yaml").unlink()

    def run(command, **kwargs):
        if command[0] == "git":
            return SimpleNamespace(returncode=1)
        if failure:
            raise failure
        return SimpleNamespace(returncode=1, stdout="", stderr="Bad interpreter")

    monkeypatch.setattr(brep.subprocess, "run", run)
    monkeypatch.setattr(
        brep.subprocess, "check_output", lambda *args, **kwargs: "different-revision\n"
    )
    result = brep.runtime_status(tmp_path / "python", root)
    assert not result["execution_available"] and not result["cuda_prerequisites_ready"]
    assert "Missing config_pc.yaml" in result["missing"]
    assert "Checkout differs from inspected upstream revision" in result["missing"]
    assert (
        "Upstream checkout has tracked modifications or cannot be checked"
        in result["missing"]
    )
    monkeypatch.setattr(
        brep.subprocess,
        "check_output",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.CalledProcessError(1, "git")
        ),
    )
    assert (
        "Cannot identify upstream checkout revision"
        in brep.runtime_status(None, root)["missing"]
    )
