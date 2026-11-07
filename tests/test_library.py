import copy,json,shutil
from pathlib import Path
import pytest
from PIL import Image
from pxr import UsdGeom,UsdShade,Sdf
from cadgit.store import Project,CadgitError,read_json,atomic_json
from cadgit.library import Library,FEATURE
from cadgit.usd import assemble,open_stage,export_usd
from cadgit.connectors import blender_import_code
from test_history import box


def image(path,color='blue'):
    Image.new('RGB',(8,8),color).save(path);return path


def project(tmp_path):
    p=Project.init(tmp_path/'project');return p,Library(p)


def test_image_identity_revisions_and_material_refs_are_pinned(tmp_path):
    p,library=project(tmp_path);file=image(tmp_path/'texture.png');a=library.import_asset(file,'Texture');material=library.create_material('Polymer',{'physical':{'properties':{}},'appearance':{'maps':{'base_color':{'revision_id':a['id'],'color_space':'sRGB'}}}})
    original=p.stage_path(a).read_bytes();image(file,'red');b=library.import_asset(file,asset_id=a['asset_id'],expected_revision=a['id']);file.unlink()
    assert a['asset_id']==b['asset_id'] and a['id']!=b['id']
    assert p.stage_path(a).read_bytes()==original and library.verify(a['id'])['ok']
    assert library.get(material['id'])['definition']['appearance']['maps']['base_color']['revision_id']==a['id']
    assert library.summaries(kind='image')[0]['head']==b['id']
    assert any(r['id']==material['id'] for r in library.used_by(a['id']))


def test_recombination_copies_facets_and_preserves_both_donors(tmp_path):
    p,lib=project(tmp_path);a=lib.create_material('Synthetic physical fixture',{'physical':{'properties':{'density':{'value':1234,'unit':'kg/m3','status':'test fixture','source':'Synthetic, not real material data'}}},'appearance':{}})
    b=lib.create_material('Appearance',{'appearance':{'preview':{'base_color':[.2,.3,.4],'roughness':.6}},'physical':{'properties':{}}})
    c=lib.recombine('Combined',a['id'],b['id'])
    assert c['definition']['physical']==a['definition']['physical']
    assert c['definition']['appearance']==b['definition']['appearance']
    assert {(r['role'],r['revision_id']) for r in c['parents']}=={('physical_from',a['id']),('appearance_from',b['id'])}


def test_default_revision_clones_definition_and_retains_unknown_fields(tmp_path):
    p,lib=project(tmp_path);a=lib.create_material('Polymer',{'physical':{'properties':{}},'appearance':{},'future_field':{'opaque':[1,2]}})
    file=Path(a['_directory'])/'manifest.json';data=read_json(file);data['extensions']={'org.future':{'value':42}};atomic_json(file,data)
    b=lib.create_material('Polymer r2',asset_id=a['asset_id'],expected_revision=a['id'])
    assert b['definition']==a['definition'] and b['extensions']==data['extensions']
    assert lib.get(a['id'])['definition']==a['definition']


def test_stale_revision_fails_and_derivative_gets_a_new_identity(tmp_path):
    p,lib=project(tmp_path);file=image(tmp_path/'a.png');a=lib.import_asset(file);b=lib.import_asset(file,asset_id=a['asset_id'],expected_revision=a['id'])
    with pytest.raises(CadgitError,match='changed|historical'):lib.import_asset(file,asset_id=a['asset_id'],expected_revision=a['id'])
    derived=lib.import_asset(file,parents=[{'revision_id':a['id'],'role':'derived_from'}],note='External edit')
    assert derived['asset_id']!=a['asset_id'] and derived['parents'][0]['revision_id']==a['id']
    assert lib.history(a['asset_id'])[-1]['id']==b['id']


def test_hashed_definition_and_manifest_must_agree(tmp_path):
    p,lib=project(tmp_path);a=lib.create_material('Material');path=Path(a['_directory'])/'manifest.json';data=read_json(path);data['definition']['appearance']={'preview':{'metallic':.9}};atomic_json(path,data)
    assert not lib.verify(a['id'])['ok']
    with pytest.raises(CadgitError,match='integrity'):lib.export(a['id'],tmp_path/'out.json')


@pytest.mark.parametrize('target',['library','revisions','marker'])
def test_library_storage_cannot_escape_through_symlinks(tmp_path,target):
    p,lib=project(tmp_path);file=image(tmp_path/'a.png')
    if target=='library':outside=tmp_path/'outside';outside.mkdir();lib.root.symlink_to(outside,target_is_directory=True)
    else:
        lib.import_asset(file)
        source=lib.root/('revisions' if target=='revisions' else 'library.json');outside=tmp_path/'outside';source.rename(outside);source.symlink_to(outside,target_is_directory=target=='revisions')
    before=list(outside.rglob('*')) if outside.is_dir() else outside.read_bytes()
    with pytest.raises(CadgitError,match='symlink'):lib.import_asset(file)
    assert (list(outside.rglob('*')) if outside.is_dir() else outside.read_bytes())==before


