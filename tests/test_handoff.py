import json
import numpy as np
import pytest
import rhino3dm as r
from cadgit.store import Project,CadgitError
from cadgit.handoff import create_native,targets,validate_targets
from test_history import box


def test_new_rhino_file_retains_lineage_and_units(tmp_path):
    p=Project.init(tmp_path/'project');snap=p.ingest(box(tmp_path/'input.usda',.001,'Y',(10,20,30)),'blender')
    output=tmp_path/'working.3dm';result=create_native(p,snap['id'],{'kind':'rhino'},output,launch=False)
    assert json.loads((tmp_path/'working.3dm.cadgit.json').read_text())['source_id']==snap['id']
    model=r.File3dm.Read(str(output));assert model.Settings.ModelUnitSystem==r.UnitSystem.Millimeters
    assert len(model.Objects)==1
    attrs=model.Objects[0].Attributes
    assert attrs.GetUserString('cadgit_source_snapshot')==snap['id']
    points=np.array([[v.X,v.Y,v.Z] for v in model.Objects[0].Geometry.Vertices])
    assert np.allclose(points.mean(0),[10,-30,20])
    assert result['representation']=='tessellated_mesh'
    assert any(json.loads(f.read_text())['kind']=='native_handoff' for f in (p.root/'history/events').glob('*.json'))
    with pytest.raises(CadgitError,match='already exists'):create_native(p,snap['id'],{'kind':'rhino'},output,False)
    assert p.verify(snap['id'])['ok']


def test_invalid_external_target_leaves_no_native_file(tmp_path):
    p=Project.init(tmp_path/'project');snap=p.ingest(box(tmp_path/'input.usda'))
    with pytest.raises(CadgitError,match='command argument list'):
        create_native(p,snap['id'],{'kind':'external'},tmp_path/'new.usdz',False)
    assert not (tmp_path/'new.usdz').exists()
    assert not (tmp_path/'new.usdz.cadgit.json').exists()


@pytest.mark.parametrize('value', [
    None, {}, [None], [{'label':4,'kind':'rhino'}],
    [{'label':'Broken','kind':'unknown'}],
    [{'label':'Broken','kind':['rhino']}],
    [{'label':'Broken','kind':'blender','executable':4}],
    [{'label':'Broken','kind':'rhino','extension':'.blend'}],
    [{'label':'Broken','kind':'external','command':['viewer']}],
    [{'label':'Broken','kind':'external','command':['', '{usd}']}],
])
def test_invalid_application_targets_rejected(value):
    with pytest.raises(CadgitError):
        validate_targets(value)


def test_application_targets_normalize_extensions_and_preserve_extensions():
    assert validate_targets([{'label':'Rhino','kind':'rhino','future':{'flag':True}}]) == [
        {'label':'Rhino','kind':'rhino','extension':'.3dm','future':{'flag':True}}]


def test_external_target_without_file_placeholder_publishes_nothing(tmp_path):
    p=Project.init(tmp_path/'project');snap=p.ingest(box(tmp_path/'input.usda'))
    output=tmp_path/'working.usdz'
    with pytest.raises(CadgitError,match=r'include \{usd\}'):
        create_native(p,snap['id'],{'kind':'external','command':['viewer']},output,False)
    assert not output.exists()
    assert not output.with_name(output.name+'.cadgit.json').exists()
    assert not list((p.root/'.cadgit/staging').glob('handoff_*'))
