"""Texture fidelity across USDZ packaging, UV seams and library draft overrides."""
import numpy as np
import pytest
from PIL import Image
from pxr import Gf,Sdf,Usd,UsdGeom,UsdShade
from cadgit.store import Project
from cadgit.library import Library
from cadgit.usd import meshes,assemble,open_stage
from cadgit.texture_preview import render_maps


def textured_plane(tmp_path,uv=True):
    image=tmp_path/'quadrants.png'
    pixels=np.zeros((32,32,3),dtype=np.uint8)
    pixels[:16,:16]=[255,0,0];pixels[:16,16:]=[0,255,0]
    pixels[16:,:16]=[0,0,255];pixels[16:,16:]=[255,255,0]
    Image.fromarray(pixels).save(image)
    path=tmp_path/'textured.usda';stage=Usd.Stage.CreateNew(str(path))
    root=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(root.GetPrim())
    UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1)
    mesh=UsdGeom.Mesh.Define(stage,'/World/Plane')
    mesh.GetPointsAttr().Set([(-1,-1,0),(1,-1,0),(1,1,0),(-1,1,0)])
    mesh.GetFaceVertexCountsAttr().Set([3,3]);mesh.GetFaceVertexIndicesAttr().Set([0,1,2,0,2,3]);mesh.GetSubdivisionSchemeAttr().Set('none')
    if uv:
        primvar=UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,'faceVarying')
        primvar.Set([(0,0),(1,0),(1,1),(0,1)]);primvar.SetIndices([0,1,2,0,2,3])
    material=UsdShade.Material.Define(stage,'/World/Looks/Finish')
    shader=UsdShade.Shader.Define(stage,'/World/Looks/Finish/Surface');shader.CreateIdAttr('UsdPreviewSurface')
    shader.CreateInput('diffuseColor',Sdf.ValueTypeNames.Color3f).Set(Gf.Vec3f(.15,.15,.15))
    shader.CreateInput('roughness',Sdf.ValueTypeNames.Float).Set(.7)
    texture=UsdShade.Shader.Define(stage,'/World/Looks/Finish/Texture');texture.CreateIdAttr('UsdUVTexture')
    texture.CreateInput('file',Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(str(image)))
    texture.CreateInput('sourceColorSpace',Sdf.ValueTypeNames.Token).Set('sRGB')
    texture.CreateOutput('rgb',Sdf.ValueTypeNames.Float3);texture.CreateOutput('r',Sdf.ValueTypeNames.Float)
    reader=UsdShade.Shader.Define(stage,'/World/Looks/Finish/UV');reader.CreateIdAttr('UsdPrimvarReader_float2')
    reader.CreateInput('varname',Sdf.ValueTypeNames.Token).Set('st');reader.CreateOutput('result',Sdf.ValueTypeNames.Float2)
    texture.CreateInput('st',Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(),'result')
    shader.GetInput('diffuseColor').ConnectToSource(texture.ConnectableAPI(),'rgb')
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(),'surface');UsdShade.MaterialBindingAPI.Apply(mesh.GetPrim()).Bind(material)
    stage.GetRootLayer().Save()
    return path,image,pixels


def test_usdz_texture_uses_packaged_image_and_indexed_corner_uvs(tmp_path):
    path,image,pixels=textured_plane(tmp_path);project=Project.init(tmp_path/'project');snapshot=project.ingest(path)
    image.unlink();path.unlink()
    part=meshes(project.stage_path(snapshot),include_textures=True)[0]
    np.testing.assert_array_equal(part['texture_maps']['base_color']['pixels'][:,:,:3],pixels)
    np.testing.assert_allclose(part['texture_maps']['base_color']['uv'],[(0,0),(1,0),(1,1),(0,0),(1,1),(0,1)])
    packed=render_maps(part)
    np.testing.assert_array_equal(packed['base_color'][:,:,:3],pixels)
    assert not part['warnings']
    assert not meshes(project.stage_path(snapshot))[0]['texture_maps']


def test_corner_uvs_follow_holes_and_reversed_winding(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path);mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Plane'))
    mesh.GetHoleIndicesAttr().Set([0]);mesh.GetOrientationAttr().Set('leftHanded');stage.GetRootLayer().Save()
    part=meshes(path,include_textures=True)[0]
    np.testing.assert_array_equal(part['faces'],[3,3,2,0])
    np.testing.assert_allclose(part['texture_maps']['base_color']['uv'],[(0,1),(1,1),(0,0)])


def test_missing_uvs_get_explicit_preview_only_box_mapping(tmp_path):
    path,_,_=textured_plane(tmp_path,uv=False);original=path.read_bytes()
    part=meshes(path,include_textures=True)[0]
    assert part['texture_maps']['base_color']['uv'].shape==(6,2)
    assert any('box mapping' in warning for warning in part['warnings'])
    assert path.read_bytes()==original


