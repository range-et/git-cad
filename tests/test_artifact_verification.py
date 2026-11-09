"""Returned print artifact IDs verify without becoming scene references."""
from pathlib import Path

import pytest

from cadgit.errors import CadgitError
from cadgit.store import Project, file_digest
from cadgit.usd import export_stl
from test_history import box


@pytest.fixture
def printed(tmp_path):
    project = Project.init(tmp_path / 'project')
    source = project.ingest(box(tmp_path / 'box.usda'))
    artifact = export_stl(project, source['id'])
    return project, source, artifact


def test_print_id_verifies_read_only_and_is_not_a_scene(printed):
    project, source, artifact = printed
    before = {p: file_digest(p) for p in project.root.rglob('*') if p.is_file()}
    result = project.verify(artifact['id'])
    assert result == {'id': artifact['id'], 'ok': True, 'errors': []}
    assert project.verify(source['id'])['ok']
    with pytest.raises(CadgitError, match='Unknown or ambiguous reference'):
        project.resolve(artifact['id'])
    assert {p: file_digest(p) for p in project.root.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('payload', ['part.stl', 'validation.json'])
def test_print_payload_corruption_fails_then_restoration_verifies(printed, payload):
    project, _, artifact = printed
    path = Path(artifact['_directory']) / payload
    original = path.read_bytes()
    path.write_bytes(b'corrupt')
    result = project.verify(artifact['id'])
    assert not result['ok'] and any('Hash mismatch: ' + payload in error for error in result['errors'])
    path.write_bytes(original)
    assert project.verify(artifact['id'])['ok']


def test_print_unknown_and_abbreviated_ids_do_not_resolve(printed):
    project, _, artifact = printed
    for ref in ('print_does_not_exist', artifact['id'][:-1]):
        with pytest.raises(CadgitError, match='Unknown or ambiguous print artifact'):
            project.verify(ref)


def test_print_commit_marker_mismatch_is_not_success(printed):
    project, _, artifact = printed
    (Path(artifact['_directory']) / 'COMMITTED').write_text('print_wrong')
    result = project.verify(artifact['id'])
    assert not result['ok'] and 'Commit marker does not match the record ID' in result['errors']


def test_print_id_does_not_verify_an_external_symlink(printed, tmp_path):
    project, _, artifact = printed
    directory = Path(artifact['_directory'])
    outside = tmp_path / 'external-artifact'
    directory.rename(outside)
    directory.symlink_to(outside, target_is_directory=True)
    with pytest.raises(CadgitError, match='Unsafe print artifact archive'):
        project.verify(artifact['id'])


def test_duplicate_print_manifest_ids_are_rejected(printed):
    import shutil
    project, _, artifact = printed
    directory = Path(artifact['_directory'])
    shutil.copytree(directory, directory.with_name('duplicate'))
    with pytest.raises(CadgitError, match='Unknown or ambiguous print artifact'):
        project.verify(artifact['id'])


def test_malformed_print_manifest_is_not_verified(printed):
    project, _, artifact = printed
    (Path(artifact['_directory']) / 'manifest.json').write_text('[]')
    with pytest.raises(CadgitError, match='Unknown or ambiguous print artifact'):
        project.verify(artifact['id'])
