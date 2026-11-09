"""Real temporary archives and publication faults, never synthetic saved history."""

from pathlib import Path

import pytest
from test_robustness import assembled

import cadgit.store as store
from cadgit.library import Library
from cadgit.usd import assemble


@pytest.mark.parametrize("existing_main", [False, True])
def test_main_pointer_published_before_sync_failure_reports_committed_state(
    tmp_path, monkeypatch, existing_main
):
    project, capture, first = assembled(tmp_path)
    if existing_main:
        project.set_main(first["id"])
    second = assemble(
        project, [{"snapshot_id": capture["id"], "prim_path": "/World/Part"}]
    )
    originals = {
        Path(r["_directory"]) / "manifest.json": (
            Path(r["_directory"]) / "manifest.json"
        ).read_bytes()
        for r in [capture, first, second]
    }
    real_sync = store.fsync_dir
    calls = 0

    def fail_pointer_sync(path):
        nonlocal calls
        if Path(path) == project.root / "main":
            calls += 1
            if calls == 2:
                raise OSError("Injected pointer directory sync failure")
        return real_sync(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "fsync_dir", fail_pointer_sync)
        result = project.set_main(second["id"])
    assert result["id"] == second["id"]
    assert "publication_warning" in result
    assert "sync" in result["publication_warning"].lower()
    assert project.resolve("main")["id"] == second["id"]
    assert (project.root / "main/scene.usda").read_bytes() == project.main_scene_bytes(
        second
    )
    assert store.Project(project.root).resolve("main")["id"] == second["id"]
    assert all(path.read_bytes() == before for path, before in originals.items())


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_library_verifies_exact_previous_revision(tmp_path, damage):
    project = store.Project.init(tmp_path / "project")
    library = Library(project)
    source = tmp_path / "spec.txt"
    source.write_text("original")
    first = library.import_asset(source)
    source.write_text("revised")
    second = library.import_asset(
        source, asset_id=first["asset_id"], expected_revision=first["id"]
    )
    second_manifest = (Path(second["_directory"]) / "manifest.json").read_bytes()
    assert library.verify(second["id"])["ok"]
    if damage == "missing":
        Path(first["_directory"]).rename(tmp_path / "removed-parent")
    else:
        project.stage_path(first).write_text("damaged payload")
    result = library.verify(second["id"])
    assert not result["ok"]
    assert any("previous" in message for message in result["errors"])
    assert (
        Path(second["_directory"]) / "manifest.json"
    ).read_bytes() == second_manifest
    assert source.read_text() == "revised"


@pytest.mark.parametrize("operation", ["branch", "version"])
@pytest.mark.parametrize("failure", ["before-config", "after-config", "event"])
def test_config_publication_and_success_events_agree(
    tmp_path, monkeypatch, operation, failure
):
    project, capture, _ = assembled(tmp_path)
    config_path = project.root / "cadgit.json"
    before = config_path.read_bytes()
    old_events = set((project.root / "history/events").glob("*.json"))
    real_write = store.atomic_json
    real_event = project.event

    def write(path, value, *args, **kwargs):
        if Path(path) == config_path:
            if failure == "before-config":
                raise OSError("Injected config failure")
            if failure == "after-config":
                real_write(path, value, *args, **kwargs)
                raise OSError("Injected config sync failure")
        return real_write(path, value, *args, **kwargs)

    def event(kind, data):
        if failure == "event":
            raise OSError("Injected event failure")
        return real_event(kind, data)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "atomic_json", write)
        scoped.setattr(project, "event", event)

        def action():
            if operation == "branch":
                return project.branch(capture["source"], "trial", activate=True)
            return project.name_version(capture["id"], "trial")

        if failure == "before-config":
            with pytest.raises(OSError):
                action()
            assert config_path.read_bytes() == before
            assert set((project.root / "history/events").glob("*.json")) == old_events
            return
        result = action()
    assert result.get("publication_warning")
    config = store.read_json(config_path)
    if operation == "branch":
        assert config["active_branches"][capture["source"]] == "trial"
    else:
        assert config["versions"]["trial"] == capture["id"]
    assert project.config == config
    assert store.Project(project.root).config == config