def test_bad_texture_or_uv_is_visible_without_losing_geometry(tmp_path):
    path,image,_=textured_plane(tmp_path);image.write_bytes(b'not an image')
    part=meshes(path,include_textures=True)[0]
    assert not part['texture_maps'] and part['points'].shape==(4,3)
    assert any('base_color texture not displayed' in warning for warning in part['warnings'])


def test_library_texture_preview_matches_saved_assembly(tmp_path):
    path,image,_=textured_plane(tmp_path);project=Project.init(tmp_path/'project');snapshot=project.ingest(path);library=Library(project)
    revision=library.import_asset(image);material=library.create_material('Textured',{'appearance':{'maps':{'base_color':{'revision_id':revision['id'],'uv_set':'st'}}}})
    draft=meshes(project.stage_path(snapshot),include_textures=True,material_override=(material,library))[0]
    saved=assemble(project,[{'snapshot_id':snapshot['id'],'prim_path':'/World/Plane','library_material_revision':material['id']}])
    result=meshes(project.stage_path(saved),include_textures=True)[0]
    np.testing.assert_array_equal(render_maps(draft)['base_color'],render_maps(result)['base_color'])
    np.testing.assert_allclose(render_maps(draft)['uv'],render_maps(result)['uv'])


def test_scalar_channels_pack_linear_orm_and_opacity(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path)
    shader=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Surface'));texture=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Texture'))
    shader.CreateInput('metallic',Sdf.ValueTypeNames.Float).ConnectToSource(texture.ConnectableAPI(),'r')
    shader.CreateInput('opacity',Sdf.ValueTypeNames.Float).ConnectToSource(texture.ConnectableAPI(),'r');stage.GetRootLayer().Save()
    part=meshes(path,include_textures=True)[0];packed=render_maps(part)
    assert packed['orm'][0,0,2]==255 and packed['orm'][0,-1,2]==0
    assert packed['orm'][0,0,1]==round(.7*255)
    assert packed['base_color'][0,0,3]==255 and packed['base_color'][0,-1,3]==0


def test_custom_vertex_uv_and_transform2d(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path);mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Plane'))
    uv=UsdGeom.PrimvarsAPI(mesh).CreatePrimvar('custom_uv',Sdf.ValueTypeNames.TexCoord2fArray,'vertex');uv.Set([(0,0),(1,0),(1,1),(0,1)])
    reader=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/UV'));reader.GetInput('varname').Set('custom_uv')
    transform=UsdShade.Shader.Define(stage,'/World/Looks/Finish/Transform');transform.CreateIdAttr('UsdTransform2d')
    transform.CreateInput('in',Sdf.ValueTypeNames.Float2).ConnectToSource(reader.ConnectableAPI(),'result')
    transform.CreateInput('scale',Sdf.ValueTypeNames.Float2).Set((2,3));transform.CreateInput('rotation',Sdf.ValueTypeNames.Float).Set(90);transform.CreateInput('translation',Sdf.ValueTypeNames.Float2).Set((.1,.2));transform.CreateOutput('result',Sdf.ValueTypeNames.Float2)
    texture=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Texture'));texture.GetInput('st').ConnectToSource(transform.ConnectableAPI(),'result');stage.GetRootLayer().Save()
    actual=meshes(path,include_textures=True)[0]['texture_maps']['base_color']['uv']
    np.testing.assert_allclose(actual,[(.1,.2),(.1,2.2),(-2.9,2.2),(.1,.2),(-2.9,2.2),(-2.9,.2)],atol=1e-6)


def test_invalid_uvs_and_mismatched_wrap_modes_are_reported(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path);mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Plane'))
    uv=UsdGeom.PrimvarsAPI(mesh).GetPrimvar('st');uv.SetIndices([0,1])
    stage.GetRootLayer().Save();part=meshes(path,include_textures=True)[0]
    assert not part['texture_maps'] and any('UV corner count' in w for w in part['warnings'])
    uv.SetIndices([0,1,2,0,2,3]);texture=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Texture'))
    texture.CreateInput('wrapS',Sdf.ValueTypeNames.Token).Set('repeat');texture.CreateInput('wrapT',Sdf.ValueTypeNames.Token).Set('clamp');stage.GetRootLayer().Save()
    part=meshes(path,include_textures=True)[0]
    assert not part['texture_maps'] and any('different S/T wrap' in w for w in part['warnings'])


def test_large_images_are_downsampled_for_preview(tmp_path):
    path,image,_=textured_plane(tmp_path);Image.new('RGB',(4096,64),'red').save(image)
    texture=meshes(path,include_textures=True)[0]['texture_maps']['base_color']
    assert texture['pixels'].shape==(32,2048,4)
    assert Image.open(image).size==(4096,64)


