"""Bounded generated real-project actions with an independent immutable-byte oracle."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from test_history import box
from test_history_graph import build_graph

import cadgit.store as store
from cadgit.usd import assemble


@settings(max_examples=20, deadline=None)
@given(
    actions=st.lists(
        st.sampled_from(["save", "fork", "compose", "fail", "main"]),
        min_size=1,
        max_size=8,
    )
)
def test_generated_history_actions_preserve_sources_and_exact_links(actions):
    with tempfile.TemporaryDirectory(prefix="cadgit-history-property-") as temporary:
        root = Path(temporary)
        project = store.Project.init(root / "project")
        source = box(root / "source.usda")
        original = source.read_bytes()
        captures = [project.ingest(source, "rhino")]
        assemblies = []
        branch = "main"
        heads = {"main": captures[0]["id"]}
        frozen = {}
        expected_main = None
        for index, action in enumerate(actions):
            for record in [*captures, *assemblies]:
                directory = Path(record["_directory"])
                for path in directory.rglob("*"):
                    if path.is_file():
                        frozen.setdefault(path, path.read_bytes())
            if action == "fork":
                branch = "fork_" + str(index)
                base = captures[0]["id"]
                project.branch("rhino", branch, base, activate=True)
                heads[branch] = base
            elif action == "save":
                capture = project.ingest(
                    source, "rhino", metadata={"capture_id": "action_" + str(index)}
                )
                assert capture["parent"] == heads[branch]
                heads[branch] = capture["id"]
                captures.append(capture)
                assert (
                    project.ingest(
                        source, "rhino", metadata={"capture_id": "action_" + str(index)}
                    )["id"]
                    == capture["id"]
                )
            elif action == "compose":
                selection = {
                    "snapshot_id": captures[0]["id"],
                    "prim_path": "/World/Part",
                    "future": {"step": index},
                }
                result = assemble(project, [selection])
                assert result["selections"][0]["snapshot_id"] == captures[0]["id"]
                assert result["selections"][0]["future"] == {"step": index}
                assemblies.append(result)
            elif action == "main" and assemblies:
                project.set_main(assemblies[-1]["id"])
                expected_main = assemblies[-1]["id"]
            elif action == "fail":
                real_write = store.atomic_json

                def fail_manifest(path, value, *args, _real_write=real_write, **kwargs):
                    if Path(path).name == "manifest.json":
                        raise OSError("Injected failed save before publication")
                    return _real_write(path, value, *args, **kwargs)

                with patch.object(store, "atomic_json", fail_manifest):
                    with pytest.raises(OSError):
                        project.ingest(source, "rhino")
            project = store.Project(project.root)
            assert {r["id"] for r in project.records()} == {r["id"] for r in captures}
            assert {r["id"] for r in project.records("assemblies")} == {
                r["id"] for r in assemblies
            }
            assert all(path.read_bytes() == content for path, content in frozen.items())
            assert source.read_bytes() == original
            assert all(
                project.verify(record["id"])["ok"]
                for record in [*captures, *assemblies]
            )
            if expected_main:
                assert project.resolve("main")["id"] == expected_main
            else:
                assert not (project.root / "main/current.json").exists()
            graph = build_graph(
                project.records(),
                project.records("assemblies"),
                project.config,
                expected_main,
            )
            assert not graph["missing"] and not graph["cyclic"]
            positions = {node["id"]: i for i, node in enumerate(graph["nodes"])}
            assert all(
                positions[edge["child"]] < positions[edge["parent"]]
                for edge in graph["edges"]
            )


def test_graph_handles_shared_import_parent_and_detects_corrupt_cycle(tmp_path):
    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "source.usda")
    first = project.ingest(source, "rhino")
    second = project.ingest(source, "rhino", metadata={"imported_from": first["id"]})
    graph = build_graph(project.records(), [], project.config)
    assert len(graph["edges"]) == 2
    assert {edge["kind"] for edge in graph["edges"]} == {"save", "import"}
    records = project.records()
    records[0]["parent"] = second["id"]  # in-memory corruption probe; never written
    cyclic = build_graph(records, [], project.config)
    assert set(cyclic["cyclic"]) == {first["id"], second["id"]}
    assert "Cyclic ancestry detected" in cyclic["warnings"]
    assert project.verify(second["id"])["ok"]
