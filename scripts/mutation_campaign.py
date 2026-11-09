"""Generate Mutmut candidates, execute in fresh processes, retain honest outcomes."""

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_RUNNING = set()
_PROCESS_LOCK = threading.Lock()


def input_inventory(root):
    paths = {
        str(p.relative_to(root))
        for directory in ("src", "tests", "scripts", "skills", "docs")
        for p in (root / directory).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
    }
    paths.update(
        name
        for name in (
            "pyproject.toml",
            "uv.lock",
            "README.md",
            "features.md",
            "AGENTS.md",
            "LICENSE",
            ".gitignore",
        )
        if (root / name).is_file()
    )
    return sorted(paths)


def digest_files(root, paths):
    digest = hashlib.sha256()
    for name in sorted(paths):
        digest.update(name.encode() + b"\0")
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def classify(report, exit_code, expected_hash, expected_mutant, expected_source):
    if not isinstance(report, dict):
        return "missing-report"
    required = {
        "source_sha256",
        "exit_code",
        "hits",
        "failed_tests",
        "collection_errors",
        "internal_errors",
    }
    if (
        not required.issubset(report)
        or type(report["exit_code"]) is not int
        or type(exit_code) is not int
    ):
        return "malformed-report"
    if type(report["hits"]) is not int or report["hits"] < 0:
        return "malformed-report"
    if any(
        not isinstance(report[key], list)
        for key in ("failed_tests", "collection_errors", "internal_errors")
    ):
        return "malformed-report"
    for failure in report["failed_tests"]:
        if (
            not isinstance(failure, dict)
            or not isinstance(failure.get("nodeid"), str)
            or not failure["nodeid"]
            or failure.get("phase") not in ("setup", "call", "teardown")
            or not isinstance(failure.get("error"), str)
        ):
            return "malformed-report"
    if (
        report.get("mutant") != expected_mutant
        or report.get("source") != expected_source
        or report.get("imported_source") != expected_source
    ):
        return "wrong-target"
    if report.get("final_source_sha256") != expected_hash:
        return "source-drift"
    if report.get("source_sha256") != expected_hash:
        return "source-drift"
    if report.get("exit_code") != exit_code:
        return "inconsistent-exit"
    if report.get("collection_errors") or report.get("internal_errors"):
        return "infrastructure-error"
    if exit_code not in (0, 1):
        return "unresolved-exit"
    if not expected_mutant:
        return (
            "baseline-passed"
            if exit_code == 0 and not report["failed_tests"]
            else "baseline-failed"
        )
    if not report.get("hits"):
        return "uncovered"
    failed = report.get("failed_tests", [])
    if exit_code == 1 and failed:
        return "killed"
    if exit_code == 0 and not failed:
        return "survived"
    return "inconsistent-tests"