def test_record_published_before_directory_sync_failure_returns_revision(
    tmp_path, monkeypatch
):
    project = store.Project.init(tmp_path / "project")
    library = Library(project)
    source = tmp_path / "spec.txt"
    source.write_text("original input")
    real_sync = store.fsync_dir

    def fail_after_publish(path):
        if Path(path) == library.root / "revisions":
            raise OSError("Injected archive sync failure")
        return real_sync(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "fsync_dir", fail_after_publish)
        result = library.import_asset(source)
    assert result.get("publication_warning")
    assert library.get(result["id"])["id"] == result["id"]
    assert library.verify(result["id"])["ok"]
    assert source.read_text() == "original input"
    assert len(library.records()) == 1


@pytest.mark.parametrize("consumer", ["snapshot", "assembly", "import"])
def test_scene_verification_detects_missing_exact_history_link(tmp_path, consumer):
    project, capture, assembly = assembled(tmp_path)
    if consumer == "assembly":
        record = assembly
    elif consumer == "snapshot":
        record = project.ingest(project.stage_path(capture), source=capture["source"])
    else:
        record = project.ingest(
            project.stage_path(capture),
            source="imported",
            metadata={"imported_from": capture["id"]},
        )
    assert project.verify(record["id"])["ok"]
    before = (Path(record["_directory"]) / "manifest.json").read_bytes()
    Path(capture["_directory"]).rename(tmp_path / "missing-capture")
    result = project.verify(record["id"])
    assert not result["ok"]
    assert any(capture["id"] in error for error in result["errors"])
    assert (Path(record["_directory"]) / "manifest.json").read_bytes() == before
    assert project.stage_path(
        record
    ).is_file()  # intact self-contained payload remains readable


def test_failed_capture_material_provenance_is_an_attempt_not_a_saved_snapshot(
    tmp_path, monkeypatch
):
    from test_history import box

    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "native.usda")
    shader = tmp_path / "material_Test.blend"
    shader.write_bytes(b"opaque archive fixture; not a real native renderer test")
    store.atomic_json(tmp_path / "materials.json", {shader.name: "Test"})
    real_commit = project.commit
    attempts = []

    def fail_snapshot(staging, destination, record):
        if record.get("source"):
            attempts.append(record["id"])
            raise OSError("Injected snapshot commit failure")
        return real_commit(staging, destination, record)

    with monkeypatch.context() as scoped:
        scoped.setattr(project, "commit", fail_snapshot)
        with pytest.raises(OSError):
            project.ingest(
                source,
                source="blender",
                metadata={"native_capture": True, "capture_id": "retry-1"},
            )
    material = project.records("materials")[0]
    assert material.get("capture_attempt_id") == attempts[0]
    assert "snapshot_id" not in material
    manifest = Path(material["_directory"]) / "manifest.json"
    original = manifest.read_bytes()
    retry = project.ingest(
        source,
        source="blender",
        metadata={"native_capture": True, "capture_id": "retry-1"},
    )
    assert retry["id"] != attempts[0]
    assert retry["metadata"]["native_materials"]["Test"] == material["id"]
    assert project.verify(retry["id"])["ok"]
    assert manifest.read_bytes() == original
    assert (
        project.ingest(
            source,
            source="blender",
            metadata={"native_capture": True, "capture_id": "retry-1"},
        )["id"]
        == retry["id"]
    )


@pytest.mark.parametrize("typed", [False, True])
def test_published_pointer_with_unreadable_readback_is_never_rolled_back(
    tmp_path, monkeypatch, typed
):
    project, capture, first = assembled(tmp_path)
    project.set_main(first["id"])
    second = assemble(
        project, [{"snapshot_id": capture["id"], "prim_path": "/World/Part"}]
    )
    pointer = project.root / "main/current.json"
    real_write, real_read = store.atomic_json, store.read_json
    published = False

    def write(path, value, *args, **kwargs):
        nonlocal published
        real_write(path, value, *args, **kwargs)
        if Path(path) == pointer:
            published = True
            cause = OSError("Injected postpublication failure")
            if typed:
                raise store.PublishedWriteError(str(pointer), cause)
            raise cause

    def read(path):
        if Path(path) == pointer and published:
            raise store.CadgitError("Injected unreadable pointer")
        return real_read(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "atomic_json", write)
        scoped.setattr(store, "read_json", read)
        if typed:
            result = project.set_main(second["id"])
            assert result["id"] == second["id"] and result.get("publication_warning")
        else:
            with pytest.raises(store.CadgitError, match="outcome is uncertain"):
                project.set_main(second["id"])
    assert real_read(pointer)["assembly_id"] == second["id"]
    assert (project.root / "main/scene.usda").read_bytes() == project.main_scene_bytes(
        second
    )
    assert store.Project(project.root).resolve("main")["id"] == second["id"]


