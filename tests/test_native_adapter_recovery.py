"""Adapter contract tests with isolated fake native runtimes, never live apps."""
import json,sys,types
from pathlib import Path
from contextlib import contextmanager
from cadgit.store import Project,atomic_json
from cadgit.usd import assemble,open_stage
from cadgit.connectors import blender_import_code
from test_history import box


class Event:
    def __init__(self):self.handlers=[]
    def __iadd__(self,handler):self.handlers.append(handler);return self
    def __isub__(self,handler):self.handlers.remove(handler);return self


def rhino_runtime(monkeypatch):
    opened=[];disposed=[]
    def open_doc(path):
        opened.append(path)
        return types.SimpleNamespace(Dispose=lambda:disposed.append(path))
    rhino=types.SimpleNamespace(RhinoDoc=types.SimpleNamespace(EndSaveDocument=Event(),OpenHeadless=open_doc),RhinoApp=types.SimpleNamespace(Idle=Event()))
    context=types.SimpleNamespace(sticky={})
    monkeypatch.setitem(sys.modules,'Rhino',rhino);monkeypatch.setitem(sys.modules,'scriptcontext',context)
    return rhino,context,opened,disposed


def attach_fake_rhino(root):
    module=types.ModuleType('cadgit.resources.rhino_hook');namespace=module.__dict__
    namespace.update(PROJECT=str(root),__rhino_doc__=types.SimpleNamespace(RuntimeSerialNumber=123))
    path=Path(__file__).resolve().parents[1]/'src/cadgit/resources/rhino_hook.py'
    namespace['__file__']=str(path);sys.modules[module.__name__]=module
    exec(compile(path.read_text(),str(path),'exec'),namespace)
    return namespace


def pending(root,name,sequence):
    directory=root/'.cadgit/inbox'/name;directory.mkdir(parents=True)
    (directory/'native_capture.3dm').write_bytes(b'fake frozen native state')
    atomic_json(directory/'pending.json',{'sequence':sequence,'captured_at':'2026-11-07T12:00:00Z'})
    return directory


def test_rhino_reattach_retains_pending_work_without_duplicate_handlers(tmp_path,monkeypatch):
    root=Project.init(tmp_path/'project').root
    rhino,context,opened,disposed=rhino_runtime(monkeypatch)
    directory=pending(root,'capture',1)
    first=attach_fake_rhino(root);second=attach_fake_rhino(root)
    assert first['_cadgit_queue'] is second['_cadgit_queue']
    assert len(second['_cadgit_queue'])==1
    assert len(rhino.RhinoDoc.EndSaveDocument.handlers)==len(rhino.RhinoApp.Idle.handlers)==1
    exported=[]
    def export(doc,directory,metadata):
        exported.append(metadata['sequence']);atomic_json(directory/'ready.json',{'file':'scene.usda'})
    second['cadgit_export']=export;second['cadgit_idle'](None,None)
    assert exported==[1] and len(opened)==len(disposed)==1
    assert not second['_cadgit_queue']
    assert not attach_fake_rhino(root)['_cadgit_queue']


def test_rhino_recovers_durable_pending_captures_after_runtime_restart(tmp_path,monkeypatch):
    root=Project.init(tmp_path/'project').root
    rhino,context,opened,disposed=rhino_runtime(monkeypatch)
    pending(root,'later',2);pending(root,'earlier',1)
    completed=pending(root,'completed',3);atomic_json(completed/'receipt.json',{'snapshot_id':'already_done'})
    failed=pending(root,'failed',4);atomic_json(failed/'failed.json',{'error':'manual attention required'})
    namespace=attach_fake_rhino(root)
    assert [meta['sequence'] for directory,meta in namespace['_cadgit_queue']]==[1,2]
    # A complete interpreter restart loses sticky state, but disk still recovers.
    context.sticky.clear();rhino.RhinoDoc.EndSaveDocument.handlers.clear();rhino.RhinoApp.Idle.handlers.clear()
    namespace=attach_fake_rhino(root)
    assert [meta['sequence'] for directory,meta in namespace['_cadgit_queue']]==[1,2]
    exported=[];namespace['cadgit_export']=lambda doc,directory,metadata:exported.append(metadata['sequence'])
    namespace['cadgit_idle'](None,None);namespace['cadgit_idle'](None,None)
    assert exported==[1,2] and len(opened)==len(disposed)==2


