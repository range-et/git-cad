"""Fresh, isolated compatibility mutation audit with a fail-closed 95% kill gate."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COUNTS = (
    "killed",
    "survived",
    "no_tests",
    "skipped",
    "suspicious",
    "timeout",
    "check_was_interrupted_by_user",
    "segfault",
)


def validate_stats(stats: dict[str, object]) -> float:
    """Unfinished, malformed and empty reports must never produce green evidence."""
    for name in (*COUNTS, "total"):
        if type(stats.get(name)) is not int or stats[name] < 0:
            raise ValueError(f"Invalid mutation count: {name}")
    total = stats["total"]
    if total == 0 or sum(stats[name] for name in COUNTS) != total:
        raise ValueError("Empty or incomplete mutation report")
    if any(stats[name] for name in COUNTS if name not in {"killed", "survived"}):
        raise ValueError("Unresolved mutation outcomes (not counted as kills)")
    score = 100 * stats["killed"] / total
    if score < 95:
        raise ValueError(f"Mutation kill score {score:.2f}% is below 95%")
    return score


def main() -> int:
    # Never mutate the working package or reuse stale results. Use the same
    # installed dependencies, but copy sources/tests into a disposable workspace.
    with tempfile.TemporaryDirectory(prefix="cadgit-mutation-") as temporary:
        workspace = Path(temporary)
        for directory in ("src", "tests"):
            shutil.copytree(
                ROOT / directory,
                workspace / directory,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        shutil.copy2(ROOT / "pyproject.toml", workspace / "pyproject.toml")
        for command in (
            ["run", "--max-children", "2"],
            ["results"],
            ["export-cicd-stats"],
        ):
            subprocess.run(
                [sys.executable, "-m", "mutmut", *command], cwd=workspace, check=True
            )
        stats = json.loads((workspace / "mutants/mutmut-cicd-stats.json").read_text())
        print(json.dumps(stats, indent=2), flush=True)
        print(
            f"Compatibility mutation kill score: {validate_stats(stats):.2f}%",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
