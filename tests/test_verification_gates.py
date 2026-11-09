"""The quality gate rejects incomplete evidence instead of treating it as a kill."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "mutation_gate", Path(__file__).resolve().parents[1] / "scripts/check_mutations.py"
)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def stats(**changes):
    return {**dict.fromkeys(gate.COUNTS, 0), "total": 100, "killed": 100, **changes}


@pytest.mark.parametrize(
    "report",
    [
        {},
        stats(total=0, killed=0),
        stats(total=101),
        stats(killed=True),
        stats(killed=-1),
        stats(killed=94, survived=6),
        stats(killed="100"),
        *[
            stats(killed=99, **{name: 1})
            for name in gate.COUNTS
            if name not in {"killed", "survived"}
        ],
    ],
)
def test_mutation_gate_rejects_false_green_reports(report):
    with pytest.raises(ValueError):
        gate.validate_stats(report)


def test_mutation_threshold_includes_survivors_in_denominator():
    assert gate.validate_stats(stats(killed=95, survived=5)) == 95
    assert gate.validate_stats(stats()) == 100