@pytest.mark.parametrize("field", ["snapshot_id", "translation", "future_extension"])
def test_assembly_manifest_must_match_its_hashed_recipe(tmp_path, field):
    project, capture, assembly = assembled(tmp_path)
    other = project.ingest(project.stage_path(capture), source="other")
    manifest = Path(assembly["_directory"]) / "manifest.json"
    data = store.read_json(manifest)
    data["selections"][0][field] = {
        "snapshot_id": other["id"],
        "translation": [1, 2, 3],
        "future_extension": {"opaque": True},
    }[field]
    store.atomic_json(manifest, data)  # explicit corruption of a real saved archive
    result = project.verify(assembly["id"])
    assert not result["ok"]
    assert any("hashed recipe" in message for message in result["errors"])


def test_snapshot_additive_field_does_not_gain_assembly_semantics(tmp_path):
    project, capture, _ = assembled(tmp_path)
    manifest = Path(capture["_directory"]) / "manifest.json"
    data = store.read_json(manifest)
    data["selections"] = {"future_vendor": "opaque"}
    store.atomic_json(manifest, data)
    before = manifest.read_bytes()
    assert project.verify(capture["id"])["ok"]
    assert manifest.read_bytes() == before


@pytest.mark.parametrize("origin", ["snap_missing", "snap_", "", 123, ["unexpected"]])
def test_imported_lineage_must_be_exact_and_valid_before_publication(tmp_path, origin):
    project, capture, _ = assembled(tmp_path)
    before = [r["id"] for r in project.records()]
    with pytest.raises(store.CadgitError):
        project.ingest(
            project.stage_path(capture),
            source="imported",
            metadata={"imported_from": origin},
        )
    assert [r["id"] for r in project.records()] == before


@pytest.mark.parametrize("exclusive", [False, True])
def test_atomic_write_reports_postpublication_sync_failure_explicitly(
    tmp_path, monkeypatch, exclusive
):
    output = tmp_path / "payload"
    if not exclusive:
        output.write_bytes(b"old")

    def fail(path):
        raise OSError("directory sync unavailable")

    monkeypatch.setattr(store, "fsync_dir", fail)
    with pytest.raises(store.PublishedWriteError) as error:
        store.atomic_write(output, b"new", replace=not exclusive)
    assert Path(error.value.destination) == output
    assert isinstance(error.value.cause, OSError)
    assert output.read_bytes() == b"new"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("typed", [False, True])
def test_config_unknown_readback_does_not_claim_unchanged_state(
    tmp_path, monkeypatch, typed
):
    project = store.Project.init(tmp_path / "project")
    path = project.root / "cadgit.json"
    real_write, real_read = store.atomic_json, store.read_json
    published = False

    def write(target, value, *args, **kwargs):
        nonlocal published
        real_write(target, value, *args, **kwargs)
        if Path(target) == path:
            published = True
            cause = OSError("Injected postpublication failure")
            if typed:
                raise store.PublishedWriteError(str(path), cause)
            raise cause

    def read(target):
        if Path(target) == path and published:
            raise store.CadgitError("Injected unreadable configuration")
        return real_read(target)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "atomic_json", write)
        scoped.setattr(store, "read_json", read)
        if typed:
            result = project.branch("rhino", "published", activate=True)
            assert result.get("publication_warning")
        else:
            with pytest.raises(store.CadgitError, match="outcome is uncertain"):
                project.branch("rhino", "published", activate=True)
    assert store.Project(project.root).config["active_branches"]["rhino"] == "published"


