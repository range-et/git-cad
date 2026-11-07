from pathlib import Path
import hashlib,json
import numpy as np
import pytest
from pxr import Usd,UsdGeom,Gf,Vt
from cadgit.store import Project,CadgitError
from cadgit.usd import assemble,meshes,export_stl,open_stage


def box(path,units=1.0,axis='Z',offset=(0,0,0)):
    stage=Usd.Stage.CreateNew(str(path));world=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(world.GetPrim())
    UsdGeom.SetStageMetersPerUnit(stage,units);UsdGeom.SetStageUpAxis(stage,axis)
    world.AddTranslateOp().Set(Gf.Vec3d(*offset))
    m=UsdGeom.Mesh.Define(stage,'/World/Part')
    m.GetPointsAttr().Set([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)])
    m.GetFaceVertexCountsAttr().Set([4]*6);m.GetFaceVertexIndicesAttr().Set([0,3,2,1,4,5,6,7,0,1,5,4,1,2,6,5,2,3,7,6,3,0,4,7]);m.GetSubdivisionSchemeAttr().Set('none')
    stage.GetRootLayer().Save();return path


def test_immutable_snapshot_and_deliberate_main(tmp_path):
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda')
    first=p.ingest(src,'rhino','initial');archive=p.stage_path(first);digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    a=assemble(p,[{'snapshot_id':first['id'],'prim_path':'/World/Part','label':'Body'}]);p.set_main(a['id'])
    old=(p.root/'main/scene.usda').read_bytes()
    # Native source can disappear; the committed snapshot is self-contained.
    src.unlink();second=p.ingest(archive,'rhino','second')
    assert second['parent']==first['id']
    assert (p.root/'main/scene.usda').read_bytes()==old
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==digest
    assert p.verify(first['id'])['ok']
    assert UsdGeom.GetStageMetersPerUnit(open_stage(p.root/'main/scene.usda'))==1
    assert UsdGeom.GetStageUpAxis(open_stage(p.root/'main/scene.usda'))=='Z'


def test_y_up_and_parent_transform_roundtrip(tmp_path):
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda',0.001,'Y',(10,20,30));r=p.ingest(src,'rhino')
    before=meshes(p.stage_path(r),'/World/Part')[0]['points']
    assert np.allclose(before.mean(0),[.01,-.03,.02])
    a=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part','label':'Part'}])
    after=meshes(p.stage_path(a))[0]['points']
    assert np.allclose(before,after)
    stl=export_stl(p,a['id'],units='mm')
    assert np.allclose(stl['report']['dimensions'],[2,2,2])
    assert stl['report']['boundary_or_nonmanifold_edges']==0
    assert stl['report']['triangles']==12


def test_corruption_and_export_overwrite_rejected(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'),'blender')
    p.stage_path(r).write_bytes(b'corrupt')
    assert not p.verify(r['id'])['ok']
    with pytest.raises(CadgitError,match='integrity'):export_stl(p,r['id'])


def test_bad_mesh_and_missing_dependency_do_not_commit(tmp_path):
    p=Project.init(tmp_path/'project');src=tmp_path/'bad.usda'
    src.write_text('#usda 1.0\n( subLayers = [@./missing.usda@] )\n')
    with pytest.raises(CadgitError,match='Unresolved'):p.ingest(src)
    assert p.records()==[]
    assert list((p.root/'history/events').glob('*.json'))


def test_init_preserves_existing_git_rules(tmp_path):
    (tmp_path/'.gitignore').write_text('my-secrets/\n')
    p=Project.init(tmp_path)
    assert (tmp_path/'.gitignore').read_text().startswith('my-secrets/\n')
    assert '*.blend binary' in (tmp_path/'.gitattributes').read_text()
    before=(tmp_path/'.gitignore').read_text();Project.init(tmp_path)
    assert (tmp_path/'.gitignore').read_text()==before


def test_print_does_not_use_display_cache(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'),'manual')
    out=tmp_path/'part.stl';result=export_stl(p,r['id'],out,units='mm')
    assert out.read_bytes()==(Path(result['_directory'])/'part.stl').read_bytes()
    import pyvista as pv
    restored=pv.read(out)
    assert np.allclose(np.asarray(restored.bounds)[1::2]-np.asarray(restored.bounds)[::2],[2000]*3)
    assert result['source_id']==r['id']
    assert not result['report']['printability_certified']


def test_native_queue_orders_save_events_not_random_directory_ids(tmp_path):
    from cadgit.service import process_inbox
    from cadgit.store import atomic_json
    p=Project.init(tmp_path/'project')
    # UUID lexical order opposes actual source save order.
    for folder,sequence,offset in [('zzzz',10,(1,0,0)),('aaaa',11,(2,0,0))]:
        d=p.root/'.cadgit/inbox'/folder;d.mkdir()
        box(d/'scene.usda',offset=offset)
        atomic_json(d/'ready.json',{'file':'scene.usda','source':'blender','metadata':{'sequence':sequence}})
    assert process_inbox(p)==2
    assert process_inbox(p)==0
    records=p.records()
    assert [r['metadata']['sequence'] for r in records]==[10,11]
    assert records[1]['parent']==records[0]['id']


def test_branch_parent_is_pinned_without_moving_main(tmp_path):
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda')
    first=p.ingest(src,'rhino')
    p.branch('rhino','experiment',base=first['id'],activate=True)
    fork=p.ingest(src,'rhino')
    assert fork['branch']=='experiment'
    assert fork['parent']==first['id']
    assert not (p.root/'main/current.json').exists()


def test_recomposed_material_identity_survives_assembly_history(tmp_path):
    from cadgit.store import atomic_json
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'source.usda'))
    mid='mat_test';directory=p.root/'materials'/mid;directory.mkdir()
    from cadgit.store import inventory
    (directory/'material.blend').write_bytes(b'opaque native graph fixture')
    atomic_json(directory/'manifest.json',{'id':mid,'label':'Historical shader','entry_layer':'material.blend','files':inventory(directory)});(directory/'COMMITTED').write_text(mid)
    first=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part','material_revision':mid}])
    path=first['bindings'][0]['prim_path']
    second=assemble(p,[{'snapshot_id':first['id'],'prim_path':path}])
    assert second['bindings'][0]['material_revision']==mid
