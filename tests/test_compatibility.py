import json,shutil
from pathlib import Path
import pytest
from pxr import Sdf,UsdShade
from cadgit.models import Snapshot,Assembly,Selection
from cadgit.store import Project,CadgitError,atomic_json,inventory,read_json
from cadgit.usd import assemble,open_stage
from test_history import box

FIXTURES=Path(__file__).parent/'fixtures/format_v1'


def test_original_v1_records_open_without_rewriting_and_can_be_reused(tmp_path):
    p=Project.init(tmp_path/'project');shutil.copyfile(FIXTURES/'project.json',p.root/'cadgit.json')
    paths=[]
    for kind,location in [('snapshot','history/sources/rhino/legacy'),('assembly','assemblies/legacy'),('material','materials/legacy')]:
        record=read_json(FIXTURES/(kind+'.json'));folder=p.root/location;folder.mkdir(parents=True)
        if kind!='material':box(folder/'scene.usda')
        else:(folder/'material.blend').write_bytes(b'opaque native asset fixture')
        record['files']=inventory(folder)
        atomic_json(folder/'manifest.json',record);(folder/'COMMITTED').write_text(record['id']);paths.append(folder/'manifest.json')
    before={f:f.read_bytes() for f in [p.root/'cadgit.json',*paths]}
    p=Project(p.root)
    for kind in ['snapshots','assemblies','materials']:assert len(p.records(kind))==1
    old=p.resolve('snap_legacy_fixture');assert p.verify(old['id'])['ok']
    result=assemble(p,[{'snapshot_id':old['id'],'prim_path':'/World/Part'}])
    assert p.verify(result['id'])['ok']
    assert all(f.read_bytes()==data for f,data in before.items())
    assert Snapshot.model_validate(read_json(paths[0])).schema_minor==0
    assert Assembly.model_validate(read_json(paths[1])).schema_minor==0


