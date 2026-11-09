"""Inbox recovery must preserve frozen captures until their archive is healthy."""

import pytest
from test_history import box

import cadgit.service as service
from cadgit.store import Project, atomic_json, read_json


def test_receipt_recovery_does_not_discard_native_capture_when_archive_is_corrupt(
    tmp_path,
):
    project = Project.init(tmp_path / "project")
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    source = box(inbox / "scene.usda")
    native = inbox / "native_capture.3dm"
    native.write_bytes(b"frozen native source for recovery")
    atomic_json(inbox / "ready.json", {"file": "scene.usda", "source": "rhino"})
    capture = project.ingest(
        source, "rhino", metadata={"capture_id": project.config["id"] + ":capture"}
    )
    project.stage_path(capture).write_bytes(b"damaged committed archive")
    original = source.read_bytes()
    assert service.process_inbox(project) == 0
    assert native.read_bytes() == b"frozen native source for recovery"
    assert source.read_bytes() == original
    assert not (inbox / "receipt.json").exists()
    assert "integrity" in read_json(inbox / "error.json")["error"]
    assert len(project.records()) == 1


def test_service_lifecycle_owns_lock_stops_and_rejects_second_daemon(
    tmp_path, monkeypatch
):
    import subprocess
    import sys
    import time

    project = Project.init(tmp_path / "project")
    processes = []
    spawn = subprocess.Popen

    def tracked(*args, **kwargs):
        process = spawn(*args, **kwargs)
        if "cadgit.service" in args[0]:
            processes.append(process)
        return process

    monkeypatch.setattr(service.subprocess, "Popen", tracked)
    try:
        started = service.start(project)
        deadline = time.monotonic() + 10
        while not started.get("running") and time.monotonic() < deadline:
            time.sleep(0.05)
            started = service.status(project)
        assert started["running"] and started["healthy"] and not started["busy"]
        assert service.start(project)["pid"] == started["pid"]
        assert len(processes) == 1
        result = subprocess.run(
            [sys.executable, "-m", "cadgit.service", str(project.root)],
            capture_output=True,
            timeout=15,
        )
        assert result.returncode == 0
        assert service.status(project)["pid"] == started["pid"]
        assert service.stop(project) == {"stopping": True}
        processes[0].wait(timeout=10)
        assert not service.status(project)["running"]
        assert service.stop(project) == {"stopping": False}
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def test_service_autocapture_failure_records_app_and_exits_cleanly(
    tmp_path, monkeypatch
):
    import signal

    import cadgit.connectors as connectors

    project = Project.init(tmp_path / "project")
    config = read_json(project.root / "cadgit.json")
    config["tool_interval_seconds"] = 1
    atomic_json(project.root / "cadgit.json", config)
    handlers = {}
    calls = []
    clock = iter([0, 31, 31])
    monkeypatch.setattr(
        service.signal,
        "signal",
        lambda number, handler: handlers.__setitem__(number, handler),
    )
    monkeypatch.setattr(service.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(service.time, "sleep", lambda delay: handlers[signal.SIGTERM]())

    def capture(target, app, respect_binding):
        calls.append((target.root, app, respect_binding))
        if app == "blender":
            raise OSError("Native application unavailable")

    monkeypatch.setattr(connectors, "capture", capture)
    service.run(project.root)
    assert calls == [(project.root, "rhino", True), (project.root, "blender", True)]
    events = [
        read_json(path) for path in (project.root / "history/events").glob("*.json")
    ]
    failures = [
        event["data"] for event in events if event["kind"] == "autosnapshot_failed"
    ]
    assert failures == [{"app": "blender", "error": "Native application unavailable"}]
    assert not (project.root / ".cadgit/service.json").exists()
    assert not service._lock_held(project)


@pytest.mark.parametrize("already_committed", [False, True])
def test_receipt_recovery_uses_source_and_capture_identity(tmp_path, already_committed):
    project = Project.init(tmp_path / "project")
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    source = box(inbox / "scene.usda")
    native = inbox / "native_capture.3dm"
    native.write_bytes(b"frozen Rhino input")
    capture_id = project.config["id"] + ":capture"
    if already_committed:
        expected = project.ingest(source, "rhino", metadata={"capture_id": capture_id})
    foreign = project.ingest(source, "blender", metadata={"capture_id": capture_id})
    atomic_json(inbox / "ready.json", {"file": "scene.usda", "source": "rhino"})
    assert service.process_inbox(project) == (0 if already_committed else 1)
    receipt = read_json(inbox / "receipt.json")
    assert receipt["snapshot_id"] != foreign["id"]
    assert project.resolve(receipt["snapshot_id"])["source"] == "rhino"
    if already_committed:
        assert receipt["snapshot_id"] == expected["id"]
    assert len(project.records()) == 2
    assert native.exists() is already_committed
    if already_committed:
        assert "cleanup_warning" in receipt


@pytest.mark.parametrize("changed", ["ready.json", "scene.usda", "native_capture.3dm"])
def test_changed_recovery_inputs_survive_until_original_identity_is_restored(
    tmp_path, monkeypatch, changed
):
    project = Project.init(tmp_path / "project")
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    box(inbox / "scene.usda")
    (inbox / "native_capture.3dm").write_bytes(b"original frozen native capture")
    atomic_json(inbox / "ready.json", {"file": "scene.usda", "source": "rhino"})
    write = service.atomic_json

    def no_receipt(path, value):
        if path.name == "receipt.json":
            raise OSError("Receipt unavailable")
        return write(path, value)

    with monkeypatch.context() as scoped:
        scoped.setattr(service, "atomic_json", no_receipt)
        assert service.process_inbox(project) == 0
    assert len(project.records()) == 1
    path = inbox / changed
    original = path.read_bytes()
    if changed == "ready.json":
        atomic_json(
            path,
            {"file": "scene.usda", "source": "rhino", "label": "Changed after capture"},
        )
    else:
        path.write_bytes(original + b"changed")
    changed_bytes = path.read_bytes()
    assert service.process_inbox(project) == 0
    assert not (inbox / "receipt.json").exists()
    assert path.read_bytes() == changed_bytes
    assert (inbox / "native_capture.3dm").exists()
    assert "inputs changed" in read_json(inbox / "error.json")["error"]
    path.write_bytes(original)
    assert service.process_inbox(project) == 0
    assert read_json(inbox / "receipt.json")["recovered"]
    assert not (inbox / "native_capture.3dm").exists()
    assert not (inbox / "error.json").exists()
    assert len(project.records()) == 1


def test_input_change_during_ingest_prevents_cleanup_and_false_receipt(
    tmp_path, monkeypatch
):
    project = Project.init(tmp_path / "project")
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    box(inbox / "scene.usda")
    native = inbox / "native_capture.3dm"
    native.write_bytes(b"original")
    atomic_json(inbox / "ready.json", {"file": "scene.usda", "source": "rhino"})
    ingest = project.ingest

    def changed(*args, **kwargs):
        result = ingest(*args, **kwargs)
        native.write_bytes(b"later capture")
        return result

    monkeypatch.setattr(project, "ingest", changed)
    assert service.process_inbox(project) == 0
    assert native.read_bytes() == b"later capture"
    assert not (inbox / "receipt.json").exists()
    assert "changed during ingestion" in read_json(inbox / "error.json")["error"]
    assert len(project.records()) == 1


def test_recovery_validates_file_containment_before_using_prior_capture(tmp_path):
    project = Project.init(tmp_path / "project")
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    source = box(tmp_path / "outside.usda")
    native = inbox / "native_capture.3dm"
    native.write_bytes(b"keep frozen input")
    project.ingest(
        source, "rhino", metadata={"capture_id": project.config["id"] + ":capture"}
    )
    atomic_json(inbox / "ready.json", {"file": str(source), "source": "rhino"})
    assert service.process_inbox(project) == 0
    assert native.read_bytes() == b"keep frozen input"
    assert not (inbox / "receipt.json").exists()
    assert "Unsafe inbox path" in read_json(inbox / "error.json")["error"]


@pytest.mark.parametrize("identity", [[], {}, 3, True, ""])
def test_invalid_new_capture_identity_is_rejected_without_publication(
    tmp_path, identity
):
    from cadgit.errors import CadgitError

    project = Project.init(tmp_path / "project")
    source = box(tmp_path / "source.usda")
    with pytest.raises(CadgitError, match="Capture identity"):
        project.ingest(source, metadata={"capture_id": identity})
    assert not project.records()


def test_malformed_legacy_capture_identity_does_not_block_valid_inbox(tmp_path):
    from pathlib import Path

    project = Project.init(tmp_path / "project")
    source = box(tmp_path / "source.usda")
    old = project.ingest(source, "blender")
    manifest = Path(old["_directory"]) / "manifest.json"
    record = read_json(manifest)
    record["metadata"]["capture_id"] = ["invalid"]
    atomic_json(manifest, record)
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    box(inbox / "scene.usda")
    atomic_json(inbox / "ready.json", {"file": "scene.usda", "source": "rhino"})
    assert service.process_inbox(project) == 1
    assert (
        project.resolve(read_json(inbox / "receipt.json")["snapshot_id"])["source"]
        == "rhino"
    )


def test_change_during_recovery_verification_preserves_native_input(
    tmp_path, monkeypatch
):
    project = Project.init(tmp_path / "project")
    inbox = project.root / ".cadgit/inbox/capture"
    inbox.mkdir()
    box(inbox / "scene.usda")
    native = inbox / "native_capture.3dm"
    native.write_bytes(b"original frozen capture")
    atomic_json(inbox / "ready.json", {"file": "scene.usda", "source": "rhino"})
    write = service.atomic_json

    def fail_receipt(path, value):
        if path.name == "receipt.json":
            raise OSError("Receipt unavailable")
        return write(path, value)

    with monkeypatch.context() as scoped:
        scoped.setattr(service, "atomic_json", fail_receipt)
        service.process_inbox(project)
    verify = project.verify

    def change_after_verify(record):
        result = verify(record)
        native.write_bytes(b"changed while verifying")
        return result

    monkeypatch.setattr(project, "verify", change_after_verify)
    assert service.process_inbox(project) == 0
    assert native.read_bytes() == b"changed while verifying"
    assert not (inbox / "receipt.json").exists()
    assert "inputs changed" in read_json(inbox / "error.json")["error"]


@pytest.mark.parametrize("escape", ["capture", "inbox", "lock", "marker"])
def test_unsafe_inbox_links_cannot_write_receipts_or_remove_external_inputs(
    tmp_path, escape, capsys
):
    from cadgit.errors import CadgitError

    project = Project.init(tmp_path / "project")
    external = tmp_path / "external"
    external.mkdir()
    box(external / "scene.usda")
    (external / "native_capture.3dm").write_bytes(b"external native original")
    atomic_json(external / "ready.json", {"source": "rhino", "file": "scene.usda"})
    inbox = project.root / ".cadgit/inbox"
    if escape == "inbox":
        inbox.rmdir()
        inbox.symlink_to(external, target_is_directory=True)
    elif escape == "capture":
        (inbox / "capture").symlink_to(external, target_is_directory=True)
    else:
        capture = inbox / "capture"
        capture.mkdir()
        box(capture / "scene.usda")
        if escape == "marker":
            (capture / "ready.json").symlink_to(external / "ready.json")
        else:
            atomic_json(
                capture / "ready.json", {"source": "rhino", "file": "scene.usda"}
            )
            (capture / "ingest.lock").symlink_to(external / "native_capture.3dm")
    original = {path: path.read_bytes() for path in external.iterdir()}
    if escape == "inbox":
        with pytest.raises(CadgitError, match="Unsafe inbox"):
            service.process_inbox(project)
    else:
        assert service.process_inbox(project) == 0
        assert "Unsafe inbox capture skipped" in capsys.readouterr().out
    assert {path: path.read_bytes() for path in external.iterdir()} == original
    assert not project.records()
