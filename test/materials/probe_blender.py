# Research probe, not CAD-GIT implementation.
# Run only in a disposable process:
# Blender --background --factory-startup --python probe_blender.py
# Outputs go to a unique temporary directory; the live Blender session is untouched.
import bpy,json,pathlib,traceback,tempfile
from pxr import Usd,UsdShade
root=pathlib.Path(tempfile.mkdtemp(prefix='cadgit-material-research-'))
report={'output_directory':str(root),'blender_version':bpy.app.version_string,'test':'Noise Texture -> Color Ramp -> Principled BSDF, USD vs native material library','results':{}}
def signature(mat):
 nodes=mat.node_tree.nodes
 return {'nodes':sorted((n.name,n.bl_idname) for n in nodes),'links':sorted((l.from_node.name,l.from_socket.identifier,l.to_node.name,l.to_socket.identifier) for l in mat.node_tree.links),'roughness':next(n for n in nodes if n.type=='BSDF_PRINCIPLED').inputs['Roughness'].default_value,'noise_scale':next((n.inputs['Scale'].default_value for n in nodes if n.type=='TEX_NOISE'),None),'ramp_positions':[e.position for n in nodes if n.type=='VALTORGB' for e in n.color_ramp.elements]}
try:
 bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
 bpy.ops.mesh.primitive_cube_add(size=1)
 obj=bpy.context.object
 mat=bpy.data.materials.new('HistoricalProceduralMaterial');mat.use_nodes=True
 nodes=mat.node_tree.nodes;nodes.clear()
 out=nodes.new('ShaderNodeOutputMaterial');bsdf=nodes.new('ShaderNodeBsdfPrincipled');noise=nodes.new('ShaderNodeTexNoise');ramp=nodes.new('ShaderNodeValToRGB')
 noise.inputs['Scale'].default_value=6.2
 bsdf.inputs['Roughness'].default_value=0.37
 ramp.color_ramp.elements[0].position=0.23;ramp.color_ramp.elements[0].color=(0.03,0.1,0.7,1)
 ramp.color_ramp.elements[1].position=0.79;ramp.color_ramp.elements[1].color=(0.7,0.08,0.03,1)
 links=mat.node_tree.links
 links.new(noise.outputs['Fac'],ramp.inputs['Fac']);links.new(ramp.outputs['Color'],bsdf.inputs['Base Color']);links.new(bsdf.outputs['BSDF'],out.inputs['Surface'])
 obj.data.materials.append(mat)
 original=signature(mat);report['original']=original
 bpy.data.libraries.write(str(root/'material.blend'),{mat},fake_user=True)
 with bpy.data.libraries.load(str(root/'material.blend'),link=False) as (src,dst):dst.materials=[mat.name]
 reloaded=dst.materials[0]
 report['results']['native_material_library']={'signature_equal':signature(reloaded)==original,'signature':signature(reloaded)}
 params={p.identifier for p in bpy.ops.wm.usd_export.get_rna_type().properties}
 kwargs={'filepath':str(root/'scene.usda'),'export_materials':True}
 if 'generate_materialx_network' in params:kwargs['generate_materialx_network']=True
 result=bpy.ops.wm.usd_export(**kwargs)
 stage=Usd.Stage.Open(str(root/'scene.usda'))
 shader_ids=[]
 for prim in stage.Traverse():
  if prim.IsA(UsdShade.Shader):shader_ids.append({'path':str(prim.GetPath()),'id':str(UsdShade.Shader(prim).GetIdAttr().Get())})
 report['results']['usd_export']={'operator_result':list(result),'shaders':shader_ids,'files':[str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()]}
 before=set(bpy.data.objects)
 imported=bpy.ops.wm.usd_import(filepath=str(root/'scene.usda'),import_materials=True,import_usd_preview=True)
 objects=[o for o in bpy.data.objects if o not in before and o.type=='MESH']
 imported_mat=objects[0].data.materials[0]
 imported_sig=signature(imported_mat)
 report['results']['usd_import']={'operator_result':list(imported),'signature_equal':imported_sig==original,'signature':imported_sig}
except Exception as e:
 report['error']=str(e);report['traceback']=traceback.format_exc()
finally:
 (root/'report.json').write_text(json.dumps(report,indent=2))
 print('CADGIT_MATERIAL_REPORT '+json.dumps(report))
