from pathlib import Path
from threading import Event
import json
import numpy as np
import pyvista as pv
import pytest
from pxr import Usd,UsdGeom,Vt
from cadgit.store import Project,CadgitError,file_digest
from cadgit.brep import prepare_job,verify_job,list_jobs,runtime_status
from test_history import box


def test_prepare_pins_inputs_and_restores_units(tmp_path):
    project=Project.init(tmp_path/'project');source=box(tmp_path/'source.usda',.001)
    snapshot=project.ingest(source);before=file_digest(project.stage_path(snapshot))
    result=prepare_job(project,snapshot['id']);request=result['request']
    assert result['status']=='prepared' and request['source_id']==snapshot['id']
    assert not list(Path(result['_directory']).rglob('*.step'))
    part=request['parts'][0];points=pv.read(Path(result['_directory'])/part['input']).points
    center=np.array(part['normalization']['center_m']);scale=part['normalization']['scale_m']
    normalized=(points-center)/scale
    assert np.isclose(np.max(np.ptp(normalized,axis=0)),1.8)
    assert np.allclose(normalized*scale+center,points)
    assert np.max(np.ptp(points,axis=0))==pytest.approx(.002)
    assert verify_job(project,result['id'])['ok']
    assert file_digest(project.stage_path(snapshot))==before
    assert not (project.root/'main/current.json').exists()
    assert len(list_jobs(project))==1


@pytest.mark.parametrize('center',[(3,0,0),(1,1,1)])
def test_disconnected_bodies_require_explicit_split(tmp_path,center):
    project=Project.init(tmp_path/'project');stage=Usd.Stage.CreateNew(str(tmp_path/'two.usda'))
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,'Z')
    a=pv.Cube();b=pv.Cube(center=center);mesh=a.merge(b,merge_points=False).triangulate()
    prim=UsdGeom.Mesh.Define(stage,'/Parts');prim.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(mesh.points))
    faces=mesh.faces.reshape(-1,4);prim.CreateFaceVertexCountsAttr(faces[:,0].tolist());prim.CreateFaceVertexIndicesAttr(faces[:,1:].ravel().tolist());prim.CreateSubdivisionSchemeAttr('none');stage.GetRootLayer().Save()
    source=project.ingest(tmp_path/'two.usda')
    with pytest.raises(CadgitError,match='disconnected'):prepare_job(project,source['id'])
    assert not list_jobs(project)
    result=prepare_job(project,source['id'],split_components=True)
    parts=result['request']['parts'];assert len(parts)==2
    assert sorted(p['normalization']['center_m'][0] for p in parts)==pytest.approx([0,center[0]])
    assert all(p['source_prim']=='/Parts' and p['source_component_count']==2 for p in parts)
    assert result['warnings']


def test_cancel_and_corruption_are_not_success(tmp_path):
    project=Project.init(tmp_path/'project');source=project.ingest(box(tmp_path/'a.usda'))
    event=Event();event.set()
    with pytest.raises(CadgitError,match='cancelled'):prepare_job(project,source['id'],cancelled=event)
    assert not list_jobs(project)
    job=prepare_job(project,source['id']);path=Path(job['_directory'])/'request.json'
    value=json.loads(path.read_text());value['status']='completed';path.write_text(json.dumps(value))
    assert not verify_job(project,job['id'])['ok']


def test_storage_ownership_and_symlink_refusal(tmp_path):
    project=Project.init(tmp_path/'project');source=project.ingest(box(tmp_path/'a.usda'))
    root=project.root/'artifacts/brep_jobs';root.mkdir();(root/'user.txt').write_text('keep')
    with pytest.raises(CadgitError,match='not owned'):prepare_job(project,source['id'])
    assert (root/'user.txt').read_text()=='keep'
    (root/'user.txt').unlink();root.rmdir();root.symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(CadgitError,match='symlink'):prepare_job(project,source['id'])


def test_runtime_optional_and_unavailable_is_honest(monkeypatch):
    monkeypatch.delenv('CADGIT_DUALBREP_PYTHON',raising=False);monkeypatch.delenv('CADGIT_DUALBREP_CHECKOUT',raising=False)
    status=runtime_status()
    assert status['preparation_available'] and not status['execution_available']
    assert not status['cuda_prerequisites_ready'] and status['missing']


def test_job_symlink_and_malformed_request(tmp_path):
    project=Project.init(tmp_path/'project');source=project.ingest(box(tmp_path/'a.usda'))
    job=prepare_job(project,source['id']);directory=Path(job['_directory'])
    (directory/'request.json').write_text('[]')
    result=verify_job(project,job['id']);assert not result['ok'] and any('object' in e for e in result['errors'])
    outside=tmp_path/'moved';directory.rename(outside);directory.symlink_to(outside,target_is_directory=True)
    with pytest.raises(CadgitError,match='symlink'):verify_job(project,job['id'])


def test_small_part_far_from_origin_keeps_double_precision(tmp_path):
    project=Project.init(tmp_path/'project');source=project.ingest(box(tmp_path/'a.usda',.001,offset=(1e9,0,0)))
    job=prepare_job(project,source['id']);part=job['request']['parts'][0]
    data=(Path(job['_directory'])/part['input']).read_bytes();header,payload=data.split(b'end_header\n',1)
    assert b'property double x' in header
    points=np.frombuffer(payload,dtype='<f8',count=part['points']*3).reshape(-1,3)
    assert points.dtype==np.float64
    assert np.ptp(points,axis=0)==pytest.approx([.002,.002,.002])
