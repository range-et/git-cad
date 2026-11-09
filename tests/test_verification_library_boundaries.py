"""Library boundary failures use real archives and retain corrupt evidence."""

from pathlib import Path

import pytest
from PIL import Image

from cadgit.library import Library, infer_kind, reference, web_url
from cadgit.store import CadgitError, Project, atomic_json, read_json


@pytest.mark.parametrize(
    "extension,kind",
    [
        (suffix, kind)
        for kind, suffixes in {
            "image": ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp", "exr", "hdr"],
            "shader": ["blend", "mtlx", "sbsar"],
            "document": ["pdf", "txt", "md", "csv", "json", "html"],
            "other": ["unknown", "bin", ""],
        }.items()
        for suffix in suffixes
    ],
)
def test_file_kind_contract_is_case_insensitive(extension, kind):
    assert infer_kind("asset." + extension) == kind
    assert infer_kind("asset." + extension.upper()) == kind


@pytest.mark.parametrize(
    "value", [None, 123, [], {}, {"revision_id": None}, {"revision_id": 1}]
)
def test_invalid_reference_is_actionable(value):
    with pytest.raises(CadgitError, match="exact revision_id"):
        reference(value)


@pytest.mark.parametrize(
    "value",
    ["https://[", "http://", "file:///tmp/source", "javascript:alert(1)", None, 123],
)
def test_invalid_source_urls_are_rejected(value):
    assert not web_url(value)


def test_unowned_library_reports_issues_and_never_changes_user_files(tmp_path):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    library.root.mkdir()
    original = library.root / "user.data"
    original.write_bytes(b"valuable input")
    assert library.records() == [] and library.issues
    with pytest.raises(CadgitError, match="not a Git CAD library"):
        library.records(strict=True)
    assert original.read_bytes() == b"valuable input"


@pytest.mark.parametrize(
    "corruption",
    ["json", "required-feature", "directory-name", "symlink", "missing-marker"],
)
def test_corrupt_revision_is_reported_without_rewriting(tmp_path, corruption):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    record = library.create_material("Original")
    directory = Path(record["_directory"])
    manifest = directory / "manifest.json"
    if corruption == "json":
        manifest.write_text("not JSON")
    elif corruption == "required-feature":
        value = read_json(manifest)
        value["required_features"].append("future.unsupported")
        atomic_json(manifest, value)
    elif corruption == "directory-name":
        directory.rename(directory.with_name("wrong-name"))
        directory = directory.with_name("wrong-name")
        manifest = directory / "manifest.json"
    elif corruption == "symlink":
        original = tmp_path / "archive-preserved"
        directory.rename(original)
        directory.symlink_to(original, target_is_directory=True)
    else:
        (directory / "COMMITTED").unlink()
    before = manifest.read_bytes()
    assert library.records() == []
    if corruption == "missing-marker":
        assert library.records(strict=True) == []
    else:
        assert library.issues
        with pytest.raises(CadgitError):
            library.records(strict=True)
    assert manifest.read_bytes() == before


def test_missing_definition_payload_is_a_verification_failure(tmp_path):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    record = library.create_material("Original")
    project.stage_path(record).unlink()
    result = library.verify(record["id"])
    assert not result["ok"] and any(
        "Cannot read JSON" in message for message in result["errors"]
    )


def test_native_graph_images_pin_the_exact_image_revision(tmp_path):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    image = tmp_path / "input.png"
    Image.new("RGB", (2, 2), "red").save(image)
    first = library.import_asset(image)
    material = library.create_material(
        "Graph",
        {"appearance": {"graph_images": {"Albedo": {"revision_id": first["id"]}}}},
    )
    Image.new("RGB", (2, 2), "blue").save(image)
    second = library.import_asset(
        image, asset_id=first["asset_id"], expected_revision=first["id"]
    )
    assert material["dependencies"] == [
        {"revision_id": first["id"], "role": "graph_image:Albedo"}
    ]
    assert second["id"] not in str(material["definition"])
    assert library.verify(material["id"])["ok"]
    with pytest.raises(CadgitError, match="image name"):
        library.create_material(
            "Invalid", {"appearance": {"graph_images": {" ": first["id"]}}}
        )


def test_cyclic_previous_links_are_rejected_and_left_for_recovery(tmp_path):
    project = Project.init(tmp_path / "project")
    library = Library(project)
    record = library.create_material("Original")
    manifest = Path(record["_directory"]) / "manifest.json"
    value = read_json(manifest)
    value["parents"] = [{"revision_id": record["id"], "role": "previous"}]
    atomic_json(manifest, value)
    before = manifest.read_bytes()
    result = library.verify(record["id"])
    assert not result["ok"] and any("Cyclic" in message for message in result["errors"])
    assert manifest.read_bytes() == before
