"""Measure the complete production/tool inventory; never omit unimported files."""

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI_SUITES = (
    "ui_smoke",
    "ui_robustness",
    "material_library_smoke",
    "texture_preview_smoke",
    "viewport_responsiveness",
    "brep_preparation_smoke",
    "workflow_combinations",
    "dialog_workflows",
    "legacy_workflows",
)


def production_files(root=ROOT):
    return sorted(
        str(p.relative_to(root))
        for folder in [
            root / "src/cadgit",
            root / "scripts",
            root / "skills/cad-git/scripts",
        ]
        for p in folder.rglob("*.py")
    )


def source_fingerprint(root=ROOT):
    digest = hashlib.sha256()
    paths = {
        str(p.relative_to(root))
        for directory in ("src", "scripts", "skills")
        for p in (root / directory).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    paths.update(
        str(p.relative_to(root))
        for p in (root / "tests").rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    )
    paths.update(
        name for name in ("pyproject.toml", "uv.lock") if (root / name).is_file()
    )
    for name in sorted(paths):
        digest.update(name.encode() + b"\0")
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def execute(command, stream, env, timeout):
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=stream,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    try:
        return process.wait(timeout=timeout)
    except BaseException:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        raise


def validate_report(report, expected):
    if not isinstance(report, dict) or not isinstance(report.get("files"), dict):
        raise ValueError("Malformed coverage report")
    files = report["files"]
    if set(files) != set(expected):
        raise ValueError(
            "Coverage file inventory differs from production source inventory"
        )
    totals = {
        "covered_lines": 0,
        "num_statements": 0,
        "missing_lines": 0,
        "excluded_lines": 0,
    }
    for name, data in files.items():
        if not isinstance(data, dict):
            raise ValueError("Malformed file coverage: " + name)
        lines = {}
        for field in ("executed_lines", "missing_lines", "excluded_lines"):
            value = data.get(field)
            if (
                not isinstance(value, list)
                or any(type(n) is not int or n <= 0 for n in value)
                or len(set(value)) != len(value)
            ):
                raise ValueError("Malformed line inventory: " + name)
            lines[field] = set(value)
        if lines["executed_lines"] & lines["missing_lines"]:
            raise ValueError("Conflicting line inventory: " + name)
        counts = {
            "covered_lines": len(lines["executed_lines"]),
            "num_statements": len(lines["executed_lines"])
            + len(lines["missing_lines"]),
            "missing_lines": len(lines["missing_lines"]),
            "excluded_lines": len(lines["excluded_lines"]),
        }
        summary = data.get("summary", {})
        if not isinstance(summary, dict) or any(
            type(summary.get(k)) is not int or summary[k] != v
            for k, v in counts.items()
        ):
            raise ValueError("Inconsistent coverage counts: " + name)
        for k, v in counts.items():
            totals[k] += v
        if lines["excluded_lines"]:
            raise ValueError("Excluded executable lines in " + name)
        if lines["missing_lines"]:
            raise ValueError("Uncovered executable lines in " + name)
    reported = report.get("totals", {})
    if not isinstance(reported, dict) or any(
        type(reported.get(k)) is not int or reported[k] != v for k, v in totals.items()
    ):
        raise ValueError("Inconsistent coverage totals")
    if not totals["num_statements"]:
        raise ValueError("No executable source measured")
    return totals["covered_lines"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--mcp", action="store_true")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Measure gaps without claiming the 100% gate passed",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = (
        args.output
        or ROOT
        / "build/coverage"
        / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    ).resolve()
    if output == ROOT or any(
        output.is_relative_to(ROOT / folder)
        for folder in ("src", "tests", "scripts", "skills", "docs")
    ):
        parser.error("Output must be outside source, test and documentation trees")
    output.mkdir(parents=True, exist_ok=False)
    config = output / "coverage.ini"
    config.write_text(
        "[run]\ncore = sysmon\nparallel = True\npatch = subprocess\nrelative_files = True\ninclude =\n"
        + "\n".join(
            "    " + str(ROOT / folder / "*")
            for folder in ["src/cadgit", "scripts", "skills/cad-git/scripts"]
        )
        + "\n[report]\nexclude_lines =\n"
    )
    env = {
        **os.environ,
        "COVERAGE_FILE": str(output / ".coverage"),
        "COVERAGE_RCFILE": str(config),
    }
    prefix = [sys.executable, "-m", "coverage"]
    commands = [
        ["-m", "pytest", "-q", "--no-cov", "--hypothesis-profile=ci"],
        ["tests/integration/cli_smoke.py"],
    ]
    if args.ui:
        commands.extend([[f"tests/integration/{suite}.py"] for suite in UI_SUITES])
    if args.mcp:
        commands.append(["tests/integration/mcp_workflow_smoke.py"])
    initial = source_fingerprint(ROOT)
    results = []
    for index, command in enumerate(commands):
        print("Coverage run: " + " ".join(command), flush=True)
        with (output / f"{index:02}.log").open("w") as stream:
            code = execute([*prefix, "run", *command], stream, env, 600)
        results.append({"command": command, "exit_code": code})
    (output / "runs.json").write_text(json.dumps(results, indent=2) + "\n")
    subprocess.run([*prefix, "combine", str(output)], cwd=ROOT, env=env, check=True)
    inventory = production_files(ROOT)
    subprocess.run(
        [*prefix, "json", "-o", str(output / "coverage.json"), *inventory],
        cwd=ROOT,
        env=env,
        check=True,
    )
    report = json.loads((output / "coverage.json").read_text())
    print(json.dumps(report["totals"], indent=2), flush=True)
    print("Coverage report: " + str(output / "coverage.json"), flush=True)
    unchanged = source_fingerprint(ROOT) == initial
    (output / "source.json").write_text(
        json.dumps({"initial_sha256": initial, "source_unchanged": unchanged}, indent=2)
        + "\n"
    )
    if not unchanged:
        raise RuntimeError("Source changed during coverage run; diagnostic only")
    if any(item["exit_code"] for item in results):
        raise RuntimeError(
            "One or more measured suites failed; coverage is diagnostic only"
        )
    if not args.report_only:
        validate_report(report, inventory)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
