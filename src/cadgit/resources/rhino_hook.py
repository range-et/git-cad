import Rhino, scriptcontext, json, uuid, pathlib, traceback, shutil, datetime, os
_cadgit_root=pathlib.Path(PROJECT)
_cadgit_doc=__rhino_doc__
_cadgit_state=scriptcontext.sticky.setdefault('cadgit_pending:'+str(_cadgit_root),{'queue':[],'busy':False})
_cadgit_queue=_cadgit_state['queue']

def cadgit_recover_pending():
    queued={str(directory.resolve()) for directory,metadata in _cadgit_queue}
    pending=[]
    for marker in (_cadgit_root/'.cadgit'/'inbox').glob('*/pending.json'):
        directory=marker.parent
        if str(directory.resolve()) in queued:continue
        if any((directory/name).exists() for name in ('ready.json','receipt.json','failed.json','error.json')):continue
        if not (directory/'native_capture.3dm').is_file():continue
        try:
            metadata=json.loads(marker.read_text())
            if not isinstance(metadata,dict):raise ValueError('Pending metadata is not an object')
            if type(metadata.get('sequence',0)) is not int or metadata.get('sequence',0)<0:raise ValueError('Invalid pending capture sequence')
            if not isinstance(metadata.get('captured_at',''),str):raise ValueError('Invalid pending capture timestamp')
            pending.append((directory,metadata))
        except Exception as exc:
            print('CAD-GIT pending capture recovery needs attention:',marker,str(exc))
    pending.sort(key=lambda entry:(entry[1].get('sequence',0),entry[1].get('captured_at',''),entry[0].name))
    _cadgit_queue.extend(pending)
    _cadgit_queue.sort(key=lambda entry:(entry[1].get('sequence',0),entry[1].get('captured_at',''),entry[0].name))

cadgit_recover_pending()

def cadgit_export(doc,directory,metadata):
    try:
        # Use Rhino's tessellator without invoking the interactive USD exporter.
        # FileUsd.Write can cancel in an isolated headless document on macOS.
        scale=Rhino.RhinoMath.UnitScale(doc.ModelUnitSystem,Rhino.UnitSystem.Meters)
        lines=['#usda 1.0','( upAxis = "Z"',' metersPerUnit = '+str(scale),' defaultPrim = "Rhino" )','def Xform "Rhino" {']
        unsupported=[]
        for obj in doc.Objects:
            if obj.IsDeleted:continue
            geo=obj.Geometry
            if isinstance(geo,Rhino.Geometry.Mesh): parts=[geo]
            else:
                brep=geo.ToBrep() if hasattr(geo,'ToBrep') else geo if isinstance(geo,Rhino.Geometry.Brep) else None
                parts=list(Rhino.Geometry.Mesh.CreateFromBrep(brep,Rhino.Geometry.MeshingParameters.Default) or []) if brep else []
            if not parts:
                unsupported.append(str(obj.Id));continue
            mesh=Rhino.Geometry.Mesh()
            for part in parts:mesh.Append(part)
            points=[(float(v.X),float(v.Y),float(v.Z)) for v in mesh.Vertices]
            counts=[];indices=[]
            for face in mesh.Faces:
                ids=[face.A,face.B,face.C] if face.IsTriangle else [face.A,face.B,face.C,face.D]
                counts.append(len(ids));indices.extend(ids)
            name='Object_'+str(obj.Id).replace('-','_')
            material_revision=obj.Attributes.GetUserString('cadgit_material_revision')
            if material_revision:lines.append('')
            lines.extend(['def Mesh "'+name+'" {','custom string cadgit:sourceObject = '+json.dumps(str(obj.Id)),'custom string cadgit:objectName = '+json.dumps(obj.Attributes.Name or ''),'point3f[] points = '+str(points),'int[] faceVertexCounts = '+str(counts),'int[] faceVertexIndices = '+str(indices),'uniform token subdivisionScheme = "none"'])
            if material_revision:lines.append('custom string userProperties:cadgit:material_revision = '+json.dumps(material_revision))
            logical_revision=obj.Attributes.GetUserString('cadgit_library_material_revision')
            if logical_revision:
                lines.append('custom string userProperties:cadgit:library_material_revision = '+json.dumps(logical_revision))
                lines.append('custom string userProperties:cadgit:library_appearance_source = '+json.dumps(obj.Attributes.GetUserString('cadgit_library_appearance_source') or 'library'))
            lines.append('}')
        lines.append('}')
        if unsupported:raise RuntimeError('USD snapshot incomplete: unsupported Rhino geometry '+', '.join(unsupported))
        (directory/'scene.usda').write_text('\n'.join(lines))
        branch=json.loads((_cadgit_root/'cadgit.json').read_text()).get('active_branches',{}).get('rhino','main')
        (directory/'ready.tmp').write_text(json.dumps({'source':'rhino','branch':metadata.pop('branch',branch),'file':'scene.usda','label':metadata.get('document_name') or 'Rhino snapshot','metadata':metadata}))
        os.replace(directory/'ready.tmp',directory/'ready.json')
        (directory/'pending.json').unlink(missing_ok=True)
        print('CAD-GIT Rhino snapshot ready')
    except Exception as exc:
        (directory/'failed.json').write_text(json.dumps({'source':'rhino','error':str(exc),'traceback':traceback.format_exc()}))
        print('CAD-GIT export failed:',exc)