def test_blender_shared_material_uses_mesh_identity_and_restores_nested_images(tmp_path,monkeypatch):
    p=Project.init(tmp_path/'project');snapshot=p.ingest(box(tmp_path/'input.usda'))
    mid='mat_shared';folder=p.root/'materials'/mid;folder.mkdir()
    from cadgit.store import inventory
    (folder/'material.blend').write_bytes(b'opaque native asset');(folder/'images').mkdir();(folder/'images/archived.png').write_bytes(b'opaque image fixture')
    atomic_json(folder/'manifest.json',{'schema_version':1,'id':mid,'label':'Shared shader','entry_layer':'material.blend','files':inventory(folder),'images':{'Texture':'images/archived.png'}})
    (folder/'COMMITTED').write_text(mid)
    assembly=assemble(p,[{'snapshot_id':snapshot['id'],'prim_path':'/World/Part','material_revision':mid},{'snapshot_id':snapshot['id'],'prim_path':'/World/Part','material_revision':mid,'translation':[3,0,0]}])
    source_bytes=p.stage_path(assembly).read_bytes()
    image=types.SimpleNamespace(name='Texture.001',filepath='/missing/original.png')
    class Tree:
        def __init__(self,nodes):self.nodes=nodes
    subtree=Tree([types.SimpleNamespace(image=image)])
    material=types.SimpleNamespace(name='Shared shader',node_tree=Tree([types.SimpleNamespace(node_tree=subtree)]))
    objects=[];loads=[]
    class Object:
        def __init__(self,name,props):self.name=name;self.props=props;self.data=types.SimpleNamespace(materials=[])
        def get(self,key):return self.props.get(key)
    def usd_import(filepath,**kwargs):
        stage=open_stage(filepath)
        for prim in stage.Traverse():
            if prim.GetTypeName()=='Mesh':
                props={attr.GetName().removeprefix('userProperties:'):attr.Get() for attr in prim.GetAttributes() if attr.GetName().startswith('userProperties:')}
                # Blender can rename repeated names; identity must still resolve.
                objects.append(Object('Part' if not objects else 'Part.001',props))
    @contextmanager
    def library_load(path,link=False):
        loads.append(path);src=types.SimpleNamespace(materials=['Shared shader'],images=['Texture']);dst=types.SimpleNamespace(materials=[],images=[])
        yield src,dst
        dst.materials[:]=[material for name in dst.materials]
        dst.images[:]=[image for name in dst.images]
    bpy=types.SimpleNamespace(data=types.SimpleNamespace(objects=objects,libraries=types.SimpleNamespace(load=library_load)),ops=types.SimpleNamespace(wm=types.SimpleNamespace(usd_import=usd_import)))
    monkeypatch.setitem(sys.modules,'bpy',bpy)
    exec(blender_import_code(p,assembly['id']),{})
    assert len(objects)==2 and len(loads)==1
    assert objects[0].data.materials==objects[1].data.materials==[material]
    assert image.filepath==str(folder/'images/archived.png')
    assert p.stage_path(assembly).read_bytes()==source_bytes


def blender_runtime(monkeypatch):
    bpy=types.ModuleType('bpy');app=types.ModuleType('bpy.app');handlers=types.ModuleType('bpy.app.handlers')
    handlers.save_post=[];handlers.persistent=lambda function:function
    app.handlers=handlers;bpy.app=app
    monkeypatch.setitem(sys.modules,'bpy',bpy);monkeypatch.setitem(sys.modules,'bpy.app',app);monkeypatch.setitem(sys.modules,'bpy.app.handlers',handlers)
    return bpy


def attach_fake_blender(project):
    module=types.ModuleType('cadgit.resources.blender_hook');namespace=module.__dict__
    namespace['PROJECT']=str(project.root)
    path=Path(__file__).resolve().parents[1]/'src/cadgit/resources/blender_hook.py'
    namespace['__file__']=str(path);sys.modules[module.__name__]=module
    exec(compile(path.read_text(),str(path),'exec'),namespace)
    return namespace