def run_probe(workspace, arguments, log, timeout, stop=None):
    command = [sys.executable, str(workspace / "scripts/mutation_probe.py"), *arguments]
    start = time.monotonic()
    with log.open("w") as stream:
        with _PROCESS_LOCK:
            if stop is not None and stop.is_set():
                return None, time.monotonic() - start
            process = subprocess.Popen(
                command,
                cwd=workspace,
                stdout=stream,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            _RUNNING.add(process)
        try:
            code = process.wait(timeout=timeout)
        except BaseException as exc:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            if isinstance(exc, subprocess.TimeoutExpired):
                return None, time.monotonic() - start
            raise
        finally:
            with _PROCESS_LOCK:
                _RUNNING.discard(process)
    return code, time.monotonic() - start


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--module",
        action="append",
        required=True,
        help="Exact cadgit module, repeat for multiple targets",
    )
    parser.add_argument(
        "--tests",
        nargs="+",
        default=["tests", "--ignore=tests/test_verification_survivors.py"],
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--baseline-timeout", type=int, default=600)
    parser.add_argument(
        "--limit", type=int, help="Diagnostic prefix only; never a complete campaign"
    )
    parser.add_argument(
        "--candidate-list",
        type=Path,
        help="Diagnostic subset of exact candidate IDs; remaining candidates stay pending",
    )
    args = parser.parse_args()
    if (
        args.workers < 1
        or args.timeout < 1
        or args.baseline_timeout < 1
        or args.limit is not None
        and args.limit < 1
    ):
        parser.error("workers, timeout and limit must be positive")
    output = args.output.resolve()
    if output == ROOT or any(
        output.is_relative_to(ROOT / folder)
        for folder in ("src", "tests", "scripts", "skills", "docs")
    ):
        parser.error("Output must be outside copied input trees")
    output.mkdir(parents=True, exist_ok=False)
    workspace = output / "workspace"
    workspace.mkdir()
    for directory in ("src", "tests", "scripts", "skills", "docs"):
        shutil.copytree(
            ROOT / directory,
            workspace / directory,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    for name in (
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "features.md",
        "AGENTS.md",
        "LICENSE",
        ".gitignore",
    ):
        if (ROOT / name).is_file():
            shutil.copy2(ROOT / name, workspace / name)
    inputs = [
        str(path.relative_to(workspace))
        for path in workspace.rglob("*")
        if path.is_file()
    ]
    source_hash = digest_files(workspace, inputs)
    metadata = {
        "source_sha256": source_hash,
        "python": sys.version,
        "platform": platform.platform(),
        "mutmut_version": importlib.metadata.version("mutmut"),
        "modules": args.module,
        "tests": args.tests,
        "limit": args.limit,
        "workers": args.workers,
        "timeout_seconds": args.timeout,
        "baseline_timeout_seconds": args.baseline_timeout,
        "baseline_runs": [],
        "results": [],
        "result": "running",
    }
    (output / "inputs.json").write_text(json.dumps(inputs, indent=2))
    from mutmut.mutation.file_mutation import mutate_file_contents

    candidates = []
    module_paths = {}
    generated_hashes = {}
    for module in args.module:
        if any(not part.isidentifier() for part in module.split(".")):
            parser.error("Target must be an exact production module")
        if module.startswith("cadgit."):
            relative = Path("src").joinpath(*module.split(".")).with_suffix(".py")
        elif module.startswith("scripts.") and len(module.split(".")) == 2:
            relative = Path(*module.split(".")).with_suffix(".py")
        elif module == "cadgit_skill.inspect_folder":
            relative = Path("skills/cad-git/scripts/inspect_folder.py")
        else:
            parser.error("Target is outside the declared production/tool inventory")
        target = workspace / relative
        generated = mutate_file_contents(str(relative), target.read_text())
        target.write_text(generated.code)
        generated_hashes[module] = hashlib.sha256(target.read_bytes()).hexdigest()
        module_paths[module] = str(target)
        candidates.extend(
            (module, module + "." + name) for name in generated.mutant_names
        )
    inventory = output / "generated.json"
    inventory.write_text(json.dumps(module_paths, indent=2))
    generated_inventory = input_inventory(workspace)
    generated_digest = digest_files(workspace, generated_inventory)
    metadata["generated_workspace_sha256"] = generated_digest
    metadata["generated_hashes"] = generated_hashes
    metadata["generated_candidates"] = len(candidates)
    metadata["candidate_ids"] = [name for _, name in candidates]
    report_path = output / "report.json"

    def save():
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(metadata, indent=2) + "\n")
        temporary.replace(report_path)

    save()

    def baseline_probe(*arguments):
        try:
            code, elapsed = run_probe(*arguments)
            metadata["baseline_runs"].append(
                {
                    "log": str(arguments[2]),
                    "exit_code": code,
                    "seconds": elapsed,
                    "timeout_seconds": arguments[3],
                }
            )
            save()
            return code, elapsed
        except BaseException:
            metadata["result"] = "interrupted or failed during baseline"
            save()
            raise

    first = args.module[0]
    baseline_path = output / "baseline.json"
    baseline_args = [
        "--source",
        module_paths[first],
        "--module",
        first,
        "--mutant",
        "",
        "--inventory",
        str(inventory),
        "--report",
        str(baseline_path),
        *args.tests,
    ]
    code, _ = baseline_probe(
        workspace, baseline_args, output / "baseline.log", args.baseline_timeout
    )
    if code != 0 or not baseline_path.exists():
        metadata["result"] = "baseline failed"
        save()
        raise RuntimeError("Generated-original baseline failed; no kills credited")
    baseline = json.loads(baseline_path.read_text())
    if (
        classify(baseline, code, generated_hashes[first], "", module_paths[first])
        != "baseline-passed"
    ):
        metadata["result"] = "baseline infrastructure failure"
        save()
        raise RuntimeError("Baseline evidence is invalid")
    tests_by_function = baseline["tests_by_function"]
    durations = baseline["test_durations"]
    selected = candidates
    if args.candidate_list:
        requested = json.loads(args.candidate_list.read_text())
        if (
            not isinstance(requested, list)
            or any(not isinstance(name, str) for name in requested)
            or not set(requested).issubset(name for _, name in candidates)
        ):
            parser.error("Candidate list must contain only generated exact IDs")
        selected = [(module, name) for module, name in candidates if name in requested]
    if args.limit:
        selected = selected[: args.limit]
    metadata["selected_candidates"] = [name for _, name in selected]
    metadata["pending_candidates"] = [
        name for _, name in candidates if name not in metadata["selected_candidates"]
    ]
    save()
    groups = {}
    for module, candidate in selected:
        function = candidate.rsplit("__mutmut_", 1)[0] + "__mutmut_"
        groups.setdefault((module, function), []).append(candidate)
    jobs = []
    baseline_cache = {}
    # Match each candidate's selected tests against an unmutated generated copy
    # before those tests can earn a kill. Fastest relevant tests run first.
    for (module, function), names in groups.items():
        tests = sorted(
            tests_by_function.get(function, []),
            key=lambda test: (durations.get(test, 0), test),
        )
        if not tests:
            metadata["results"].extend(
                {"mutant": name, "status": "uncovered", "tests": []} for name in names
            )
            save()
            continue
        group_path = output / hashlib.sha256(function.encode()).hexdigest()[:16]
        group_path.mkdir()
        common = ["--source", module_paths[module], "--module", module]
        matched = group_path / "baseline.json"
        cache_key = (module, tuple(tests))
        if cache_key in baseline_cache:
            prior, elapsed = baseline_cache[cache_key]
            matched_report = json.loads(prior.read_text())
            matched_report["reused_from"] = str(prior)
            matched.write_text(json.dumps(matched_report, indent=2) + "\n")
            code = 0
        else:
            code, elapsed = baseline_probe(
                workspace,
                [*common, "--mutant", "", "--report", str(matched), *tests],
                group_path / "baseline.log",
                args.baseline_timeout,
            )
            matched_report = (
                json.loads(matched.read_text()) if matched.exists() else None
            )
        if (
            classify(
                matched_report, code, generated_hashes[module], "", module_paths[module]
            )
            != "baseline-passed"
        ):
            metadata["results"].extend(
                {"mutant": name, "status": "matched-baseline-failed", "tests": tests}
                for name in names
            )
            save()
            continue
        baseline_cache[cache_key] = (matched, elapsed)
        jobs.extend(
            (module, name, tests, group_path, max(args.timeout, elapsed * 3))
            for name in names
        )
    stop = threading.Event()

    def execute_candidate(job):
        module, name, tests, group_path, timeout = job
        if stop.is_set():
            return {"mutant": name, "status": "interrupted"}
        filename = hashlib.sha256(name.encode()).hexdigest()[:16]
        evidence_path = group_path / (filename + ".json")
        common = ["--source", module_paths[module], "--module", module]
        code, elapsed = run_probe(
            workspace,
            [*common, "--mutant", name, "--report", str(evidence_path), *tests],
            group_path / (filename + ".log"),
            timeout,
            stop,
        )
        evidence = (
            json.loads(evidence_path.read_text()) if evidence_path.exists() else None
        )
        status = (
            "timeout"
            if code is None
            else classify(
                evidence, code, generated_hashes[module], name, module_paths[module]
            )
        )
        return {
            "mutant": name,
            "status": status,
            "seconds": elapsed,
            "timeout_seconds": timeout,
            "evidence": str(evidence_path),
            "tests": tests,
        }

    workers = ThreadPoolExecutor(max_workers=args.workers)
    try:
        futures = [workers.submit(execute_candidate, job) for job in jobs]
        for future in as_completed(futures):
            metadata["results"].append(future.result())
            save()
            if len(metadata["results"]) % 10 == 0 or len(metadata["results"]) == len(
                selected
            ):
                counts = {}
                for result in metadata["results"]:
                    counts[result["status"]] = counts.get(result["status"], 0) + 1
                print(
                    f"{len(metadata['results'])}/{len(candidates)} {counts}", flush=True
                )
        metadata["source_unchanged"] = (
            input_inventory(ROOT) == sorted(inputs)
            and digest_files(ROOT, inputs) == source_hash
        )
        metadata["workspace_unchanged"] = (
            input_inventory(workspace) == generated_inventory
            and digest_files(workspace, generated_inventory) == generated_digest
        )
        complete = (
            bool(candidates)
            and len(metadata["results"]) == len(candidates)
            and all(result["status"] == "killed" for result in metadata["results"])
        )
        metadata["result"] = (
            "all generated mutants killed"
            if complete
            and metadata["source_unchanged"]
            and metadata["workspace_unchanged"]
            else "incomplete or surviving mutations; review required"
        )
        save()
    except BaseException:
        stop.set()
        with _PROCESS_LOCK:
            for process in list(_RUNNING):
                if process.poll() is None:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        metadata["result"] = "interrupted or failed"
        save()
        raise
    finally:
        workers.shutdown(wait=True, cancel_futures=True)
    return 0 if metadata["result"] == "all generated mutants killed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
