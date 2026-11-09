"""Real shared and deep histories have bounded validation work and diagnostics."""

import sys
from collections import Counter

from test_history import box

from cadgit.library import Library
from cadgit.store import Project


def test_shared_material_ancestors_checked_once_and_corruption_reports_both_roles(
    tmp_path, monkeypatch
):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    original = library.create_material("Original")
    current = original
    for index in range(7):
        current = library.recombine(str(index), current["id"], current["id"])
    calls = Counter()
    local = project._verify_local

    def counted(record):
        calls[record["id"]] += 1
        return local(record)

    monkeypatch.setattr(project, "_verify_local", counted)
    assert library.verify(current["id"])["ok"]
    assert len(calls) == 8 and set(calls.values()) == {1}
    calls.clear()
    project.stage_path(original).write_text("corrupt payload")
    result = library.verify(current["id"])
    assert not result["ok"]
    assert len(calls) == 8 and set(calls.values()) == {1}
    assert any("Hash mismatch" in error for error in result["errors"])
    assert any("physical_from" in error for error in result["errors"])
    assert any("appearance_from" in error for error in result["errors"])
    assert len(result["errors"]) <= 20


def test_long_real_scene_history_does_not_use_recursive_python_calls(
    tmp_path, monkeypatch
):
    project = Project.init(tmp_path / "project")
    source = box(tmp_path / "part.usda")
    for _ in range(80):
        latest = project.ingest(source, "rhino")
    calls = Counter()
    local = project._verify_local

    def counted(record):
        calls[record["id"]] += 1
        return local(record)

    monkeypatch.setattr(project, "_verify_local", counted)
    depth = 0
    frame = sys._getframe()
    while frame:
        depth += 1
        frame = frame.f_back
    previous = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(depth + 45)
        assert project.verify(latest["id"])["ok"]
    finally:
        sys.setrecursionlimit(previous)
    assert len(calls) == 80 and set(calls.values()) == {1}


def test_library_parent_role_is_provenance_not_a_scene_save_relationship(tmp_path):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    source = tmp_path / "spec.txt"
    source.write_text("original specification")
    first = library.import_asset(source)
    derived = library.import_asset(
        source, parents=[{"revision_id": first["id"], "role": "parent"}]
    )
    assert library.verify(derived["id"])["ok"]
    assert derived["parents"] == [{"revision_id": first["id"], "role": "parent"}]
