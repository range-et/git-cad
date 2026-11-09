"""Build/install/import the actual wheel in a temporary destination."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_real_wheel_contains_runtime_resources_and_loadable_entrypoint(tmp_path):
    dist = tmp_path / "dist"
    installed = tmp_path / "installed"

    def run(command):
        result = subprocess.run(
            command, cwd=ROOT, capture_output=True, text=True, timeout=90
        )
        assert result.returncode == 0, result.stdout + "\n" + result.stderr
        return result

    run(["uv", "build", "--out-dir", str(dist)])
    wheels = list(dist.glob("*.whl"))
    assert len(wheels) == 1
    run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            "--no-deps",
            "--target",
            str(installed),
            str(wheels[0]),
        ]
    )
    # Preserve isolated import checking while allowing the complete-inventory
    # coverage runner to instrument the real checker in this subprocess.
    prefix = [sys.executable, "-I"]
    if os.environ.get("COVERAGE_RCFILE"):
        prefix += ["-m", "coverage", "run"]
    result = run([*prefix, str(ROOT / "scripts/check_wheel.py"), str(installed)])
    assert "cad-git" in result.stdout
