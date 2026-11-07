"""Create ordinary native working files; keep their ancestry in project events/sidecars."""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path
from .store import CadgitError, atomic_json, uid, now,read_json,publish_file


def targets(project):
    return read_json(project.root/'cadgit.json').get('open_targets',[
        {'label':'Blender','kind':'blender','extension':'.blend','executable':'/Applications/Blender.app/Contents/MacOS/Blender'},
        {'label':'Rhino','kind':'rhino','extension':'.3dm','application':'/Applications/Rhino 8.app'},
    ])


def create_native(project, ref, target, output, launch=True):
    record=project.resolve(ref)
    verification=project.verify(record['id'])
    if not verification['ok']:raise CadgitError('Source snapshot failed integrity verification')
    output=Path(output).expanduser().absolute()
    sidecar=Path(str(output)+'.cadgit.json')
    if output.exists() or output.is_symlink() or sidecar.exists() or sidecar.is_symlink():raise CadgitError(f'Output already exists: {output}')
    kind=target['kind']
    if kind not in ('blender','rhino','external'):raise CadgitError('Unknown target adapter: '+kind)
    extension=target.get('extension',{'blender':'.blend','rhino':'.3dm','external':'.usdz'}[kind])
    if output.suffix.lower()!=extension.lower():raise CadgitError('Output must end with '+extension)
    output.parent.mkdir(parents=True,exist_ok=True)
    lineage={'schema_version':1,'id':uid('handoff'),'created_at':now(),'source_id':record['id'],'project':str(project.root),'target':kind,'file':str(output),'representation':'tessellated_mesh' if kind=='rhino' else 'usd_import'}
    staging=project.root/'.cadgit'/'staging'/lineage['id'];staging.mkdir(parents=True)
    staged=staging/('working'+extension)
    sidecar_published=False;file_published=False
    try:
        if kind=='blender':
            from .connectors import blender_import_code,script
            executable=target.get('executable') or shutil.which('blender')
            if not executable or not Path(executable).exists():raise CadgitError('Configure the Blender executable in Settings')
            code='import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\n'+blender_import_code(project,record['id'])
            code+='\nbpy.ops.file.make_paths_absolute()\nbpy.ops.wm.save_as_mainfile(filepath='+repr(str(staged))+',relative_remap=False)\n'
            runner=staging/'create.py';runner.write_text(code)
            result=subprocess.run([executable,'--background','--factory-startup','--python-exit-code','1','--python',str(runner)],capture_output=True,text=True,timeout=180)
            (staging/'creation.log').write_text(result.stdout+'\n'+result.stderr)
            if result.returncode or not staged.exists():raise CadgitError('Blender file creation failed. See '+str(staging/'creation.log'))
            launcher=project.root/'.cadgit'/'blender_save_hook.py';launcher.write_text(script('blender_hook.py',project))
            command=[executable,str(output),'--python',str(launcher)]
        elif kind=='rhino':
            import rhino3dm as r
            from .usd import meshes
            model=r.File3dm();model.Settings.ModelUnitSystem=r.UnitSystem.Millimeters
            parts=meshes(project.stage_path(record))
            if not parts:raise CadgitError('No supported mesh geometry in this USD snapshot')
            for part in parts:
                mesh=r.Mesh()
                for point in part['points']*1000:mesh.Vertices.Add(*map(float,point))
                faces=part['faces'];i=0
                while i<len(faces):
                    n=int(faces[i]);indices=faces[i+1:i+1+n];i+=n+1
                    # USD polygons are triangulated with VTK rather than a concave-unsafe fan.
                    if n in (3,4):mesh.Faces.AddFace(*map(int,indices))
                    else:
                        import pyvista as pv
                        polygon=pv.PolyData(part['points'][indices],[n,*range(n)]).triangulate()
                        for triangle in polygon.faces.reshape(-1,4)[:,1:]:mesh.Faces.AddFace(*[int(indices[j]) for j in triangle])
                mesh.Normals.ComputeNormals();mesh.Compact()
                attrs=r.ObjectAttributes();attrs.Name=part['path'].rsplit('/',1)[-1]
                attrs.SetUserString('cadgit_source_snapshot',record['id']);attrs.SetUserString('cadgit_source_prim',part['path'])
                binding=next((b for b in record.get('bindings',[]) if b['prim_path']==part['path']),None)
                if binding:attrs.SetUserString('cadgit_material_revision',binding['material_revision'])
                logical=next((b for b in record.get('library_bindings',[]) if b['prim_path']==part['path']),None)
                if logical:
                    attrs.SetUserString('cadgit_library_material_revision',logical['library_material_revision'])
                    attrs.SetUserString('cadgit_library_appearance_source',logical.get('appearance_source','library'))
                model.Objects.AddMesh(mesh,attrs)
            if not model.Write(str(staged),8):raise CadgitError('Rhino native file write failed')
            command=['open','-a',target.get('application','/Applications/Rhino 8.app'),str(output)]
        else:
            from pxr import UsdUtils,Sdf
            if extension!='.usdz':raise CadgitError('External targets currently receive packaged .usdz files')
            if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(project.stage_path(record))),str(staged)):raise CadgitError('USD packaging failed')
            argv=target.get('command')
            if not isinstance(argv,list) or not argv or not all(isinstance(x,str) for x in argv):raise CadgitError('External target requires a command argument list with {usd}')
            command=[x.replace('{usd}',str(output)) for x in argv]
        # Publish ancestry before the normal native file becomes available for opening.
        atomic_json(sidecar,lineage,replace=False);sidecar_published=True
        publish_file(staged,output);file_published=True
        try:project.event('native_handoff',lineage)
        except OSError as exc:lineage['publication_warning']='Native file created; event could not be written: '+str(exc)
    except Exception:
        if sidecar_published and not file_published:sidecar.unlink(missing_ok=True)
        raise
    if launch:
        try:
            subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            lineage['launched']=True
        except OSError as exc:
            lineage['launched']=False;lineage['launch_error']=str(exc)
    return lineage
