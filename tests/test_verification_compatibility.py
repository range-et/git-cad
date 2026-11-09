"""Independent format oracle, including rejection without modifying caller data."""

from copy import deepcopy

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from cadgit.compatibility import check_compatibility
from cadgit.errors import CadgitError

JSON = st.recursive(
    st.none()
    | st.booleans()
    | st.integers()
    | st.floats(allow_nan=False, allow_infinity=False)
    | st.text(),
    lambda children: (
        st.lists(children, max_size=5)
        | st.dictionaries(st.text(), children, max_size=5)
    ),
    max_leaves=20,
)
KNOWN = ["cadgit.material-library.v1", "cadgit.brep-job.v1"]


@given(
    minor=st.integers(min_value=0),
    required=st.lists(st.sampled_from(KNOWN), max_size=8),
    extension=JSON,
)
def test_additive_formats_are_accepted_unchanged(minor, required, extension):
    data = {
        "schema_version": 1,
        "schema_minor": minor,
        "required_features": required,
        "future": extension,
    }
    before = deepcopy(data)
    assert check_compatibility(data) is None
    assert data == before


def assert_format_contract(value, legacy):
    before = deepcopy(value)
    valid = False
    if isinstance(value, dict):
        major = value.get("schema_version", 1 if legacy else None)
        minor = value.get("schema_minor", 0)
        required = value.get("required_features", [])
        valid = (
            type(major) is int
            and major == 1
            and type(minor) is int
            and minor >= 0
            and isinstance(required, list)
            and all(isinstance(item, str) and item in KNOWN for item in required)
        )
    if valid:
        assert check_compatibility(value, legacy=legacy) is None
    else:
        with pytest.raises(CadgitError):
            check_compatibility(value, legacy=legacy)
    assert value == before


@given(value=JSON, legacy=st.booleans())
@example(value=True, legacy=True)
@example(value={"schema_version": True}, legacy=False)
@example(value={"schema_version": 1, "schema_minor": False}, legacy=False)
@example(value={"schema_version": None}, legacy=True)
@example(value={}, legacy=True)
@example(value={}, legacy=False)
def test_arbitrary_json_matches_format_contract(value, legacy):
    assert_format_contract(value, legacy)


@given(
    field=st.sampled_from(["schema_version", "schema_minor", "required_features"]),
    value=JSON,
)
def test_generated_boundary_field(field, value):
    data = {"schema_version": 1, field: value}
    assert_format_contract(data, False)


@pytest.mark.parametrize("legacy", [False, True])
def test_legacy_defaults_and_explicit_versions(legacy):
    check_compatibility({"schema_version": 1}, legacy=legacy)
    for major in [None, True, False, 0, -1, 2, 1.0, "1", [], {}]:
        with pytest.raises(CadgitError, match="unsupported schema version"):
            check_compatibility({"schema_version": major}, legacy=legacy)
    if legacy:
        check_compatibility({}, legacy=True)
    else:
        with pytest.raises(CadgitError):
            check_compatibility({})


@pytest.mark.parametrize("minor", [None, True, False, -1, 0.0, "0", [], {}])
def test_invalid_minor(minor):
    with pytest.raises(CadgitError, match="invalid schema_minor"):
        check_compatibility({"schema_version": 1, "schema_minor": minor})


@pytest.mark.parametrize(
    "required", [None, "x", {}, True, [1], [None], [KNOWN[0], False]]
)
def test_invalid_features(required):
    with pytest.raises(
        CadgitError, match="required_features must be a list of feature identifiers"
    ):
        check_compatibility({"schema_version": 1, "required_features": required})


def test_actionable_diagnostics_are_stable():
    cases = [
        ([], "asset: expected a JSON object"),
        (
            {"schema_version": 2},
            "asset: unsupported schema version 2; this release supports major 1. Original data was not migrated.",
        ),
        ({"schema_version": 1, "schema_minor": -1}, "asset: invalid schema_minor -1"),
        (
            {"schema_version": 1, "required_features": ["z", "a", "z", *KNOWN]},
            "asset: requires unsupported features: a, z. Upgrade Git CAD to use this data.",
        ),
    ]
    for value, message in cases:
        with pytest.raises(CadgitError) as error:
            check_compatibility(value, context="asset")
        assert str(error.value) == message
    with pytest.raises(CadgitError, match="^record: expected a JSON object$"):
        check_compatibility(None)
