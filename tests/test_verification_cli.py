"""CLI outcomes must agree with persistent state and immutable archive boundaries."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import cadgit.cli as cli
import cadgit.store as store


@pytest.mark.parametrize("after_publication", [False, True])
def test_autosnapshot_save_outcome_matches_config_and_events(
    tmp_path, monkeypatch, after_publication
):
    project = store.Project.init(tmp_path / "project")
    before = (project.root / "cadgit.json").read_bytes()
    events = {path.name for path in (project.root / "history/events").iterdir()}
    write = store.atomic_json
    sync = store.fsync_dir
    if after_publication:

        def failed_sync(path):
            if Path(path) == project.root:
                raise OSError("Config durability unavailable")
            return sync(path)

        monkeypatch.setattr(store, "fsync_dir", failed_sync)
    else:

        def failed_write(path, value, *args, **kwargs):
            if Path(path) == project.root / "cadgit.json":
                raise OSError("Config save denied")
            return write(path, value, *args, **kwargs)

        monkeypatch.setattr(store, "atomic_json", failed_write)
        monkeypatch.setattr(cli, "atomic_json", failed_write)
    result = CliRunner().invoke(
        cli.app,
        ["--project", str(project.root), "autosnapshot", "on", "--interval", "60"],
    )
    if after_publication:
        assert result.exit_code == 0, result.output
        emitted = json.loads(result.stdout)
        assert (
            emitted["interval"] == 60
            and "Config durability unavailable" in emitted["publication_warning"]
        )
        assert (
            store.read_json(project.root / "cadgit.json")["tool_interval_seconds"] == 60
        )
    else:
        assert result.exit_code != 0
        assert (project.root / "cadgit.json").read_bytes() == before
        assert {
            path.name for path in (project.root / "history/events").iterdir()
        } == events


def invoke(project, *arguments):
    return CliRunner().invoke(
        cli.app, ["--project", str(project.root), *map(str, arguments)]
    )


def test_cli_native_control_reports_partial_failures_and_snapshot_receipts(
    tmp_path, monkeypatch
):
    from test_history import box

    import cadgit.connectors as connectors
    import cadgit.service as service

    project = store.Project.init(tmp_path / "project")
    calls = []

    def attach(p, app, endpoint):
        calls.append(("attach", p.root, app, endpoint))
        if app == "rhino":
            raise OSError("Rhino unavailable")

    def detach(p, app):
        calls.append(("detach", p.root, app))
        if app == "blender":
            raise OSError("Blender unavailable")

    monkeypatch.setattr(connectors, "attach", attach)
    monkeypatch.setattr(connectors, "detach", detach)
    monkeypatch.setattr(service, "start", lambda p: {"running": True, "pid": 123})
    monkeypatch.setattr(service, "stop", lambda p: {"stopping": True})
    started = invoke(project, "begin", "--rhino-endpoint", "http://fixture.invalid")
    assert started.exit_code == 0
    assert json.loads(started.stdout) == {
        "rhino": "Rhino unavailable",
        "blender": "save hook attached",
        "service": {"running": True, "pid": 123},
    }
    stopped = invoke(project, "stop")
    assert json.loads(stopped.stdout) == {
        "rhino": "detached",
        "blender": "Blender unavailable",
        "service": {"stopping": True},
    }
    assert calls[0] == ("attach", project.root, "rhino", "http://fixture.invalid")

    def capture(p, app):
        inbox = p.root / ".cadgit/inbox/cli-capture"
        inbox.mkdir()
        box(inbox / "scene.usda")
        store.atomic_json(inbox / "ready.json", {"source": app, "file": "scene.usda"})

    monkeypatch.setattr(connectors, "capture", capture)
    result = invoke(project, "snapshot", "--source", "blender")
    assert result.exit_code == 0 and json.loads(result.stdout) == {
        "snapshots_committed": 1
    }
    assert project.records()[0]["source"] == "blender"


def test_cli_diagnostics_report_available_and_missing_dependencies(
    tmp_path, monkeypatch
):
    import importlib.metadata

    import cadgit.connectors as connectors

    project = store.Project.init(tmp_path / "project")

    def version(name):
        if name == "usd-core":
            raise importlib.metadata.PackageNotFoundError(name)
        return "test-runtime"

    monkeypatch.setattr(importlib.metadata, "version", version)
    monkeypatch.setattr(connectors, "rhino_endpoint", lambda: "fixture endpoint")
    monkeypatch.setattr(
        connectors,
        "blender_rpc",
        lambda code: (_ for _ in ()).throw(OSError("No Blender endpoint")),
    )
    first = invoke(project, "doctor")
    assert first.exit_code == 0
    result = json.loads(first.stdout)
    assert (
        result["packages"]["usd-core"] == "missing"
        and result["packages"]["PySide6"] == "test-runtime"
    )
    assert (
        result["rhino"] == "fixture endpoint"
        and result["blender"] == "No Blender endpoint"
    )
    monkeypatch.setattr(
        connectors,
        "rhino_endpoint",
        lambda: (_ for _ in ()).throw(OSError("No Rhino endpoint")),
    )
    monkeypatch.setattr(connectors, "blender_rpc", lambda code: "Blender API available")
    second = json.loads(invoke(project, "doctor").stdout)
    assert (
        second["rhino"] == "No Rhino endpoint"
        and second["blender"] == "Blender API available"
    )


def test_cli_ui_and_view_pass_exact_targets_and_return_launch_status(
    tmp_path, monkeypatch
):
    from test_history import box

    import cadgit.ui_v2 as ui

    project = store.Project.init(tmp_path / "project")
    record = project.ingest(box(tmp_path / "source.usda"))
    calls = []
    monkeypatch.delenv("CADGIT_INITIAL_REF", raising=False)
    monkeypatch.setattr(ui, "launch", lambda *args: (calls.append(args), 7)[1])
    screenshot = tmp_path / "capture.png"
    assert invoke(project, "ui", "--screenshot", screenshot).exit_code == 7
    assert calls[-1] == (project.root, str(screenshot))
    assert invoke(project, "view", record["id"]).exit_code == 7
    assert cli.os.environ["CADGIT_INITIAL_REF"] == record["id"] and calls[-1] == (
        project.root,
    )


def test_cli_invalid_exports_and_corruption_fail_without_new_artifacts(tmp_path):
    from test_history import box

    project = store.Project.init(tmp_path / "project")
    record = project.ingest(box(tmp_path / "source.usda"))
    assert invoke(project, "compose", "--input", "missing-path").exit_code != 0
    output = tmp_path / "output.usda"
    for arguments in [
        ("export", record["id"], "--output", output, "--format", "unknown"),
        (
            "export",
            record["id"],
            "--output",
            output,
            "--format",
            "usd",
            "--select",
            "/World/Part",
        ),
        ("autosnapshot", "unexpected"),
        ("autosnapshot", "on", "--interval", "5"),
    ]:
        assert invoke(project, *arguments).exit_code != 0
    assert not output.exists() and not project.records("assemblies")
    project.stage_path(record).write_bytes(b"corrupt archive")
    result = invoke(project, "verify", record["id"])
    assert result.exit_code == 5 and not json.loads(result.stdout)["ok"]


def test_cli_library_roundtrip_retains_provenance_and_pinned_revisions(tmp_path):
    project = store.Project.init(tmp_path / "project")
    source = tmp_path / "spec.txt"
    source.write_text("first definition")
    imported = invoke(
        project,
        "library",
        "import",
        source,
        "--provider",
        "test-provider",
        "--source-url",
        "https://example.invalid/spec",
        "--license-name",
        "Fixture license",
    )
    assert imported.exit_code == 0, imported.output
    first = json.loads(imported.stdout)
    assert first["provenance"]["provider"] == "test-provider"
    assert first["provenance"]["license"] == {"name": "Fixture license"}
    assert first["provenance"]["source_url"] == "https://example.invalid/spec"
    derivative = json.loads(
        invoke(project, "library", "import", source, "--parent", first["id"]).stdout
    )
    assert derivative["parents"] == [
        {"revision_id": first["id"], "role": "derived_from"}
    ]
    material = json.loads(invoke(project, "library", "material", "One").stdout)
    definition = tmp_path / "definition.json"
    store.atomic_json(definition, {"appearance": {"preview": {"roughness": 0.2}}})
    appearance = json.loads(
        invoke(project, "library", "material", "Two", "--definition", definition).stdout
    )
    mixed = invoke(
        project,
        "library",
        "recombine",
        "Combined",
        "--physical-from",
        material["id"],
        "--appearance-from",
        appearance["id"],
    )
    assert mixed.exit_code == 0, mixed.output
    combined = json.loads(mixed.stdout)
    assert combined["definition"]["appearance"]["preview"]["roughness"] == 0.2
    assert json.loads(invoke(project, "library", "used-by", appearance["id"]).stdout)
    destination = tmp_path / "export.txt"
    assert (
        invoke(
            project, "library", "export", first["id"], "--output", destination
        ).exit_code
        == 0
    )
    assert destination.read_bytes() == source.read_bytes()
    (Path(first["_directory"]) / first["entry_layer"]).write_bytes(b"damaged")
    failed = invoke(project, "library", "verify", first["id"])
    assert failed.exit_code == 5 and not json.loads(failed.stdout)["ok"]