@pytest.mark.parametrize('definition',[{'physical':None},{'appearance':None},{'appearance':{'maps':[]}},{'physical':{'properties':{'density':{'value':'banana','unit':'kg/m3'}}}},{'physical':{'properties':{'density':{'value':-1,'unit':'kg/m3'}}}},{'physical':{'properties':{'density':{'value':float('nan'),'unit':'kg/m3'}}}}])
def test_invalid_material_data_has_an_actionable_error(tmp_path,definition):
    p,lib=project(tmp_path)
    with pytest.raises(CadgitError):lib.create_material('Invalid',definition)
    assert not lib.records()


def test_invalid_relationship_is_not_committed(tmp_path):
    p,lib=project(tmp_path);file=image(tmp_path/'a.png');a=lib.import_asset(file)
    with pytest.raises(CadgitError,match='relationship'):lib.import_asset(file,parents=[{'revision_id':a['id']}])
    assert len(lib.records())==1


def test_current_import_path_and_existing_provenance_are_preserved(tmp_path):
    p,lib=project(tmp_path);a=lib.import_asset(image(tmp_path/'original.png'),provenance={'provider':'Local fixture','source_url':'https://example.org/source','license':{'name':'fixture license'}})
    b=lib.import_asset(image(tmp_path/'edited.png','red'),asset_id=a['asset_id'],expected_revision=a['id'])
    assert b['provenance']['import_path'].endswith('edited.png')
    assert b['provenance']['source_url']==a['provenance']['source_url']
    assert b['provenance']['license']==a['provenance']['license']


def test_logical_assignments_survive_capture_and_dependency_verification(tmp_path):
    p,lib=project(tmp_path);texture=lib.import_asset(image(tmp_path/'blue.png'));material=lib.create_material('Polymer',{'physical':{'properties':{}},'appearance':{'maps':{'base_color':{'revision_id':texture['id'],'color_space':'sRGB'}}}})
    source=p.ingest(box(tmp_path/'part.usda'));assembly=assemble(p,[{'snapshot_id':source['id'],'prim_path':'/World/Part','library_material_revision':material['id']}])
    assert assembly['required_features']==[FEATURE] and assembly['library_bindings'][0]['library_material_revision']==material['id']
    capture=p.ingest(p.stage_path(assembly),'rhino');assert capture['library_bindings'][0]['library_material_revision']==material['id'] and FEATURE in capture['required_features']
    assert any(record['kind']=='snapshot' for record in lib.used_by(material['id']))
    p.stage_path(texture).write_bytes(b'corrupted image')
    assert not p.verify(assembly)['ok'] and not p.verify(capture)['ok']
    with pytest.raises(CadgitError,match='integrity'):export_usd(p,capture['id'],tmp_path/'bad.usdz')


def legacy_graph(p,tmp_path,label='Original'):
    folder=p.root/'.cadgit/staging/legacy';folder.mkdir();(folder/'material.blend').write_bytes(b'opaque original graph')
    return p.commit(folder,p.root/'materials/mat_original',{'schema_version':1,'id':'mat_original','label':label,'entry_layer':'material.blend','images':{}})


def test_native_capture_mapping_handles_spaces_and_never_replaces_edited_graph(tmp_path):
    p,lib=project(tmp_path);old=legacy_graph(p,tmp_path);material=lib.create_material('PLA',{'appearance':{'native_graph':old['id']},'physical':{'properties':{}}})
    path=box(tmp_path/'capture.usda');stage=open_stage(path);part=stage.GetPrimAtPath('/World/Part');part.CreateAttribute('userProperties:cadgit:library_material_revision',Sdf.ValueTypeNames.String).Set(material['id']);mat=UsdShade.Material.Define(stage,'/World/Looks/PLA_Red');UsdShade.MaterialBindingAPI.Apply(part).Bind(mat);stage.GetRootLayer().Save()
    (tmp_path/'material_0.blend').write_bytes(b'opaque edited graph');atomic_json(tmp_path/'materials.json',{'material_0.blend':{'name':'PLA Red','images':{}}})
    capture=p.ingest(path,'blender',metadata={'native_capture':True})
    assert capture['library_bindings'][0]['appearance_source']=='captured_native'
    new=capture['metadata']['native_materials_by_prim']['/World/Part'];assert new!=old['id']
    code=blender_import_code(p,capture['id']);assert 'library_materials={}\n' in code
    assert capture['bindings'][0]['material_revision']==new


