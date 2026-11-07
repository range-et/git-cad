"""Behavioral checks for the portable skill's read-only onboarding helper."""
import hashlib
import importlib.util
from pathlib import Path
from cadgit.store import Project
from test_history import box

MODULE=Path(__file__).resolve().parents[1]/'skills/cad-git/scripts/inspect_folder.py'
spec=importlib.util.spec_from_file_location('cadgit_skill_inspector',MODULE)
inspector=importlib.util.module_from_spec(spec);spec.loader.exec_module(inspector)


def contents(root):
    return {str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in root.rglob('*') if path.is_file() and not path.is_symlink()}


def test_inventory_preserves_existing_files_and_avoids_reserved_paths(tmp_path):
    (tmp_path/'models').mkdir();(tmp_path/'models/engine.3dm').write_bytes(b'opaque native model')
    (tmp_path/'models/engine.blend').write_bytes(b'opaque Blender model');(tmp_path/'models/engine.blend1').write_bytes(b'backup')
    (tmp_path/'materials').mkdir();(tmp_path/'materials/finish.png').write_bytes(b'opaque texture')
    (tmp_path/'cad-project').mkdir();box(tmp_path/'export.usda');(tmp_path/'older.usdz').write_bytes(b'opaque USD export')
    before=contents(tmp_path);paths=sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))
    report=inspector.inspect_folder(tmp_path,limit=1)
    assert contents(tmp_path)==before
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob('*'))==paths
    assert report['initialization']['suggested_project_root']==str(tmp_path.resolve()/'cad-project-2')
    assert report['initialization']['reserved_conflicts']==['materials']
    assert report['candidates']['rhino']['count']==report['candidates']['blender']['count']==1
    assert report['candidates']['backups']['count']==1
    assert report['candidates']['usd']['count']==2 and report['candidates']['usd']['omitted']==1


def test_offline_onboarding_retains_assets_and_rediscovers_its_project(tmp_path):
    (tmp_path/'materials').mkdir();native=tmp_path/'engine.3dm';native.write_bytes(b'keep editable original')
    source=box(tmp_path/'baseline.usda',.001)
    first=inspector.inspect_folder(tmp_path);p=Project.init(first['initialization']['suggested_project_root'])
    snapshot=p.ingest(source,'manual','Existing USD baseline');assert p.verify(snapshot['id'])['ok']
    second=inspector.inspect_folder(tmp_path)
    assert second['nested_project_configs']==['cad-project']
    assert second['initialization']['mode']=='existing_nested_config_needs_tool_validation'
    assert second['initialization']['suggested_project_root']==str(p.root)
    # The exported baseline is a candidate; the new archived package is not.
    assert second['candidates']['usd']['count']==1
    assert native.read_bytes()==b'keep editable original'


def test_malformed_config_and_symlinks_are_reported_without_following_assets(tmp_path):
    root=tmp_path/'design';root.mkdir();(root/'cadgit.json').write_text('{incomplete config')
    (root/'main').mkdir();(root/'main/user-export.usda').write_bytes(b'existing user export')
    outside=tmp_path/'outside';outside.mkdir();(outside/'private.blend').write_bytes(b'external asset')
    (root/'linked-assets').symlink_to(outside,target_is_directory=True)
    (root/'linked-scene.blend').symlink_to(outside/'private.blend')
    before=contents(root);report=inspector.inspect_folder(root)
    assert contents(root)==before and report['config']['readable'] is False
    assert report['warnings'] and report['initialization']['mode']=='existing_config_needs_tool_validation'
    assert report['candidates']['usd']['count']==1  # invalid config must not hide main/
    assert report['candidates']['blender']['count']==0
    assert report['symlinks_not_followed']['count']==2


def test_non_directory_source_cannot_be_selected_for_in_place_initialization(tmp_path):
    (tmp_path/'source').write_text('user data')
    report=inspector.inspect_folder(tmp_path)
    assert report['initialization']['mode']=='new_child_recommended'
    assert 'source (not a directory)' in report['initialization']['reserved_conflicts']
    assert (tmp_path/'source').read_text()=='user data'