@pytest.mark.parametrize("failed_sync", [1, 2])
def test_native_handoff_keeps_exact_lineage_after_published_sync_failure(
    tmp_path, monkeypatch, failed_sync
):
    from cadgit.handoff import create_native

    project, capture, _ = assembled(tmp_path)
    output = tmp_path / "working.usdz"
    sidecar = Path(str(output) + ".cadgit.json")
    real_sync = store.fsync_dir
    calls = 0

    def fail_sync(path):
        nonlocal calls
        if Path(path) == output.parent:
            calls += 1
            if calls == failed_sync:
                raise OSError("Injected handoff durability failure")
        return real_sync(path)

    monkeypatch.setattr(store, "fsync_dir", fail_sync)
    result = create_native(
        project,
        capture["id"],
        {"kind": "external", "command": ["viewer", "{usd}"]},
        output,
        launch=False,
    )
    assert output.is_file()
    assert store.read_json(sidecar)["source_id"] == capture["id"]
    assert result["source_id"] == capture["id"]
    assert "Injected handoff durability failure" in result["publication_warning"]
    assert project.verify(capture["id"])["ok"]
    original = output.read_bytes(), sidecar.read_bytes()
    with pytest.raises(store.CadgitError, match="already exists"):
        create_native(
            project,
            capture["id"],
            {"kind": "external", "command": ["viewer", "{usd}"]},
            output,
            launch=False,
        )
    assert (output.read_bytes(), sidecar.read_bytes()) == original


def test_failed_first_main_selection_restores_absent_projection(tmp_path, monkeypatch):
    project, _, assembly = assembled(tmp_path)
    scene = project.root / "main/scene.usda"
    scene.unlink()
    real_json = store.atomic_json

    def fail_pointer(path, value, *args, **kwargs):
        if Path(path).name == "current.json":
            raise OSError("Pointer rejected before publication")
        return real_json(path, value, *args, **kwargs)

    monkeypatch.setattr(store, "atomic_json", fail_pointer)
    with pytest.raises(OSError, match="Pointer rejected"):
        project.set_main(assembly["id"])
    assert not (project.root / "main/current.json").exists()
    assert not scene.exists()
    assert project.verify(assembly["id"])["ok"]


@pytest.mark.parametrize("kind", ["usd", "stl"])
def test_external_export_reports_published_file_on_directory_sync_failure(
    tmp_path, monkeypatch, kind
):
    from cadgit.usd import export_stl, export_usd

    project, capture, _ = assembled(tmp_path)
    output = tmp_path / ("export." + ("usdz" if kind == "usd" else "stl"))
    real_sync = store.fsync_dir

    def fail_output_sync(path):
        if Path(path) == output.parent:
            raise OSError("Injected export directory sync failure")
        return real_sync(path)

    monkeypatch.setattr(store, "fsync_dir", fail_output_sync)
    result = (export_usd if kind == "usd" else export_stl)(
        project, capture["id"], output=output
    )
    assert output.is_file() and output.stat().st_size > 0
    assert "Injected export directory sync failure" in result["publication_warning"]
    assert project.verify(capture["id"])["ok"]


@pytest.mark.parametrize("route", ["tip", "base", "duplicate"])
def test_ingest_rejects_damaged_parent_without_losing_incoming_capture(tmp_path, route):
    from test_history import box

    project = store.Project.init(tmp_path / "project")
    incoming = box(tmp_path / "incoming.usda")
    original = incoming.read_bytes()
    parent = project.ingest(incoming, "rhino", metadata={"capture_id": "same"})
    if route == "base":
        project.branch("rhino", "future", parent["id"], activate=True)
    project.stage_path(parent).write_bytes(b"damaged archive")
    manifests = {p: p.read_bytes() for p in project.root.rglob("manifest.json")}
    events = list((project.root / "history/events").iterdir())
    with pytest.raises(store.CadgitError, match="integrity verification"):
        project.ingest(
            incoming,
            "rhino",
            metadata={"capture_id": "same" if route == "duplicate" else "new"},
        )
    assert incoming.read_bytes() == original
    assert {p: p.read_bytes() for p in project.root.rglob("manifest.json")} == manifests
    assert list((project.root / "history/events").iterdir()) == events
    assert len(project.records()) == 1


@pytest.mark.parametrize("reference", [None, 4, {}, "", ["assetrev_missing"]])
def test_invalid_library_pin_reports_integrity_error_instead_of_crashing(
    tmp_path, reference
):
    project, _, assembly = assembled(tmp_path)
    manifest = Path(assembly["_directory"]) / "manifest.json"
    data = store.read_json(manifest)
    data["library_bindings"] = [{"library_material_revision": reference}]
    store.atomic_json(manifest, data)
    result = project.verify(assembly["id"])
    assert not result["ok"]
    assert "Invalid library material revision reference" in result["errors"]


