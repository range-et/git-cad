import bpy, json, uuid, pathlib, traceback
from bpy.app.handlers import persistent
_cadgit_root = pathlib.Path(PROJECT)

def cadgit_capture(trigger='user_save'):
    event_id=uuid.uuid4().hex
    directory=_cadgit_root/'.cadgit'/'inbox'/event_id
    directory.mkdir(parents=True,exist_ok=True)
    import datetime, os
    captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
    seq_file=_cadgit_root/'.cadgit'/'sequence_blender.json'
    sequence=json.loads(seq_file.read_text()).get('sequence',0)+1 if seq_file.exists() else 1
    seq_tmp=seq_file.with_suffix('.tmp')
    seq_tmp.write_text(json.dumps({'sequence':sequence}));os.replace(seq_tmp,seq_file)
    try:
        # Runs synchronously on Blender's main thread at the save-post boundary.
        result=bpy.ops.wm.usd_export(filepath=str(directory/'scene.usda'),export_materials=True,generate_materialx_network=True)
        if 'FINISHED' not in result: raise RuntimeError('USD export did not finish')
        material_map={}; warnings=[]
        materials={m for o in bpy.context.scene.objects if o.type=='MESH' for m in o.data.materials if m}
        for index,mat in enumerate(sorted(materials,key=lambda m:m.name)):
            filename=f'material_{index}.blend'
            try:
                bpy.data.libraries.write(str(directory/filename),{mat},fake_user=True,path_remap='ABSOLUTE')
                images={}
                def collect(tree,visited):
                    if tree in visited: return
                    visited.add(tree)
                    for node in tree.nodes:
                        image=getattr(node,'image',None)
                        if image:
                            original=pathlib.Path(bpy.path.abspath(image.filepath))
                            if original.is_file(): images[image.name]=str(original)
                            elif not image.packed_file: warnings.append('Unavailable image: '+image.name)
                        child=getattr(node,'node_tree',None)
                        if child: collect(child,visited)
                if mat.node_tree: collect(mat.node_tree,set())
                material_map[filename]={'name':mat.name,'images':images}
            except Exception as exc: warnings.append('Native material capture failed: '+mat.name+': '+str(exc))
        (directory/'materials.json').write_text(json.dumps(material_map))
        lineage_path=pathlib.Path(bpy.data.filepath+'.cadgit.json')
        lineage=json.loads(lineage_path.read_text()) if lineage_path.is_file() else {}
        metadata={'imported_from':lineage.get('source_id'),'handoff_id':lineage.get('id'),'sequence':sequence,'captured_at':captured_at,'trigger':trigger,'native_capture':True,'native_path':bpy.data.filepath,'native_state_saved':trigger=='user_save','app_version':bpy.app.version_string,'warnings':warnings}
        (directory/'ready.tmp').write_text(json.dumps({'source':'blender','branch':json.loads((_cadgit_root/'cadgit.json').read_text()).get('active_branches',{}).get('blender','main'),'file':'scene.usda','label':pathlib.Path(bpy.data.filepath).stem or 'Blender snapshot','metadata':metadata}))
        os.replace(directory/'ready.tmp',directory/'ready.json')
        print('CAD-GIT captured',event_id)
    except Exception as exc:
        (directory/'failed.json').write_text(json.dumps({'source':'blender','error':str(exc),'traceback':traceback.format_exc()}))
        print('CAD-GIT export failed:',exc)

@persistent
def cadgit_save_post(_unused): cadgit_capture('user_save')
cadgit_save_post._cadgit_project=PROJECT
previous_projects=sorted({h._cadgit_project for h in bpy.app.handlers.save_post if hasattr(h,'_cadgit_project') and h._cadgit_project!=PROJECT})
bpy.app.handlers.save_post[:]=[h for h in bpy.app.handlers.save_post if not hasattr(h,'_cadgit_project')]
if previous_projects:print('CAD-GIT switched Blender capture from '+', '.join(previous_projects)+' to '+PROJECT)
bpy.app.handlers.save_post.append(cadgit_save_post)
print('CAD-GIT save hook attached to Blender; project:',PROJECT)