def test_native_name_collision_is_rejected_instead_of_guessing(tmp_path):
    p,lib=project(tmp_path);path=box(tmp_path/'capture.usda');stage=open_stage(path);mat=UsdShade.Material.Define(stage,'/World/Looks/PLA_Red');UsdShade.MaterialBindingAPI.Apply(stage.GetPrimAtPath('/World/Part')).Bind(mat);stage.GetRootLayer().Save()
    (tmp_path/'material_0.blend').write_bytes(b'graph one');(tmp_path/'material_1.blend').write_bytes(b'graph two');atomic_json(tmp_path/'materials.json',{'material_0.blend':{'name':'PLA Red'},'material_1.blend':{'name':'PLA_Red'}})
    with pytest.raises(CadgitError,match='unambiguously'):p.ingest(path,'blender',metadata={'native_capture':True})
    assert not p.records()


def test_textured_captured_shader_descriptor_keeps_blend_path(tmp_path):
    p,lib=project(tmp_path);folder=p.root/'.cadgit/staging/shader';folder.mkdir();(folder/'material.blend').write_bytes(b'opaque graph');(folder/'images').mkdir();image(folder/'images/texture.png')
    native=p.commit(folder,p.root/'materials/mat_textured',{'schema_version':1,'id':'mat_textured','label':'Textured','entry_layer':'material.blend','images':{'Texture':'images/texture.png'}})
    material=lib.create_material('Textured polymer',{'appearance':{'native_graph':native['id']}})
    descriptor=lib.native_shader(material['id'])
    assert descriptor['path']==str(p.stage_path(native))
    assert descriptor['images']['Texture'].endswith('images/texture.png')


def test_rhino_geometry_capture_keeps_library_graph_and_blender_clear_does_not(tmp_path):
    p,lib=project(tmp_path);native=legacy_graph(p,tmp_path);material=lib.create_material('Polymer',{'appearance':{'native_graph':native['id']}})
    source=p.ingest(box(tmp_path/'source.usda'));assembly=assemble(p,[{'snapshot_id':source['id'],'prim_path':'/World/Part','library_material_revision':material['id']}])
    rhino=p.ingest(p.stage_path(assembly),'rhino',metadata={'native_capture':True})
    assert rhino['library_bindings'][0]['appearance_source']=='library'
    assert 'library_materials={}' not in blender_import_code(p,rhino['id'])
    cleared=p.ingest(p.stage_path(assembly),'blender',metadata={'native_capture':True})
    assert cleared['library_bindings'][0]['appearance_source']=='captured_native'
    assert 'library_materials={}\n' in blender_import_code(p,cleared['id'])


def test_resolved_capture_tags_survive_export_and_reingestion(tmp_path):
    p,lib=project(tmp_path);old=legacy_graph(p,tmp_path);material=lib.create_material('Polymer',{'appearance':{'native_graph':old['id']}})
    source=box(tmp_path/'capture.usda');stage=open_stage(source);prim=stage.GetPrimAtPath('/World/Part')
    prim.CreateAttribute('userProperties:cadgit:library_material_revision',Sdf.ValueTypeNames.String).Set(material['id'])
    prim.CreateAttribute('userProperties:cadgit:material_revision',Sdf.ValueTypeNames.String).Set(old['id'])
    prim.CreateAttribute('userProperties:cadgit:library_appearance_source',Sdf.ValueTypeNames.String).Set('library')
    native=UsdShade.Material.Define(stage,'/World/Looks/Edited_Shader');UsdShade.MaterialBindingAPI.Apply(prim).Bind(native);stage.GetRootLayer().Save()
    (tmp_path/'material_0.blend').write_bytes(b'edited graph');atomic_json(tmp_path/'materials.json',{'material_0.blend':{'name':'Edited Shader'}})
    capture=p.ingest(source,'blender',metadata={'native_capture':True});new=capture['bindings'][0]['material_revision']
    # Hold the stage while inspecting its prim.
    archived_stage=open_stage(p.stage_path(capture));archived=archived_stage.GetPrimAtPath('/World/Part')
    assert archived.GetAttribute('userProperties:cadgit:material_revision').Get()==new
    replay=p.ingest(p.stage_path(capture),'manual')
    assert replay['bindings'][0]['material_revision']==new
    assert replay['library_bindings'][0]['appearance_source']=='captured_native'


def test_material_selection_is_gated_even_before_an_assembly_is_saved(monkeypatch):
    from cadgit.models import Selection
    import cadgit.compatibility as compatibility
    data=Selection(snapshot_id='snapshot',prim_path='/Part',library_material_revision='assetrev_pinned').model_dump()
    assert FEATURE in data['required_features']
    monkeypatch.setattr(compatibility,'SUPPORTED_FEATURES',frozenset())
    with pytest.raises(CadgitError,match='unsupported features'):compatibility.check_compatibility(data,'Older reader',legacy=True)