@pytest.mark.parametrize("operation", ["write", "copy"])
@pytest.mark.parametrize("published", [True, False])
def test_temporary_cleanup_failure_preserves_correct_publication_outcome(
    tmp_path, monkeypatch, operation, published
):
    from cadgit.errors import PublishedWriteError

    source = tmp_path / "source"
    source.write_bytes(b"original content")
    destination = tmp_path / "destination"
    unlink = Path.unlink

    def reject_cleanup(path, *args, **kwargs):
        if path.suffix == ".tmp":
            raise OSError("Temporary cleanup denied")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "unlink", reject_cleanup)
        if not published:
            scoped.setattr(
                store.os,
                "link",
                lambda *args: (_ for _ in ()).throw(OSError("Publication denied")),
            )
        with pytest.raises(PublishedWriteError if published else OSError) as caught:
            if operation == "write":
                store.atomic_write(destination, source.read_bytes(), replace=False)
            else:
                store.publish_file(source, destination)
    if published:
        assert caught.value.destination == str(destination)
        assert destination.read_bytes() == b"original content"
    else:
        assert not isinstance(caught.value, PublishedWriteError)
        assert not destination.exists()
    assert source.read_bytes() == b"original content"


def test_exclusive_write_preserves_existing_destination(tmp_path):
    destination = tmp_path / "destination"
    destination.write_bytes(b"keep me")
    with pytest.raises(store.CadgitError, match="already exists"):
        store.atomic_write(destination, b"replacement", replace=False)
    assert destination.read_bytes() == b"keep me"
    assert list(tmp_path.iterdir()) == [destination]


def test_unreadable_marker_and_recipe_are_reported_as_corruption(tmp_path):
    project, capture, assembly = assembled(tmp_path)
    marker = Path(capture["_directory"]) / "COMMITTED"
    marker.write_bytes(b"\xff")
    assert "Unreadable commit marker" in project.verify(capture["id"])["errors"]
    recipe = Path(assembly["_directory"]) / "recipe.json"
    recipe.write_text("{broken")
    result = project.verify(assembly["id"])
    assert not result["ok"] and any(
        "recipe.json" in error for error in result["errors"]
    )


def test_invalid_source_branch_and_missing_project_are_actionable(tmp_path):
    from test_history import box

    with pytest.raises(store.CadgitError, match="Run git-cad init"):
        store.Project(tmp_path / "absent")
    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "part.usda")
    with pytest.raises(store.CadgitError, match="Source must"):
        project.ingest(source, "../escape")
    with pytest.raises(store.CadgitError, match="Branch names"):
        project.branch("rhino", "../escape")
    with pytest.raises(store.CadgitError, match="Invalid history offset"):
        project.resolve("rhino~not-a-number")
    assert not project.records()


def test_missing_library_revision_is_a_failed_verification_not_exception(tmp_path):
    library = Library(store.Project.init(tmp_path / "project"))
    result = library.verify("assetrev_absent")
    assert not result["ok"] and result["id"] == "assetrev_absent"
    with pytest.raises(store.CadgitError, match="Unknown"):
        library.get("assetrev_absent")


def test_native_capture_archives_images_and_detects_later_loss(tmp_path):
    from test_history import box

    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "native.usda")
    shader = tmp_path / "material_Test.blend"
    shader.write_bytes(b"opaque native graph archive")
    texture = tmp_path / "texture.png"
    texture.write_bytes(b"opaque image archive")
    store.atomic_json(
        tmp_path / "materials.json",
        {shader.name: {"name": "Test", "images": {"Albedo": str(texture)}}},
    )
    capture = project.ingest(source, "blender", metadata={"native_capture": True})
    material = project.records("materials")[0]
    archived = Path(material["_directory"]) / material["images"]["Albedo"]
    assert archived.read_bytes() == texture.read_bytes()
    assert project.verify(capture["id"])["ok"]
    texture.write_bytes(b"edited external original")
    assert archived.read_bytes() == b"opaque image archive"
    archived.unlink()
    result = project.verify(capture["id"])
    assert not result["ok"] and any(
        "Hash mismatch" in error for error in result["errors"]
    )


