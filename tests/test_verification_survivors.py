"""Audit the exact surviving edits, with controls that must break the test oracle."""

import inspect
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import pytest
import test_verification_compatibility as contract
from hypothesis import example, given
from hypothesis import strategies as st

import cadgit.compatibility as compatibility
from cadgit.errors import CadgitError

SOURCE = inspect.getsource(compatibility)
CAST = ("cast(dict[str, object], data)", "cast(None, data)")
MINOR = ('data.get("schema_minor", 0)', 'data.get("schema_minor", 1)')


def edited_source(edit):
    old, new = edit
    # Fail loudly if the implementation changes: these are exact reviewed edits,
    # not permanent waivers keyed to unstable Mutmut numeric IDs.
    assert SOURCE.count(old) == 1
    return SOURCE.replace(old, new, 1)


def variant(edit):
    namespace = {"__package__": "cadgit"}
    exec(
        compile(edited_source(edit), "<isolated compatibility mutant>", "exec"),
        namespace,
    )
    return namespace["check_compatibility"]


def outcome(function, value, legacy):
    data = deepcopy(value)
    try:
        result = ("accepted", function(data, context="audit", legacy=legacy))
    except CadgitError as error:
        result = ("rejected", str(error))
    assert data == value
    return result


RECORDS = st.one_of(
    contract.JSON,
    st.builds(lambda extra: {"schema_version": 1, "future": extra}, contract.JSON),
    st.builds(
        lambda field, value: {"schema_version": 1, field: value},
        st.sampled_from(["schema_version", "schema_minor", "required_features"]),
        contract.JSON,
    ),
)


@pytest.mark.parametrize("edit", [CAST, MINOR], ids=["cast-target", "minor-default"])
@given(value=RECORDS, legacy=st.booleans())
@example(value={"schema_version": 1}, legacy=False)
@example(value={}, legacy=True)
@example(value={"schema_version": 1, "schema_minor": -1}, legacy=False)
@example(value={"schema_version": 1, "schema_minor": None}, legacy=False)
def test_survivors_have_same_runtime_outcome_and_preserve_input(edit, value, legacy):
    assert outcome(variant(edit), value, legacy) == outcome(
        compatibility.check_compatibility, value, legacy
    )


@pytest.mark.parametrize(
    "edit,value",
    [
        ((MINOR[0], 'data.get("schema_minor", -1)'), {"schema_version": 1}),
        (("minor < 0", "minor < -1"), {"schema_version": 1, "schema_minor": -1}),
        (
            ("type(major) is not int", "not isinstance(major, int)"),
            {"schema_version": True},
        ),
    ],
    ids=["invalid-default", "accept-negative-minor", "accept-boolean-major"],
)
def test_existing_oracle_detects_behavior_changing_controls(edit, value):
    contract.assert_format_contract(value, False)
    with patch.object(contract, "check_compatibility", variant(edit)):
        # A rejected valid record raises CadgitError; accepting an invalid record
        # causes pytest.raises to fail. Both demonstrate the existing oracle firing.
        with pytest.raises((CadgitError, pytest.fail.Exception)):
            contract.assert_format_contract(value, False)


def test_static_gate_rejects_cast_mutant_but_accepts_baseline_and_minor_mutant(
    tmp_path,
):
    package = tmp_path / "probe"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "errors.py").write_text(
        Path(compatibility.__file__).with_name("errors.py").read_text()
    )
    (tmp_path / "mypy.ini").write_text("[mypy]\nstrict = True\n")
    target = package / "compatibility.py"
    for source, expected in [
        (SOURCE, 0),
        (edited_source(CAST), 1),
        (edited_source(MINOR), 0),
    ]:
        target.write_text(source)
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--no-incremental", str(target)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == expected, result.stdout + result.stderr
        if expected:
            assert '"None" has no attribute "get"' in result.stdout
