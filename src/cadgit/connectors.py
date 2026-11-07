"""Trusted local adapters for the already-installed community listeners."""
from __future__ import annotations
import json, socket, urllib.request
from pathlib import Path
from .store import CadgitError


def blender_rpc(code, host="127.0.0.1", port=9876):
    with socket.create_connection((host, port), timeout=120) as sock:
        sock.sendall(json.dumps({"type": "execute_code", "params": {"code": code}}).encode())
        data = b""
        while len(data) < 16 * 1024 * 1024:
            chunk = sock.recv(65536)
            if not chunk: raise CadgitError("Blender disconnected before response")
            data += chunk
            try:
                r = json.loads(data)
                if r.get("status") == "error": raise CadgitError(r.get("message", str(r)))
                return r
            except json.JSONDecodeError: pass
    raise CadgitError("Blender response exceeds size limit")


def rhino_endpoint():
    listeners = Path.home() / "Library/Application Support/McNeel/Rhinoceros/ai/listeners"
    active = []
    for path in listeners.glob("*.json"):
        try:
            info = json.loads(path.read_text())
            port = info.get("port") or int(path.stem.rsplit("-",1)[-1])
            endpoint = f"http://127.0.0.1:{port}/"
            req = urllib.request.Request(endpoint, json.dumps({"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"get_context","arguments":{}}}).encode(), {"Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=2) as response:
                if "result" in json.load(response): active.append(endpoint)
        except Exception: continue
    if len(active) != 1: raise CadgitError(f"Found {len(active)} Rhino documents; specify --rhino-endpoint explicitly")
    return active[0]


def rhino_rpc(code, endpoint=None):
    endpoint = endpoint or rhino_endpoint()
    payload = {"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"run_python","arguments":{"script":code}}}
    req = urllib.request.Request(endpoint, json.dumps(payload).encode(), {"Content-Type":"application/json"})
    with urllib.request.urlopen(req, timeout=120) as response: result = json.load(response)
    if "error" in result or result.get("result",{}).get("isError"): raise CadgitError(str(result))
    return result


def script(name, project):
    return "PROJECT = " + repr(str(project.root)) + "\n" + (Path(__file__).parent / "resources" / name).read_text()


def attach(project, app, endpoint=None):
    code = script(f"{app}_hook.py", project)
    if app == "blender": return blender_rpc(code)
    if app == "rhino":
        from .store import read_json,atomic_json
        settings=project.root/'.cadgit/connections.local.json'
        config=read_json(settings) if settings.exists() else {}
        resolved=endpoint or config.get('rhino_endpoint') or rhino_endpoint()
        result=rhino_rpc(code,resolved)
        config['rhino_endpoint']=resolved;atomic_json(settings,config)
        return result
    raise CadgitError(f"Unknown adapter {app}")


def capture(project, app, endpoint=None, respect_binding=False):
    # Background timers may capture only the project explicitly bound by the
    # user. They must never reattach and steal another project's native session.
    if not respect_binding:attach(project,app,endpoint)
    root=repr(str(project.root));trigger=repr('tool_snapshot' if respect_binding else 'manual_snapshot')
    if app=='blender':
        code="import bpy\nhooks=[h for h in bpy.app.handlers.save_post if hasattr(h,'_cadgit_project')]\n"
        code+="owned=[h for h in hooks if h._cadgit_project=="+root+"]\n"
        code+="if len(owned)!=1 or any(h._cadgit_project!="+root+" for h in hooks): raise RuntimeError('CAD-GIT capture refused: Blender is unbound or belongs to another project; run begin explicitly to switch')\n"
        code+="owned[0].__globals__['cadgit_capture']("+trigger+")"
        return blender_rpc(code)
    if app!='rhino':raise CadgitError('Unknown adapter '+app)
    if endpoint is None:
        settings=project.root/'.cadgit/connections.local.json'
        endpoint=json.loads(settings.read_text()).get('rhino_endpoint') if settings.exists() else None
    code="import scriptcontext\nh=scriptcontext.sticky.get('cadgit_capture')\n"
    code+="owner=getattr(h,'_cadgit_project',None) or getattr(h,'__globals__',{}).get('PROJECT')\n"
    code+="if h is None or owner!="+root+": raise RuntimeError('CAD-GIT capture refused: Rhino is unbound or belongs to another project; run begin explicitly to switch')\n"
    code+="h("+trigger+")"
    return rhino_rpc(code,endpoint)


def detach(project, app, endpoint=None):
    if app == "blender":
        return blender_rpc("import bpy\nbpy.app.handlers.save_post[:]=[h for h in bpy.app.handlers.save_post if getattr(h,'_cadgit_project',None)!="+repr(str(project.root))+"]")
    endpoint=endpoint or (json.loads((project.root/'.cadgit/connections.local.json').read_text()).get('rhino_endpoint') if (project.root/'.cadgit/connections.local.json').exists() else None)
    root=repr(str(project.root))
    code="import Rhino,scriptcontext\nh=scriptcontext.sticky.get('cadgit_save_handler')\n"
    code+="owner=getattr(h,'_cadgit_project',None) or getattr(h,'__globals__',{}).get('PROJECT') or scriptcontext.sticky.get('cadgit_active_project')\n"
    code+="if owner=="+root+":\n"
    code+="    h=scriptcontext.sticky.pop('cadgit_save_handler',None)\n    if h: Rhino.RhinoDoc.EndSaveDocument -= h\n"
    code+="    i=scriptcontext.sticky.pop('cadgit_idle_handler',None)\n    if i: Rhino.RhinoApp.Idle -= i\n"
    code+="    scriptcontext.sticky.pop('cadgit_capture',None)\n    scriptcontext.sticky.pop('cadgit_active_project',None)\n"
    code+="    print('CAD-GIT Rhino save hook detached for this project')\n"
    code+="else: print('CAD-GIT Rhino hook unchanged: active hook belongs to another project or is not attached')"
    return rhino_rpc(code,endpoint)



def blender_import_code(project, ref):
    record = project.resolve(ref)
    if not record.get('bindings') and record.get('metadata',{}).get('native_materials'):
        from .usd import open_stage
        from pxr import UsdGeom,UsdShade
        record=dict(record);record['bindings']=[]
        source_stage=open_stage(project.stage_path(record))
        for prim in source_stage.Traverse():
            if not prim.IsA(UsdGeom.Mesh):continue
            material=UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
            revision=record['metadata']['native_materials'].get(material.GetPrim().GetName()) if material else None
            if revision:record['bindings'].append({'prim_path':str(prim.GetPath()),'material_revision':revision})
    record=dict(record);record['bindings']=list(record.get('bindings',[]));library_materials={}
    if record.get('library_bindings'):
        from .library import Library
        library=Library(project)
        captured_paths={binding['prim_path'] for binding in record['bindings']}
        for binding in record['library_bindings']:
            if binding['prim_path'] in captured_paths or binding.get('appearance_source')=='captured_native':continue
            revision=binding['library_material_revision'];descriptor=library.native_shader(revision)
            if descriptor:
                key='library_'+revision;library_materials[key]=descriptor
                record['bindings'].append({'prim_path':binding['prim_path'],'material_revision':key})
    import_path=project.stage_path(record)
    if record.get('bindings'):
        # Native material identity is shared by many meshes. Give each imported
        # mesh its own stable identity in a disposable projection, never by
        # modifying the immutable archived USD.
        from .usd import open_stage
        from .store import uid
        from pxr import Usd,UsdGeom,Sdf
        directory=project.root/'.cadgit'/'staging'/uid('blender_import')
        directory.mkdir(parents=True)
        projected=Usd.Stage.Open(open_stage(import_path).Flatten())
        for prim in projected.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                prim.CreateAttribute('userProperties:cadgit:import_prim_path',Sdf.ValueTypeNames.String).Set(str(prim.GetPath()))
        import_path=directory/'scene.usda'
        projected.Export(str(import_path))
    code = "import bpy,json\nfrom pathlib import Path\n"
    code += "record=" + repr({k:v for k,v in record.items() if not k.startswith('_')}) + "\n"
    code += "library_materials="+repr(library_materials)+"\n"
    code += "root=Path(" + repr(str(project.root)) + ")\n"
    code += "path=" + repr(str(import_path)) + "\n"
    code += '''before=set(bpy.data.objects)
bpy.ops.wm.usd_import(filepath=path,property_import_mode='ALL',create_collection=True)
imported=[o for o in bpy.data.objects if o not in before]
restored=[]
materials_by_revision={}
original_image_names={}
def restore_images(tree,manifest,mid,visited=None):
    visited=visited if visited is not None else set()
    if tree is None or tree in visited:return
    visited.add(tree)
    for node in tree.nodes:
        image=getattr(node,'image',None)
        if image:
            pointer=image.as_pointer() if hasattr(image,'as_pointer') else id(image)
            original=original_image_names.get(pointer)
            weak=getattr(image,'library_weak_reference',None)
            if original is None and weak and Path(weak.filepath).resolve()==Path(manifest['_blend_path']).resolve():
                original=weak.id_name[2:] if weak.id_name.startswith('IM') else None
            if original is None and not weak:original=image.name
            if original in manifest.get('images',{}):image.filepath=str(root/'materials'/mid/manifest['images'][original])
            elif not getattr(image,'packed_file',None) and not getattr(image,'packed_files',[]) and getattr(image,'source','FILE') not in {'GENERATED','VIEWER'}:
                raise RuntimeError('Native graph image is not pinned to archived bytes: '+str(original or image.name)+'. Bind its original image name in the material graph_images map.')
        child=getattr(node,'node_tree',None)
        if child:restore_images(child,manifest,mid,visited)
for binding in record.get('bindings',[]):
    mid=binding['material_revision']
    prim_path=binding['prim_path']
    targets=[o for o in imported if o.get('cadgit:import_prim_path')==prim_path or o.get('userProperties:cadgit:import_prim_path')==prim_path]
    if not targets:
        # Compatibility fallback for importers that omit custom properties.
        # A material revision is a candidate filter, never an object identity.
        candidates=[o for o in imported if o.get('cadgit:material_revision')==mid or o.get('userProperties:cadgit:material_revision')==mid]
        leaf=prim_path.split('/')[-1]
        targets=[o for o in candidates or imported if o.name==leaf]
    if len(targets)!=1:
        raise RuntimeError('Cannot restore historical material unambiguously: '+str(binding)+' candidate count '+str(len(targets)))
    if mid not in materials_by_revision:
        descriptor=library_materials.get(mid)
        manifest={'label':descriptor.get('material_name'),'images':descriptor['images']} if descriptor else json.loads((root/'materials'/mid/'manifest.json').read_text())
        blend_path=descriptor['path'] if descriptor else str(root/'materials'/mid/'material.blend')
        manifest['_blend_path']=blend_path
        requested_images=[]
        with bpy.data.libraries.load(blend_path,link=False) as (src,dst):
            requested_images=[name for name in getattr(src,'images',[]) if name in manifest.get('images',{})]
            if requested_images:dst.images=requested_images[:]
            names=[manifest['label']] if manifest.get('label') in src.materials else src.materials if len(src.materials)==1 else []
            if not names:raise RuntimeError('Cannot identify archived material '+mid)
            dst.materials=names[:1]
        for original,image in zip(requested_images,getattr(dst,'images',[])):
            if image:original_image_names[image.as_pointer() if hasattr(image,'as_pointer') else id(image)]=original
        mat=dst.materials[0]
        if not mat:raise RuntimeError('Archived material could not be loaded: '+mid)
        restore_images(mat.node_tree,manifest,mid)
        materials_by_revision[mid]=mat
    mat=materials_by_revision[mid]
    obj=targets[0]
    if not hasattr(obj.data,'materials'):raise RuntimeError('Material target has no material slots: '+prim_path)
    obj.data.materials.clear(); obj.data.materials.append(mat)
    restored.append({'object':obj.name,'material':mat.name,'revision':mid})
print(json.dumps({'imported':len(imported),'restored':restored,'native_file_saved':False}))
'''
    return code


def restore_blender(project, ref):
    return blender_rpc(blender_import_code(project, ref))