def test_native_capture_rejects_missing_declared_image_before_success(tmp_path):
    from test_history import box

    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "native.usda")
    original = source.read_bytes()
    shader = tmp_path / "material_Test.blend"
    shader.write_bytes(b"opaque native graph archive")
    store.atomic_json(
        tmp_path / "materials.json",
        {
            shader.name: {
                "name": "Test",
                "images": {"Albedo": str(tmp_path / "missing.png")},
            }
        },
    )
    with pytest.raises(store.CadgitError, match="Missing captured image"):
        project.ingest(source, "blender", metadata={"native_capture": True})
    assert source.read_bytes() == original
    assert not project.records() and not project.records("materials")


def test_cross_source_save_parent_is_rejected_but_import_provenance_is_valid(tmp_path):
    from test_history import box

    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "part.usda")
    rhino = project.ingest(source, "rhino")
    blender = project.ingest(source, "blender")
    project.branch("rhino", "future", rhino["id"], activate=True)
    config = store.read_json(project.root / "cadgit.json")
    config["branches"]["rhino"]["future"]["base"] = blender["id"]
    store.atomic_json(project.root / "cadgit.json", config)
    with pytest.raises(store.CadgitError, match="same source"):
        project.ingest(source, "rhino")
    assert len(project.records()) == 2
    imported = project.ingest(
        source, "rhino", branch="main", metadata={"imported_from": blender["id"]}
    )
    assert project.verify(imported["id"])["ok"]
    manifest = Path(imported["_directory"]) / "manifest.json"
    record = store.read_json(manifest)
    record["parent"] = blender["id"]
    store.atomic_json(manifest, record)
    result = project.verify(imported["id"])
    assert not result["ok"]
    assert any("same source" in error for error in result["errors"])


def test_native_capture_rejects_unbound_logical_material_and_preserves_source(
    tmp_path, monkeypatch
):
    from pxr import Sdf
    from test_history import box

    from cadgit.usd import open_stage

    project = store.Project.init(tmp_path / "project")
    material = Library(project).create_material("Logical")
    source = box(tmp_path / "native.usda")
    stage = open_stage(source)
    stage.GetPrimAtPath("/World/Part").CreateAttribute(
        "userProperties:cadgit:library_material_revision", Sdf.ValueTypeNames.String
    ).Set(material["id"])
    stage.GetRootLayer().Save()
    shader = tmp_path / "material_Test.blend"
    shader.write_bytes(b"opaque graph")
    original = source.read_bytes()
    monkeypatch.setattr(
        project,
        "event",
        lambda *args: (_ for _ in ()).throw(OSError("Event storage unavailable")),
    )
    with pytest.raises(store.CadgitError, match="no single bound native material"):
        project.ingest(source, "blender", metadata={"native_capture": True})
    assert not project.records() and source.read_bytes() == original


@pytest.mark.parametrize("fail_packaging", [False, True])
def test_native_capture_removes_stale_shader_pin_only_in_committed_copy(
    tmp_path, monkeypatch, fail_packaging
):
    from pxr import Sdf, UsdUtils
    from test_history import box

    from cadgit.usd import open_stage

    project = store.Project.init(tmp_path / "project")
    source = box(tmp_path / "native.usda")
    stage = open_stage(source)
    attribute = "userProperties:cadgit:material_revision"
    stage.GetPrimAtPath("/World/Part").CreateAttribute(
        attribute, Sdf.ValueTypeNames.String
    ).Set("mat_stale")
    stage.GetRootLayer().Save()
    original = source.read_bytes()
    package = UsdUtils.CreateNewUsdzPackage

    def guarded(asset, destination):
        if fail_packaging and Path(destination).name == "canonical.usdz":
            return False
        return package(asset, destination)

    monkeypatch.setattr(UsdUtils, "CreateNewUsdzPackage", guarded)
    if fail_packaging:
        with pytest.raises(store.CadgitError, match="canonical material bindings"):
            project.ingest(source, "blender", metadata={"native_capture": True})
        assert not project.records()
    else:
        result = project.ingest(source, "blender", metadata={"native_capture": True})
        committed = open_stage(project.stage_path(result))
        assert not committed.GetPrimAtPath("/World/Part").HasAttribute(attribute)
        assert project.verify(result["id"])["ok"]
    assert source.read_bytes() == original


