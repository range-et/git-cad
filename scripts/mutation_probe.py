"""One fresh-process Mutmut candidate with hit and pytest-outcome evidence."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--mutant", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("tests", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    expected = args.source.resolve()
    sys.path.insert(0, str(expected.parents[len(args.module.split(".")) - 1]))
    import pytest
    from mutmut.mutation.trampoline import set_mutant_under_test

    set_mutant_under_test(args.mutant)
    os.environ["MUTANT_UNDER_TEST"] = args.mutant
    evidence = {
        "mutant": args.mutant,
        "source": str(expected),
        "source_sha256": hashlib.sha256(expected.read_bytes()).hexdigest(),
        "hits": 0,
        "failed_tests": [],
        "collection_errors": [],
        "internal_errors": [],
        "exit_code": None,
    }
    short_name = args.mutant.rsplit(".", 1)[-1]
    files = (
        json.loads(args.inventory.read_text())
        if args.inventory
        else {args.module: str(expected)}
    )
    modules_by_path = {
        str(Path(path).resolve()): module for module, path in files.items()
    }
    evidence["tests_by_function"] = {}
    evidence["test_durations"] = {}
    active = [None]
    monitoring = sys.monitoring
    tool = next(index for index in range(6) if monitoring.get_tool(index) is None)
    monitoring.use_tool_id(tool, "cadgit_mutation_probe")

    def started(code, offset):
        if args.mutant:
            if (
                code.co_name == short_name
                and Path(code.co_filename).resolve() == expected
            ):
                evidence["hits"] += 1
                monitoring.set_events(tool, 0)
        elif active[0] and code.co_name.endswith("__mutmut_orig"):
            module = modules_by_path.get(str(Path(code.co_filename).resolve()))
            if module:
                function = module + "." + code.co_name.removesuffix("orig")
                tests = evidence["tests_by_function"].setdefault(function, [])
                if active[0] not in tests:
                    tests.append(active[0])
        return monitoring.DISABLE

    class Outcomes:
        def pytest_runtest_logstart(self, nodeid, location):
            active[0] = nodeid
            if not args.mutant:
                monitoring.restart_events()

        def pytest_runtest_logfinish(self, nodeid, location):
            active[0] = None

        def pytest_runtest_logreport(self, report):
            evidence["test_durations"][report.nodeid] = (
                evidence["test_durations"].get(report.nodeid, 0) + report.duration
            )
            if report.failed:
                evidence["failed_tests"].append(
                    {
                        "nodeid": report.nodeid,
                        "phase": report.when,
                        "error": str(report.longrepr),
                    }
                )

        def pytest_collectreport(self, report):
            if report.failed:
                evidence["collection_errors"].append(str(report.longrepr))

        def pytest_internalerror(self, excrepr, excinfo):
            evidence["internal_errors"].append(str(excrepr))

    monitoring.register_callback(tool, monitoring.events.PY_START, started)
    monitoring.set_events(tool, monitoring.events.PY_START)
    try:
        evidence["exit_code"] = int(
            pytest.main(
                ["-x", "-q", "--no-cov", "--hypothesis-profile=ci", *args.tests],
                plugins=[Outcomes()],
            )
        )
        module = sys.modules.get(args.module)
        evidence["imported_source"] = (
            str(Path(module.__file__).resolve())
            if module is not None and getattr(module, "__file__", None)
            else None
        )
        if evidence["imported_source"] not in (None, str(expected)):
            evidence["internal_errors"].append(
                "Target imported outside isolated generated source"
            )
    finally:
        evidence["final_source_sha256"] = hashlib.sha256(
            expected.read_bytes()
        ).hexdigest()
        monitoring.set_events(tool, 0)
        monitoring.free_tool_id(tool)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        temporary = args.report.with_suffix(".tmp")
        temporary.write_text(json.dumps(evidence, indent=2) + "\n")
        temporary.replace(args.report)
    return evidence["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
