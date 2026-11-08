import datetime as dt
import json,os,signal
from pathlib import Path
import pytest
from cadgit.store import Project,CadgitError,atomic_json,atomic_write,publish_file,read_json
from cadgit.usd import assemble,export_stl,export_usd,open_stage
from test_history import box


def assembled(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'),'rhino')
    a=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part'}]);return p,r,a


def test_init_never_overwrites_an_existing_repository_asset(tmp_path):
    (tmp_path/'main').mkdir();file=tmp_path/'main/scene.usda';file.write_text('valuable existing content')
    with pytest.raises(CadgitError,match='conflict'):Project.init(tmp_path)
    assert file.read_text()=='valuable existing content' and not (tmp_path/'cadgit.json').exists()


@pytest.mark.parametrize('timestamp',['bad/nested/date','2026-11-07','2026-11-07T12:00:00',{'unexpected':'object'}])
def test_invalid_capture_timestamps_cannot_hide_snapshots_in_nested_paths(tmp_path,timestamp):
    p=Project.init(tmp_path/'project')
    with pytest.raises(CadgitError,match='captured_at'):p.ingest(box(tmp_path/'part.usda'),metadata={'captured_at':timestamp})
    assert not p.records() and not list((p.root/'.cadgit/staging').iterdir())


def test_clock_rollback_does_not_rewrite_branch_ancestry(tmp_path):
    p=Project.init(tmp_path/'project');source=box(tmp_path/'part.usda')
    versions=[p.ingest(source,'rhino',metadata={'captured_at':stamp}) for stamp in ['2026-11-10T12:00:00Z','2026-11-01T12:00:00Z','2026-11-11T12:00:00Z']]
    assert versions[2]['parent']==versions[1]['id']
    assert [r['id'] for r in p.records()]==[r['id'] for r in versions]
    assert p.resolve('rhino/main~1')['id']==versions[1]['id']
    with pytest.raises(CadgitError,match='nonnegative'):p.resolve('rhino~-1')


@pytest.mark.parametrize('entry',['../external.usda','/tmp/external.usda'])
def test_entry_layer_cannot_escape_the_verified_archive(tmp_path,entry):
    p,r,_=assembled(tmp_path);file=Path(r['_directory'])/'manifest.json';record=read_json(file);record['entry_layer']=entry;atomic_json(file,record)
    result=p.verify(r['id']);assert not result['ok'] and any('Unsafe' in x for x in result['errors'])
    with pytest.raises(CadgitError,match='Unsafe'):p.stage_path(p.resolve(r['id']))


def test_entry_layer_must_be_in_inventory_and_commit_marker_must_match(tmp_path):
    p,r,_=assembled(tmp_path);folder=Path(r['_directory']);box(folder/'extra.usda');record=read_json(folder/'manifest.json');record['entry_layer']='extra.usda';atomic_json(folder/'manifest.json',record)
    assert not p.verify(r['id'])['ok']
    (folder/'COMMITTED').write_text('different-id')
    assert any('marker' in error for error in p.verify(r['id'])['errors'])


def test_committed_capture_is_recovered_after_receipt_failure(tmp_path,monkeypatch):
    import cadgit.service as service
    p=Project.init(tmp_path/'project');inbox=p.root/'.cadgit/inbox/event_1';inbox.mkdir();box(inbox/'scene.usda')
    atomic_json(inbox/'ready.json',{'file':'scene.usda','source':'rhino','metadata':{}})
    original=service.atomic_json
    def fail_receipt(path,data):
        if Path(path).name=='receipt.json':raise OSError('simulated disk error')
        return original(path,data)
    monkeypatch.setattr(service,'atomic_json',fail_receipt)
    assert service.process_inbox(p)==0 and len(p.records())==1
    assert (inbox/'error.json').exists()
    monkeypatch.setattr(service,'atomic_json',original)
    service.process_inbox(p)
    assert len(p.records())==1 and read_json(inbox/'receipt.json')['recovered']
    assert not (inbox/'error.json').exists()


def test_event_failure_after_commit_does_not_report_capture_as_uncommitted(tmp_path,monkeypatch):
    p=Project.init(tmp_path/'project')
    def fail(*args,**kwargs):raise OSError('event disk unavailable')
    monkeypatch.setattr(p,'event',fail)
    r=p.ingest(box(tmp_path/'part.usda'),metadata={'capture_id':'stable-event'})
    assert r.get('publication_warning') and len(p.records())==1
    assert p.ingest(p.stage_path(r),metadata={'capture_id':'stable-event'})['id']==r['id']
    assert len(p.records())==1


@pytest.mark.parametrize('failure',['scene','pointer'])
def test_main_selection_failure_preserves_previous_result(tmp_path,monkeypatch,failure):
    import cadgit.store as store
    p,r,a=assembled(tmp_path);p.set_main(a['id']);b=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part'}])
    pointer=p.root/'main/current.json';scene=p.root/'main/scene.usda';before=(pointer.read_bytes(),scene.read_bytes())
    original_write=store.atomic_write;original_json=store.atomic_json
    if failure=='scene':
        def write(path,data,*args,**kwargs):
            if Path(path)==scene:raise OSError('cannot publish projection')
            return original_write(path,data,*args,**kwargs)
        monkeypatch.setattr(store,'atomic_write',write)
    else:
        def write_json(path,data,*args,**kwargs):
            if Path(path)==pointer:raise OSError('cannot publish pointer')
            return original_json(path,data,*args,**kwargs)
        monkeypatch.setattr(store,'atomic_json',write_json)
    with pytest.raises(OSError):p.set_main(b['id'])
    assert (pointer.read_bytes(),scene.read_bytes())==before


def test_reopening_repairs_interrupted_main_projection(tmp_path):
    p,r,a=assembled(tmp_path);p.set_main(a['id']);b=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part'}])
    expected=(p.root/'main/scene.usda').read_bytes();atomic_write(p.root/'main/scene.usda',p.main_scene_bytes(b))
    p=Project(p.root)
    assert p.resolve('main')['id']==a['id'] and (p.root/'main/scene.usda').read_bytes()==expected


def test_existing_stl_output_is_rejected_before_creating_artifacts(tmp_path):
    p,r,a=assembled(tmp_path);out=tmp_path/'part.stl';out.write_bytes(b'existing')
    with pytest.raises(CadgitError,match='already exists'):export_stl(p,a['id'],out)
    assert out.read_bytes()==b'existing' and not list((p.root/'artifacts/prints').iterdir())


def test_publication_race_never_overwrites_competing_file(tmp_path,monkeypatch):
    import cadgit.store as store
    src=tmp_path/'source';src.write_bytes(b'new-data');out=tmp_path/'output'
    def competitor(source,destination):
        Path(destination).write_bytes(b'competitor');raise FileExistsError('race')
    monkeypatch.setattr(store.os,'link',competitor)
    with pytest.raises(CadgitError,match='already exists'):publish_file(src,out)
    assert out.read_bytes()==b'competitor' and not list(tmp_path.glob('.*.tmp'))


def test_failed_copy_leaves_no_partial_output(tmp_path,monkeypatch):
    import cadgit.store as store
    src=tmp_path/'source';src.write_bytes(b'new-data');out=tmp_path/'output'
    def fail(source,destination):destination.write(b'partial');raise OSError('copy interrupted')
    monkeypatch.setattr(store.shutil,'copyfileobj',fail)
    with pytest.raises(OSError):publish_file(src,out)
    assert not out.exists() and not list(tmp_path.glob('.*.tmp'))


def test_usd_export_uses_integrity_checks_and_complete_publication(tmp_path):
    p,r,a=assembled(tmp_path);out=tmp_path/'export.usdz';export_usd(p,a['id'],out);assert open_stage(out)
    with pytest.raises(CadgitError,match='already exists'):export_usd(p,a['id'],out)
    p.stage_path(a).write_bytes(b'corrupt')
    with pytest.raises(CadgitError,match='integrity'):export_usd(p,a['id'],tmp_path/'bad.usdz')
    assert not (tmp_path/'bad.usdz').exists()


def test_native_handoff_publication_race_does_not_leave_false_lineage(tmp_path,monkeypatch):
    import cadgit.handoff as handoff
    p,r,a=assembled(tmp_path);out=tmp_path/'working.3dm'
    def competitor(source,destination):Path(destination).write_bytes(b'competing-native-file');raise CadgitError('output race')
    monkeypatch.setattr(handoff,'publish_file',competitor)
    with pytest.raises(CadgitError,match='race'):handoff.create_native(p,a['id'],{'kind':'rhino'},out,False)
    assert out.read_bytes()==b'competing-native-file' and not Path(str(out)+'.cadgit.json').exists()


def test_busy_live_service_remains_stoppable_and_foreign_pid_is_not_signalled(tmp_path,monkeypatch):
    import cadgit.service as service
    p=Project.init(tmp_path/'project');atomic_json(p.root/'.cadgit/service.json',{'pid':12345,'heartbeat':'2000-01-01T00:00:00Z'})
    calls=[];monkeypatch.setattr(service.os,'kill',lambda pid,sig:calls.append((pid,sig)))
    monkeypatch.setattr(service,'_process_matches',lambda *args:True);monkeypatch.setattr(service,'_lock_held',lambda *args:True)
    assert service.status(p)['running'] and service.status(p)['busy'];service.stop(p)
    assert (12345,signal.SIGTERM) in calls
    calls.clear();monkeypatch.setattr(service,'_process_matches',lambda *args:False);service.stop(p)
    assert all(sig==0 for _,sig in calls)


def test_bad_record_is_isolated_for_reading_but_cannot_poison_new_ancestry(tmp_path):
    p,r,a=assembled(tmp_path);bad=p.root/'history/sources/rhino/corrupt';bad.mkdir();(bad/'manifest.json').write_text('{bad JSON');(bad/'COMMITTED').write_text('corrupt')
    assert [record['id'] for record in p.records(strict=False)]==[r['id']]
    assert p.record_issues['snapshots'] and p.resolve(r['id'])['id']==r['id']
    assert p.verify(r['id'])['ok']
    with pytest.raises(CadgitError,match='needs attention'):p.ingest(p.stage_path(r),'rhino')
    assert (bad/'manifest.json').read_text()=='{bad JSON'


def test_uncommitted_malformed_staging_record_is_not_read_as_history(tmp_path):
    p=Project.init(tmp_path/'project');folder=p.root/'history/sources/rhino/incomplete';folder.mkdir(parents=True);(folder/'manifest.json').write_text('{invalid')
    assert p.records()==[] and not p.record_issues['snapshots']


def test_material_payload_corruption_invalidates_dependent_assembly(tmp_path):
    from cadgit.store import inventory
    p,r,_=assembled(tmp_path);folder=p.root/'materials/mat_fixture';folder.mkdir();blob=folder/'material.blend';blob.write_bytes(b'original shader')
    atomic_json(folder/'manifest.json',{'schema_version':1,'id':'mat_fixture','label':'Fixture','entry_layer':'material.blend','files':inventory(folder)});(folder/'COMMITTED').write_text('mat_fixture')
    a=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part','material_revision':'mat_fixture'}]);assert p.verify(a['id'])['ok']
    blob.write_bytes(b'changed shader');assert not p.verify(a['id'])['ok']
    with pytest.raises(CadgitError,match='integrity'):export_usd(p,a['id'],tmp_path/'broken.usdz')


@pytest.mark.parametrize('allow_issues',[False,True])
def test_stl_rejects_meshes_with_no_exportable_faces(tmp_path,allow_issues):
    from pxr import UsdGeom
    p=Project.init(tmp_path/'project');source=box(tmp_path/'holes.usda')
    stage=open_stage(source)
    UsdGeom.Mesh(stage.GetPrimAtPath('/World/Part')).GetHoleIndicesAttr().Set([0,1,2,3,4,5])
    stage.GetRootLayer().Save();del stage
    snapshot=p.ingest(source);output=tmp_path/'empty.stl'
    with pytest.raises(CadgitError,match='no exportable mesh faces'):
        export_stl(p,snapshot['id'],output,allow_issues=allow_issues)
    assert not output.exists() and not p.records('artifacts/prints')