def test_main_selection_event_failure_does_not_undo_published_pointer(
    tmp_path, monkeypatch
):
    project, _, assembly = assembled(tmp_path)
    monkeypatch.setattr(
        project,
        "event",
        lambda *args: (_ for _ in ()).throw(OSError("Event storage unavailable")),
    )
    result = project.set_main(assembly["id"])
    assert result["id"] == assembly["id"]
    assert "Event storage unavailable" in result["publication_warning"]
    assert store.Project(project.root).resolve("main")["id"] == assembly["id"]


@pytest.mark.parametrize("revision", [123, ""])
def test_malformed_assembly_selection_reference_fails_without_traversal(
    tmp_path, revision
):
    project, _, assembly = assembled(tmp_path)
    assembly["selections"][0]["snapshot_id"] = revision
    result = project.verify(assembly)
    assert not result["ok"]
    assert "Invalid selection revision reference" in result["errors"]


def test_failed_main_rollback_cannot_create_authoritative_main(tmp_path, monkeypatch):
    project, _, assembly = assembled(tmp_path)
    scene = project.root / "main/scene.usda"
    scene.unlink()
    write = store.atomic_json
    unlink = Path.unlink

    def fail_pointer(path, value, *args, **kwargs):
        if Path(path).name == "current.json":
            raise OSError("Pointer save denied")
        return write(path, value, *args, **kwargs)

    def fail_projection_cleanup(path, *args, **kwargs):
        if path == scene:
            raise OSError("Projection cleanup denied")
        return unlink(path, *args, **kwargs)

    with monkeypatch.context() as scoped:
        scoped.setattr(store, "atomic_json", fail_pointer)
        scoped.setattr(Path, "unlink", fail_projection_cleanup)
        with pytest.raises(OSError, match="Pointer save denied"):
            project.set_main(assembly["id"])
    assert not (project.root / "main/current.json").exists()
    reopened = store.Project(project.root)
    with pytest.raises(store.CadgitError, match="Main is empty"):
        reopened.resolve("main")
    assert reopened.verify(assembly["id"])["ok"]


def test_initialization_readback_failure_preserves_preexisting_user_files(
    tmp_path, monkeypatch
):
    root = tmp_path / "project"
    root.mkdir()
    original = root / "design.txt"
    original.write_bytes(b"user content")
    ignore = root / ".gitignore"
    ignore.write_bytes(b"user rule\n")
    write = store.atomic_json
    read = store.read_json

    def fail_config_after_publication(path, value, *args, **kwargs):
        result = write(path, value, *args, **kwargs)
        if Path(path) == root / "cadgit.json":
            raise OSError("Initialization completion unavailable")
        return result

    def unreadable_config(path):
        if Path(path) == root / "cadgit.json":
            raise store.CadgitError("Config readback denied")
        return read(path)

    monkeypatch.setattr(store, "atomic_json", fail_config_after_publication)
    monkeypatch.setattr(store, "read_json", unreadable_config)
    with pytest.raises(OSError, match="Initialization completion unavailable"):
        store.Project.init(root)
    assert original.read_bytes() == b"user content"
    assert ignore.read_bytes() == b"user rule\n"
    assert not (root / "history").exists()


def test_canonical_native_capture_preserves_packaged_texture_bytes(tmp_path):
    import numpy as np
    from pxr import Sdf, UsdUtils
    from test_texture_preview import textured_plane

    from cadgit.usd import meshes, open_stage

    source, image, pixels = textured_plane(tmp_path)
    stage = open_stage(source)
    stage.GetPrimAtPath("/World/Plane").CreateAttribute(
        "userProperties:cadgit:material_revision", Sdf.ValueTypeNames.String
    ).Set("mat_stale")
    stage.GetRootLayer().Save()
    original = source.read_bytes()
    project = store.Project.init(tmp_path / "project")
    capture = project.ingest(source, "blender", metadata={"native_capture": True})
    image.unlink()
    _, _, unresolved = UsdUtils.ComputeAllDependencies(
        Sdf.AssetPath(str(project.stage_path(capture)))
    )
    assert not unresolved
    part = meshes(project.stage_path(capture), include_textures=True)[0]
    np.testing.assert_array_equal(
        part["texture_maps"]["base_color"]["pixels"][:, :, :3], pixels
    )
    assert source.read_bytes() == original