def cadgit_capture(trigger='user_save',document=None):
    doc_source=document or _cadgit_doc
    directory=_cadgit_root/'.cadgit'/'inbox'/uuid.uuid4().hex
    directory.mkdir(parents=True,exist_ok=True)
    captured_at=datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z')
    seq_file=_cadgit_root/'.cadgit'/'sequence_rhino.json'
    sequence=json.loads(seq_file.read_text()).get('sequence',0)+1 if seq_file.exists() else 1
    seq_tmp=seq_file.with_suffix('.tmp');seq_tmp.write_text(json.dumps({'sequence':sequence}));os.replace(seq_tmp,seq_file)
    metadata={'sequence':sequence,'captured_at':captured_at,'trigger':trigger,'native_capture':True,'native_path':doc_source.Path,'document_name':doc_source.Name,'native_state_saved':trigger=='user_save','app_version':str(Rhino.RhinoApp.Version),'units':str(doc_source.ModelUnitSystem),'warnings':['Rhino capture preserves geometry, layers and object names; classic material shading is not transferred yet; block instances are expanded to geometry; custom renderer content may require manual USD export'],'branch':json.loads((_cadgit_root/'cadgit.json').read_text()).get('active_branches',{}).get('rhino','main')}
    sidecar=pathlib.Path((doc_source.Path or '')+'.cadgit.json')
    if sidecar.is_file():
        lineage=json.loads(sidecar.read_text());metadata['imported_from']=lineage.get('source_id');metadata['handoff_id']=lineage.get('id')
    if trigger=='user_save':
        try:
            # EndSave can precede the final working-file rename. Serialize memory now;
            # export an isolated document on Idle after the save stack unwinds.
            snapshot=Rhino.FileIO.File3dm()
            try:
                snapshot.Settings.ModelUnitSystem=doc_source.ModelUnitSystem
                snapshot.Settings.ModelAbsoluteTolerance=doc_source.ModelAbsoluteTolerance
                for layer in doc_source.Layers:snapshot.Layers.Add(layer)
                for material in doc_source.Materials:snapshot.Materials.Add(material)
                for obj in doc_source.Objects:
                    if obj.IsDeleted:continue
                    if getattr(obj,'IsInstanceDefinitionGeometry',False):continue
                    def freeze_object(item,transform,name_prefix='',parent_attributes=None):
                        attrs=item.Attributes.Duplicate()
                        if isinstance(item,Rhino.DocObjects.InstanceObject):
                            instance_transform=transform*item.InstanceXform
                            prefix=name_prefix+(attrs.Name or item.InstanceDefinition.Name)+'__'
                            for child in item.InstanceDefinition.GetObjects():freeze_object(child,instance_transform,prefix,attrs)
                        else:
                            geometry=item.Geometry.Duplicate()
                            geometry.Transform(transform)
                            if name_prefix:
                                import System
                                attrs.ObjectId=System.Guid.NewGuid()
                                attrs.Name=name_prefix+(attrs.Name or str(item.Id))
                                attrs.SetUserString('cadgit_instance_source',str(item.Id))
                                if parent_attributes and attrs.MaterialSource==Rhino.DocObjects.ObjectMaterialSource.MaterialFromParent:
                                    attrs.MaterialSource=parent_attributes.MaterialSource;attrs.MaterialIndex=parent_attributes.MaterialIndex
                            snapshot.Objects.Add(geometry,attrs)
                    freeze_object(obj,Rhino.Geometry.Transform.Identity)
                if not snapshot.Write(str(directory/'native_capture.3dm'),8):
                    raise RuntimeError('In-memory native geometry snapshot failed')
            finally:snapshot.Dispose()
            (directory/'pending.tmp').write_text(json.dumps(metadata))
            os.replace(directory/'pending.tmp',directory/'pending.json')
            _cadgit_queue.append((directory,metadata))
        except Exception as exc:
            (directory/'failed.json').write_text(json.dumps({'source':'rhino','error':'Exact native save copy failed: '+str(exc)}))
    else: cadgit_export(doc_source,directory,metadata)