def test_blender_project_switch_has_one_owner_and_old_detach_cannot_remove_it(tmp_path,monkeypatch,capsys):
    from cadgit import connectors
    a=Project.init(tmp_path/'a');b=Project.init(tmp_path/'b');bpy=blender_runtime(monkeypatch)
    unrelated=lambda:None;bpy.app.handlers.save_post.append(unrelated)
    attach_fake_blender(a);attach_fake_blender(b)
    hooks=[h for h in bpy.app.handlers.save_post if hasattr(h,'_cadgit_project')]
    assert len(hooks)==1 and hooks[0]._cadgit_project==str(b.root)
    assert unrelated in bpy.app.handlers.save_post
    assert 'switched Blender capture from' in capsys.readouterr().out
    monkeypatch.setattr(connectors,'blender_rpc',lambda code:exec(code,{}))
    connectors.detach(a,'blender')
    assert hooks[0] in bpy.app.handlers.save_post


def test_blender_background_capture_cannot_steal_another_project(tmp_path,monkeypatch):
    import pytest
    from cadgit import connectors
    a=Project.init(tmp_path/'a');b=Project.init(tmp_path/'b');bpy=blender_runtime(monkeypatch)
    namespace=attach_fake_blender(b);captured=[];namespace['cadgit_capture']=lambda trigger:captured.append(trigger)
    monkeypatch.setattr(connectors,'blender_rpc',lambda code:exec(code,{}))
    with pytest.raises(RuntimeError,match='capture refused'):connectors.capture(a,'blender',respect_binding=True)
    assert not captured and bpy.app.handlers.save_post[0]._cadgit_project==str(b.root)
    connectors.capture(b,'blender',respect_binding=True)
    assert captured==['tool_snapshot']


def test_rhino_old_project_detach_preserves_current_project_hooks(tmp_path,monkeypatch,capsys):
    from cadgit import connectors
    a=Project.init(tmp_path/'a');b=Project.init(tmp_path/'b')
    rhino,context,opened,disposed=rhino_runtime(monkeypatch)
    attach_fake_rhino(a.root);active=attach_fake_rhino(b.root)
    monkeypatch.setattr(connectors,'rhino_rpc',lambda code,endpoint=None:exec(code,{}))
    connectors.detach(a,'rhino',endpoint='fake://rhino')
    assert context.sticky['cadgit_save_handler'] is active['cadgit_saved']
    assert len(rhino.RhinoDoc.EndSaveDocument.handlers)==len(rhino.RhinoApp.Idle.handlers)==1
    assert 'switched Rhino capture from' in capsys.readouterr().out
    connectors.detach(b,'rhino',endpoint='fake://rhino')
    assert not rhino.RhinoDoc.EndSaveDocument.handlers and not rhino.RhinoApp.Idle.handlers


def test_rhino_background_capture_cannot_steal_another_project(tmp_path,monkeypatch):
    import pytest
    from cadgit import connectors
    a=Project.init(tmp_path/'a');b=Project.init(tmp_path/'b')
    rhino,context,opened,disposed=rhino_runtime(monkeypatch)
    attach_fake_rhino(b.root);captured=[]
    def capture(trigger):captured.append(trigger)
    capture._cadgit_project=str(b.root);context.sticky['cadgit_capture']=capture
    monkeypatch.setattr(connectors,'rhino_rpc',lambda code,endpoint=None:exec(code,{}))
    with pytest.raises(RuntimeError,match='capture refused'):connectors.capture(a,'rhino',endpoint='fake://rhino',respect_binding=True)
    assert not captured
    connectors.capture(b,'rhino',endpoint='fake://rhino',respect_binding=True)
    assert captured==['tool_snapshot']


def test_malformed_rhino_pending_capture_does_not_block_valid_recovery(tmp_path,monkeypatch,capsys):
    root=Project.init(tmp_path/'project').root;rhino_runtime(monkeypatch)
    bad=pending(root,'bad',1);atomic_json(bad/'pending.json',{'sequence':'invalid'})
    pending(root,'valid',2)
    namespace=attach_fake_rhino(root)
    assert [metadata['sequence'] for directory,metadata in namespace['_cadgit_queue']]==[2]
    assert (bad/'native_capture.3dm').exists()
    assert 'recovery needs attention' in capsys.readouterr().out
