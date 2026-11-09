"""Exercise the existing Pydantic contracts without changing archive semantics."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError
from test_verification_compatibility import JSON

from cadgit.models import Assembly, Selection, Snapshot


@given(
    extension=JSON,
    revision=st.text(min_size=1),
    translation=st.tuples(*[st.floats(allow_nan=False, allow_infinity=False)] * 3),
)
def test_selection_roundtrip_pins_revisions_and_preserves_additive_fields(
    extension, revision, translation
):
    data = {
        "snapshot_id": "snap_exact",
        "prim_path": "/World/Part",
        "library_material_revision": revision,
        "future": extension,
        "translation": translation,
    }
    before = deepcopy(data)
    result = Selection.model_validate(data).model_dump(mode="json")
    assert result["snapshot_id"] == "snap_exact"
    assert result["library_material_revision"] == revision
    assert result["future"] == extension
    assert result["translation"] == list(translation)
    assert result["required_features"] == ["cadgit.material-library.v1"]
    assert Selection.model_validate(result).model_dump(mode="json") == result
    assert data == before


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
@pytest.mark.parametrize("axis", range(3))
def test_nonfinite_translation_is_rejected(bad, axis):
    translation = [0, 0, 0]
    translation[axis] = bad
    with pytest.raises(ValidationError):
        Selection(
            snapshot_id="snap_exact", prim_path="/World/Part", translation=translation
        )


@given(
    translation=st.lists(st.integers(), max_size=6).filter(
        lambda value: len(value) != 3
    )
)
def test_translation_requires_exactly_three_coordinates(translation):
    with pytest.raises(ValidationError):
        Selection(
            snapshot_id="snap_exact", prim_path="/World/Part", translation=translation
        )


def test_default_feature_lists_are_independent():
    first = Selection(snapshot_id="a", prim_path="/A")
    second = Selection(snapshot_id="b", prim_path="/B")
    first.required_features.append("future")
    assert second.required_features == []


@pytest.mark.parametrize(
    "model,filename", [(Snapshot, "snapshot.json"), (Assembly, "assembly.json")]
)
def test_legacy_serialization_contract(snapshot, model, filename):
    # Existing historical fixtures are read-only. No timestamp/ID normalization
    # can conceal a change in the serialized public record.
    path = Path(__file__).parent / "fixtures" / "format_v1" / filename
    original = path.read_bytes()
    data = json.loads(original)
    data["future"] = {"nested": [None, True, {"unit": "µm", "value": 0}]}
    assert model.model_validate(data).model_dump(mode="json") == snapshot
    assert path.read_bytes() == original