def cadgit_idle(sender,args):
    if _cadgit_state['busy'] or not _cadgit_queue:return
    _cadgit_state['busy']=True
    directory,metadata=_cadgit_queue.pop(0)
    doc=None
    try:
        doc=Rhino.RhinoDoc.OpenHeadless(str(directory/'native_capture.3dm'))
        if not doc:raise RuntimeError('Cannot reopen exact native save staging copy')
        cadgit_export(doc,directory,metadata)
    except Exception as exc:
        (directory/'failed.json').write_text(json.dumps({'source':'rhino','error':str(exc)}))
    finally:
        if doc:doc.Dispose()
        _cadgit_state['busy']=False

def cadgit_saved(sender,args):
    sidecar=pathlib.Path((args.Document.Path or '')+'.cadgit.json')
    belongs=sidecar.is_file() and json.loads(sidecar.read_text()).get('project')==str(_cadgit_root)
    if args.Document.RuntimeSerialNumber==_cadgit_doc.RuntimeSerialNumber or belongs:cadgit_capture('user_save',args.Document)
cadgit_saved._cadgit_project=PROJECT
cadgit_idle._cadgit_project=PROJECT
cadgit_capture._cadgit_project=PROJECT
old=scriptcontext.sticky.get('cadgit_save_handler')
previous_project=getattr(old,'_cadgit_project',None) or getattr(old,'__globals__',{}).get('PROJECT')
if previous_project and previous_project!=PROJECT:print('CAD-GIT switched Rhino capture from '+previous_project+' to '+PROJECT)
if old:Rhino.RhinoDoc.EndSaveDocument-=old
old_idle=scriptcontext.sticky.get('cadgit_idle_handler')
if old_idle:Rhino.RhinoApp.Idle-=old_idle
Rhino.RhinoDoc.EndSaveDocument+=cadgit_saved
Rhino.RhinoApp.Idle+=cadgit_idle
scriptcontext.sticky['cadgit_save_handler']=cadgit_saved
scriptcontext.sticky['cadgit_idle_handler']=cadgit_idle
scriptcontext.sticky['cadgit_capture']=cadgit_capture
scriptcontext.sticky['cadgit_active_project']=PROJECT
print('CAD-GIT save hook attached to Rhino; project:',PROJECT)