def test_color_space_and_wrapping_defaults(tmp_path):
    from cadgit.texture_preview import linear_pixels
    path,image,_=textured_plane(tmp_path);Image.new('RGB',(8,8),(128,128,128)).save(image)
    stage=open_stage(path);texture=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Texture'));texture.GetInput('sourceColorSpace').Set('auto');stage.GetRootLayer().Save()
    texture=meshes(path,include_textures=True)[0]['texture_maps']['base_color']
    assert texture['srgb'] and texture['wrap']=='black'
    assert linear_pixels(texture)[0,0,0]==pytest.approx(.21586,abs=1e-4)
    Image.new('L',(8,8),128).save(image)
    texture=meshes(path,include_textures=True)[0]['texture_maps']['base_color']
    assert not texture['srgb']
    assert linear_pixels(texture)[0,0,0]==pytest.approx(128/255,abs=1e-5)


def test_selected_mesh_retains_inherited_indexed_uvs_and_metadata(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path)
    mesh=stage.GetPrimAtPath('/World/Plane');mesh.RemoveProperty('primvars:st');mesh.RemoveProperty('primvars:st:indices')
    inherited=UsdGeom.PrimvarsAPI(stage.GetPrimAtPath('/World')).CreatePrimvar('st',Sdf.ValueTypeNames.TexCoord2fArray,'constant')
    inherited.Set([(.25,.75),(.75,.25)]);inherited.SetIndices([0]);inherited.GetAttr().SetCustomDataByKey('future_mapping_note','retain authored metadata')
    stage.GetRootLayer().Save();project=Project.init(tmp_path/'project');snapshot=project.ingest(path)
    before=meshes(project.stage_path(snapshot),'/World/Plane',include_textures=True)[0]
    saved=assemble(project,[{'snapshot_id':snapshot['id'],'prim_path':'/World/Plane'}])
    after=meshes(project.stage_path(saved),include_textures=True)[0]
    np.testing.assert_allclose(after['texture_maps']['base_color']['uv'],before['texture_maps']['base_color']['uv'])
    assert not any('No UV coordinates' in warning for warning in after['warnings'])
    output=open_stage(project.stage_path(saved));mesh=next(prim for prim in output.Traverse() if prim.IsA(UsdGeom.Mesh))
    restored=UsdGeom.PrimvarsAPI(mesh).GetPrimvar('st')
    assert restored.IsIndexed() and list(restored.GetIndices())==[0]
    assert restored.GetAttr().GetCustomDataByKey('future_mapping_note')=='retain authored metadata'
    assert project.verify(saved['id'])['ok']


def test_material_values_use_the_requested_geometry_sample_time(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path)
    shader=UsdShade.Shader(stage.GetPrimAtPath('/World/Looks/Finish/Surface'))
    color=shader.GetInput('diffuseColor');color.DisconnectSource();color.GetAttr().Clear()
    color.Set(Gf.Vec3f(1,0,0),0);color.Set(Gf.Vec3f(0,0,1),1)
    for name,start,end in [('roughness',.2,.8),('metallic',.1,.9),('opacity',.3,.7)]:
        input=shader.GetInput(name) or shader.CreateInput(name,Sdf.ValueTypeNames.Float)
        input.GetAttr().Clear();input.Set(start,0);input.Set(end,1)
    stage.GetRootLayer().Save()
    for time,color,roughness,metallic,opacity in [(0,(1,0,0),.2,.1,.3),(1,(0,0,1),.8,.9,.7)]:
        part=meshes(path,time=time,include_textures=True)[0]
        assert part['color']==color
        assert part['roughness']==pytest.approx(roughness)
        assert part['metallic']==pytest.approx(metallic)
        assert part['opacity']==pytest.approx(opacity)
    # Display color follows the same time when there is no bound material.
    mesh=UsdGeom.Mesh(stage.GetPrimAtPath('/World/Plane'));UsdShade.MaterialBindingAPI(mesh).UnbindAllBindings()
    mesh.GetDisplayColorAttr().Set([Gf.Vec3f(0,1,0)],0);mesh.GetDisplayColorAttr().Set([Gf.Vec3f(1,1,0)],1)
    stage.GetRootLayer().Save()
    assert meshes(path,time=0)[0]['color']==(0,1,0)
    assert meshes(path,time=1)[0]['color']==(1,1,0)


def test_inherited_display_color_matches_source_and_selected_assembly(tmp_path):
    path,_,_=textured_plane(tmp_path);stage=open_stage(path)
    mesh=stage.GetPrimAtPath('/World/Plane');UsdShade.MaterialBindingAPI(mesh).UnbindAllBindings()
    color=UsdGeom.PrimvarsAPI(stage.GetPrimAtPath('/World')).CreatePrimvar('displayColor',Sdf.ValueTypeNames.Color3fArray,'constant')
    color.Set([Gf.Vec3f(1,0,0),Gf.Vec3f(0,1,0)]);color.SetIndices([1])
    stage.GetRootLayer().Save();project=Project.init(tmp_path/'project');snapshot=project.ingest(path)
    saved=assemble(project,[{'snapshot_id':snapshot['id'],'prim_path':'/World/Plane'}])
    source_part=meshes(project.stage_path(snapshot),'/World/Plane')[0]
    saved_part=meshes(project.stage_path(saved))[0]
    assert source_part['color']==saved_part['color']==(0,1,0)