def test_additive_selection_fields_survive_validation_recipe_and_manifest(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'))
    selection={'snapshot_id':r['id'],'prim_path':'/World/Part','future_annotation':{'reviewer':'me','nested':[1,{'value':2}]},'extensions':{'org.example.material':{'density':{'value':7850,'unit':'kg/m3'}}}}
    assert Selection.model_validate(selection).model_dump()['future_annotation']==selection['future_annotation']
    result=assemble(p,[selection])
    recipe=read_json(Path(result['_directory'])/'recipe.json')
    for record in [result,recipe]:
        assert record['selections'][0]['future_annotation']==selection['future_annotation']
        assert record['selections'][0]['extensions']==selection['extensions']


def test_unknown_material_and_config_fields_survive_known_updates(tmp_path):
    p=Project.init(tmp_path/'project');config=read_json(p.root/'cadgit.json')
    extension={'org.example.engineering':{'density':{'value':7850,'unit':'kg/m3'},'youngs_modulus':{'value':210e9,'unit':'Pa'}}}
    config.update(schema_minor=50,extensions=extension,future_ui={'layout':'custom'})
    atomic_json(p.root/'cadgit.json',config);p=Project(p.root)
    p.branch('rhino','study',activate=True)
    assert read_json(p.root/'cadgit.json')['extensions']==extension
    assert read_json(p.root/'cadgit.json')['future_ui']=={'layout':'custom'}
    material=read_json(FIXTURES/'material.json');material.update(schema_minor=50,extensions=extension,new_material_parameter={'unfamiliar':True})
    folder=p.root/'materials'/material['id'];folder.mkdir();atomic_json(folder/'manifest.json',material);(folder/'COMMITTED').write_text(material['id'])
    before=(folder/'manifest.json').read_bytes();loaded=p.records('materials')[0]
    assert loaded['extensions']==extension and loaded['new_material_parameter']=={'unfamiliar':True}
    assert (folder/'manifest.json').read_bytes()==before


def test_unknown_usd_geometry_and_material_properties_survive_composition(tmp_path):
    p=Project.init(tmp_path/'project');src=box(tmp_path/'part.usda');stage=open_stage(src)
    part=stage.GetPrimAtPath('/World/Part');part.CreateAttribute('example:newProperty',Sdf.ValueTypeNames.String).Set('preserved')
    mat=UsdShade.Material.Define(stage,'/World/Looks/Material');mat.GetPrim().CreateAttribute('example:density',Sdf.ValueTypeNames.Double).Set(7850)
    UsdShade.MaterialBindingAPI.Apply(part).Bind(mat);stage.GetRootLayer().Save()
    snapshot=p.ingest(src);result=assemble(p,[{'snapshot_id':snapshot['id'],'prim_path':'/World/Part'}])
    output=open_stage(p.stage_path(result));mesh=next(prim for prim in output.Traverse() if prim.GetTypeName()=='Mesh')
    assert mesh.GetAttribute('example:newProperty').Get()=='preserved'
    bound=UsdShade.MaterialBindingAPI(mesh).ComputeBoundMaterial()[0]
    assert bound.GetPrim().GetAttribute('example:density').Get()==7850


@pytest.mark.parametrize('change,message',[({'schema_version':2},'unsupported schema'),({'required_features':['org.example.semantic_geometry_merge']},'unsupported features')])
def test_incompatible_projects_are_rejected_without_modification(tmp_path,change,message):
    p=Project.init(tmp_path/'project');config=read_json(p.root/'cadgit.json');config.update(change);atomic_json(p.root/'cadgit.json',config)
    before=(p.root/'cadgit.json').read_bytes()
    with pytest.raises(CadgitError,match=message):Project(p.root)
    assert (p.root/'cadgit.json').read_bytes()==before


def test_unsupported_record_semantics_are_not_silently_composed(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'))
    file=Path(r['_directory'])/'manifest.json';record=read_json(file);record['required_features']=['org.example.changed_transform_semantics'];atomic_json(file,record)
    before=file.read_bytes()
    with pytest.raises(CadgitError,match='unsupported features'):assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part'}])
    assert file.read_bytes()==before and not p.records('assemblies')


def test_main_pointer_extensions_survive_selecting_a_new_assembly(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'));a=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part'}]);p.set_main(a['id'])
    pointer=p.root/'main/current.json';current=read_json(pointer);current['extensions']={'org.example.review':{'approved':True}};atomic_json(pointer,current)
    b=assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part'}]);p.set_main(b['id'])
    assert read_json(pointer)['extensions']==current['extensions']


def test_project_mutations_recheck_compatibility_after_external_update(tmp_path):
    p=Project.init(tmp_path/'project');file=p.root/'cadgit.json';config=read_json(file)
    config['required_features']=['org.example.branch_semantics_v2'];atomic_json(file,config);before=file.read_bytes()
    with pytest.raises(CadgitError,match='unsupported features'):p.branch('rhino','new-branch')
    assert file.read_bytes()==before


def test_unknown_required_selection_behavior_cannot_be_silently_ignored(tmp_path):
    p=Project.init(tmp_path/'project');r=p.ingest(box(tmp_path/'part.usda'))
    with pytest.raises(CadgitError,match='unsupported features'):
        assemble(p,[{'snapshot_id':r['id'],'prim_path':'/World/Part','required_features':['org.example.deformation']}])
    assert not p.records('assemblies')


@pytest.mark.parametrize('model,fixture',[(Snapshot,'snapshot.json'),(Assembly,'assembly.json')])
def test_typed_record_roundtrip_preserves_future_optional_fields(model,fixture):
    original=read_json(FIXTURES/fixture)
    original.update(schema_minor=9,extensions={'org.example.provider':{'nested':['opaque',{'value':42}]}},future_parameter={'value':1.2,'unit':'custom'})
    serialized=model.model_validate(original).model_dump()
    assert serialized['extensions']==original['extensions']
    assert serialized['future_parameter']==original['future_parameter']
    assert serialized['schema_minor']==9
