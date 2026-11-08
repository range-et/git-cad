"""Failure and rendering regressions from the second three-agent review."""
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from pxr import Sdf,UsdShade
from cadgit.store import Project,CadgitError
from cadgit.library import Library
from cadgit.usd import meshes,open_stage
from cadgit.texture_preview import image_pixels,render_maps
from test_texture_preview import textured_plane


@pytest.mark.parametrize('conflict',['source-file','source-broken-link','ignore-directory','attributes-binary','rules-link'])
def test_init_preflights_user_paths_before_publication(tmp_path,conflict):
    root=tmp_path/'project';root.mkdir()
    if conflict=='source-file':(root/'source').write_bytes(b'native original')
    elif conflict=='source-broken-link':(root/'source').symlink_to(root/'missing')
    elif conflict=='ignore-directory':(root/'.gitignore').mkdir()
    elif conflict=='attributes-binary':(root/'.gitattributes').write_bytes(b'\xff\xfe')
    else:
        target=tmp_path/'shared-ignore';target.write_bytes(b'shared original');(root/'.gitignore').symlink_to(target)
    before={p.name:(p.is_symlink(),p.read_bytes() if p.is_file() else None) for p in root.iterdir()}
    with pytest.raises(CadgitError):Project.init(root)
    assert not (root/'cadgit.json').exists() and not (root/'history').exists()
    assert {p.name:(p.is_symlink(),p.read_bytes() if p.is_file() else None) for p in root.iterdir()}==before


@pytest.mark.parametrize('failure',['rules','config','config-fsync'])
def test_failed_init_restores_git_rules_and_existing_native_files(tmp_path,monkeypatch,failure):
    import cadgit.store as store
    root=tmp_path/'project';(root/'source').mkdir(parents=True);native=root/'source/model.blend';native.write_bytes(b'original native file')
    ignore=root/'.gitignore';attributes=root/'.gitattributes';ignore.write_bytes(b'# custom\r\nkeep-this\r\n');attributes.write_bytes(b'*.custom binary\n')
    before={ignore:ignore.read_bytes(),attributes:attributes.read_bytes()};original_write=store.atomic_write;original_json=store.atomic_json
    def write(path,data,*args,**kwargs):
        if failure=='rules' and Path(path)==attributes:raise OSError('rules publication failed')
        return original_write(path,data,*args,**kwargs)
    def write_json(path,data,*args,**kwargs):
        if Path(path)==root/'cadgit.json':
            if failure=='config-fsync':original_json(path,data,*args,**kwargs)
            if failure in {'config','config-fsync'}:raise OSError('config publication failed')
        return original_json(path,data,*args,**kwargs)
    monkeypatch.setattr(store,'atomic_write',write);monkeypatch.setattr(store,'atomic_json',write_json)
    with pytest.raises(OSError):Project.init(root)
    assert native.read_bytes()==b'original native file'
    assert all(path.read_bytes()==data for path,data in before.items())
    assert not (root/'cadgit.json').exists() and not (root/'history').exists()
    assert {p.name for p in root.iterdir()}=={'source','.gitignore','.gitattributes'}


def test_init_preserves_exact_original_git_rule_bytes(tmp_path):
    root=tmp_path/'project';root.mkdir();original=b'# custom\r\nkeep-this\r\n';(root/'.gitignore').write_bytes(original)
    project=Project.init(root)
    assert (root/'.gitignore').read_bytes().startswith(original+b'\n# CAD-GIT')
    assert (root/'source').is_dir() and project.records()==[]
    events=list((root/'history/events').glob('*.json'));assert len(events)==1 and 'project_initialized' in events[0].read_text()


def test_wrong_texture_file_type_falls_back_without_losing_geometry(tmp_path):
    path,image,_=textured_plane(tmp_path);stage=open_stage(path);texture=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Texture'))
    texture.GetPrim().RemoveProperty('inputs:file');texture.CreateInput('file',Sdf.ValueTypeNames.String).Set(str(image));stage.GetRootLayer().Save()
    part=meshes(path,include_textures=True)[0]
    assert not part['texture_maps'] and part['points'].shape==(4,3)
    assert any('image file input must be a USD asset path' in warning for warning in part['warnings'])


@pytest.mark.parametrize('size,expected',[((8192,1),(1,2048,4)),((1,8192),(2048,1,4))])
def test_skinny_images_keep_a_nonzero_preview_dimension(tmp_path,size,expected):
    image=tmp_path/'skinny.png';Image.new('RGB',size,'red').save(image)
    pixels,_=image_pixels(str(image),{})
    assert pixels.shape==expected and pixels[0,0,0]==255


def map_fixture(pixels):
    return {'pixels':np.asarray(pixels,dtype=np.uint8),'uv':np.array([[0.,0.],[1.,1.]]),'wrap':'repeat','channel':'r','srgb':False,'scale':(1,1,1,1),'bias':(0,0,0,0)}


def test_opacity_packing_preserves_finer_mask_than_base_color():
    base=map_fixture([[[255,255,255,255]]]);base['channel']='rgb'
    mask=map_fixture([[[0,0,0,255],[255,255,255,255]],[[255,255,255,255],[0,0,0,255]]])
    part={'color':(.5,.5,.5),'warnings':[],'texture_maps':{'base_color':base,'opacity':mask}}
    result=render_maps(part)
    assert result['base_color'].shape==(2,2,4)
    np.testing.assert_array_equal(result['base_color'][:,:,3],[[0,255],[255,0]])


def test_orm_packing_preserves_finer_metallic_map():
    roughness=map_fixture([[[128,128,128,255]]])
    metallic=map_fixture([[[0,0,0,255],[255,255,255,255]],[[255,255,255,255],[0,0,0,255]]])
    part={'color':(.5,.5,.5),'warnings':[],'texture_maps':{'roughness':roughness,'metallic':metallic}}
    result=render_maps(part)
    assert result['orm'].shape==(2,2,3)
    np.testing.assert_array_equal(result['orm'][:,:,2],[[0,255],[255,0]])
    assert (result['orm'][:,:,1]==128).all()


def test_verification_streams_payloads_and_reports_read_failure(tmp_path,monkeypatch):
    import cadgit.store as store
    project=Project.init(tmp_path/'project');library=Library(project)
    source=tmp_path/'large-shader.blend';source.write_bytes(b'shader bytes'*200000)
    revision=library.import_asset(source);payload=project.stage_path(revision)
    original=Path.read_bytes
    def forbid_buffering(path):
        if path==payload:raise AssertionError('Verification buffered entire native payload')
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',forbid_buffering)
    assert project.verify(revision)['ok']
    original_digest=store.file_digest
    def fail_read(path):
        if Path(path)==payload:raise PermissionError('payload unreadable')
        return original_digest(path)
    monkeypatch.setattr(store,'file_digest',fail_read)
    result=project.verify(revision)
    assert not result['ok'] and any('Cannot read archived payload' in error for error in result['errors'])
