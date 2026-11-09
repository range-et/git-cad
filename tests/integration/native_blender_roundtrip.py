"""Opt-in live Blender save/capture/restore gate, using disposable native processes."""
import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from pxr import Sdf, UsdUtils

from cadgit.handoff import create_native
from cadgit.service import process_inbox
from cadgit.store import Project, read_json
from cadgit.usd import assemble, meshes


def run(command, timeout=180):
    process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,start_new_session=True)
    try:output,_=process.communicate(timeout=timeout)
    except BaseException:
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        process.wait();raise
    if process.returncode:raise RuntimeError(output)
    return output


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--blender',type=Path,default=Path('/Applications/Blender.app/Contents/MacOS/Blender'))
    args=parser.parse_args()
    if not args.blender.is_file():raise SystemExit('Blender executable unavailable: '+str(args.blender))
    hook=Path(__file__).resolve().parents[2]/'src/cadgit/resources/blender_hook.py'
    with tempfile.TemporaryDirectory(prefix='cadgit-live-blender-') as folder:
        root=Path(folder);project=Project.init(root/'project')
        texture=root/'albedo.png';Image.new('RGB',(8,8),(160,40,210)).save(texture)
        working=root/'source.blend';capture=root/'capture.py'
        capture.write_text('''import bpy
bpy.ops.object.select_all(action='SELECT')
bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
obj=bpy.context.object
material=bpy.data.materials.new('NativeGraph')
material.use_nodes=True
texture=material.node_tree.nodes.new('ShaderNodeTexImage')
texture.image=bpy.data.images.load('''+repr(str(texture))+''')
material.node_tree.links.new(texture.outputs['Color'],material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'])
obj.data.materials.append(material)
PROJECT='''+repr(str(project.root))+'''
exec(compile(open('''+repr(str(hook))+''').read(),'''+repr(str(hook))+''','exec'),globals())
bpy.ops.wm.save_as_mainfile(filepath='''+repr(str(working))+''')
obj.location.x=3
material.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value=.75
bpy.ops.wm.save_as_mainfile(filepath='''+repr(str(working))+''')
''')
        output=run([str(args.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(capture)])
        original=working.read_bytes();texture_bytes=texture.read_bytes()
        markers=list((project.root/'.cadgit/inbox').glob('*/ready.json'))
        assert len(markers)==2,(len(markers),output)
        assert process_inbox(project)==2
        records=project.records();assert len(records)==2
        assert records[1]['parent']==records[0]['id']
        assert all(project.verify(r['id'])['ok'] for r in records)
        assert all(r['metadata']['native_state_saved'] for r in records)
        detached=root/'detached-albedo.png';texture.rename(detached)
        for record in records:
            assert not UsdUtils.ComputeAllDependencies(Sdf.AssetPath(str(project.stage_path(record))))[2]
            rendered=meshes(project.stage_path(record),include_textures=True)[0]
            assert 'base_color' in rendered['texture_maps'],rendered['warnings']
            np.testing.assert_array_equal(rendered['texture_maps']['base_color']['pixels'][0,0,:3],[160,40,210])
        detached.rename(texture)
        materials=project.records('materials');assert len(materials)==2
        for material in materials:
            assert material['images']
            assert all((Path(material['_directory'])/path).read_bytes()==texture_bytes for path in material['images'].values())
        prim=meshes(project.stage_path(records[0]))[0]['path']
        combined=assemble(project,[{'snapshot_id':records[0]['id'],'prim_path':prim}])
        destination=root/'restored.blend'
        lineage=create_native(project,combined['id'],{'kind':'blender','executable':str(args.blender)},destination,launch=False)
        assert lineage['source_id']==combined['id'] and destination.is_file()
        inspection=root/'inspect.py';result_path=root/'inspection.json'
        inspection.write_text('''import bpy,json
bpy.ops.wm.open_mainfile(filepath='''+repr(str(destination))+''')
objects=[obj for obj in bpy.context.scene.objects if obj.type=='MESH']
assert len(objects)==1
materials=[mat for obj in objects for mat in obj.data.materials if mat]
assert len(materials)==1 and materials[0].use_nodes
images=[node.image for node in materials[0].node_tree.nodes if node.type=='TEX_IMAGE' and node.image]
assert len(images)==1
result={'version':bpy.app.version_string,'image':bpy.path.abspath(images[0].filepath),'objects':len(objects),'material':materials[0].name}
open('''+repr(str(result_path))+''','w').write(json.dumps(result))
''')
        run([str(args.blender),'--background','--factory-startup','--python-exit-code','1','--python',str(inspection)])
        result=read_json(result_path)
        assert Path(result['image']).resolve().is_relative_to((project.root/'materials').resolve())
        assert Path(result['image']).read_bytes()==texture_bytes
        assert working.read_bytes()==original and texture.read_bytes()==texture_bytes
        assert project.verify(combined['id'])['ok']
        print(json.dumps({'blender':result['version'],'captures':len(records),'material_revisions':len(materials),'restored_meshes':result['objects'],'originals_immutable':True}))
    print('NATIVE_BLENDER_ROUNDTRIP_VERIFIED: isolated saves, archive images, lineage and native restoration')


if __name__=='__main__':main()
