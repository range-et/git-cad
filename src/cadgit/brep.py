"""Optional DualBrep input bundles. Preparing a job does not produce CAD surfaces."""
from pathlib import Path
import json,os,shutil,subprocess,tempfile
import numpy as np
import pyvista as pv
from .store import CadgitError,atomic_json,read_json,uid,now,file_digest
from .compatibility import BREP_JOB_FEATURE
from .usd import meshes

UPSTREAM='https://github.com/AutodeskAILab/DualBrep'
REVISION='9707b4b4e531943f38e83092ff7ad833cc60b2cb'
COLLECTION='artifacts/brep_jobs'


def face_components(triangles,check_cancel=lambda:None):
    """Match trimesh face adjacency: exactly two triangles share an edge.

    Vertex-connected components are insufficient: two bodies touching at one
    vertex would be fused for preparation and one discarded by upstream.
    """
    count=len(triangles);edges=triangles[:,[[0,1],[1,2],[2,0]]].reshape(-1,2)
    edges=np.sort(edges,axis=1);order=np.lexsort((edges[:,1],edges[:,0]));sorted_edges=edges[order]
    starts=np.r_[0,np.flatnonzero(np.any(sorted_edges[1:]!=sorted_edges[:-1],axis=1))+1,len(edges)]
    paired=starts[:-1][np.diff(starts)==2];pairs=np.column_stack([order[paired]//3,order[paired+1]//3])
    parent=list(range(count));sizes=[1]*count
    def find(index):
        while parent[index]!=index:parent[index]=parent[parent[index]];index=parent[index]
        return index
    for index,(a,b) in enumerate(pairs):
        if index%4096==0:check_cancel()
        a=find(int(a));b=find(int(b))
        if a==b:continue
        if sizes[a]<sizes[b]:a,b=b,a
        parent[b]=a;sizes[a]+=sizes[b]
    labels={};result=np.empty(count,dtype=np.int64)
    for i in range(count):
        if i%4096==0:check_cancel()
        root=find(i)
        if root not in labels:labels[root]=len(labels)
        result[i]=labels[root]
    return result


def write_mesh_ply(path,mesh):
    # VTK's PLY writer downcasts coordinates to float32. Retain world-space
    # precision here, especially for small parts far from the project origin.
    points=np.asarray(mesh.points,dtype='<f8');triangles=mesh.faces.reshape(-1,4)[:,1:]
    faces=np.empty(len(triangles),dtype=[('count','u1'),('vertices','<i4',(3,))])
    faces['count']=3;faces['vertices']=triangles
    header=('ply\nformat binary_little_endian 1.0\ncomment Git CAD world meters Z-up\n'
            f'element vertex {len(points)}\nproperty double x\nproperty double y\nproperty double z\n'
            f'element face {len(faces)}\nproperty list uchar int vertex_indices\nend_header\n')
    with Path(path).open('wb') as stream:stream.write(header.encode('ascii'));stream.write(points.tobytes());stream.write(faces.tobytes())


def collection(project,create=False):
    root=project.root/COLLECTION
    if (project.root/'artifacts').is_symlink() or root.is_symlink():raise CadgitError('B-rep job storage cannot be a symlink')
    marker=root/'collection.json'
    if root.exists():
        if not root.is_dir():raise CadgitError('B-rep job storage is not a directory')
        if marker.is_symlink():raise CadgitError('Unsafe B-rep collection marker')
        if marker.exists():
            metadata=read_json(marker)
            if not isinstance(metadata,dict) or metadata.get('project_id')!=project.config['id']:raise CadgitError('B-rep jobs belong to another project')
        elif any(root.iterdir()):raise CadgitError('Existing brep_jobs folder is not owned by Git CAD')
    if create:
        root.mkdir(parents=True,exist_ok=True)
        if not marker.exists():atomic_json(marker,{'project_id':project.config['id'],'schema_version':1},replace=False)
    return root


def list_jobs(project):
    root=collection(project)
    if root.exists():
        for child in root.iterdir():
            if child.is_symlink():raise CadgitError('B-rep job directory cannot be a symlink: '+child.name)
            if child.is_dir():
                if not child.resolve().is_relative_to(root.resolve()):raise CadgitError('B-rep job escapes its collection')
                for name in ('manifest.json','COMMITTED'):
                    if (child/name).is_symlink():raise CadgitError('Unsafe B-rep job metadata: '+str(child/name))
    return project.records(COLLECTION)


def get_job(project,ref):
    records=list_jobs(project);exact=[r for r in records if r['id']==ref]
    matches=exact or [r for r in records if r['id'].startswith(ref)]
    if len(matches)!=1:raise CadgitError('Unknown or ambiguous B-rep job: '+ref)
    return matches[0]


def verify_job(project,ref):
    record=get_job(project,ref);result=project.verify(record)
    try:
        request=read_json(project.stage_path(record))
        if not isinstance(request,dict):raise CadgitError('Job request must be an object')
        if request!=record.get('request'):result['errors'].append('Job request differs from committed manifest')
        source=project.resolve(request['source_id'])
        if file_digest(Path(source['_directory'])/'manifest.json')!=request['source_manifest_sha256']:
            result['errors'].append('Source manifest changed')
        source_check=project.verify(source)
        result['errors'].extend('Source: '+error for error in source_check['errors'])
    except (OSError,ValueError,KeyError,TypeError,CadgitError) as exc:result['errors'].append(str(exc))
    result['ok']=not result['errors'];return result


def prepare_job(project,ref,selections=None,split_components=False,allow_base_mesh=False,cancelled=None):
    record=project.resolve(ref)
    if not project.verify(record)['ok']:raise CadgitError('Source integrity verification failed')
    collection(project)
    def check_cancel():
        if cancelled is not None and cancelled.is_set():raise CadgitError('B-rep job preparation cancelled')
    check_cancel()
    selected=list(dict.fromkeys(selections or []));parts={}
    for path in selected or [None]:
        for part in meshes(project.stage_path(record),path):parts[part['path']]=part
    if not parts:raise CadgitError('Selection contains no visible mesh geometry')
    if any(p['subdivision']!='none' for p in parts.values()) and not allow_base_mesh:
        raise CadgitError('Subdivision surfaces require explicit base-mesh acknowledgement')
    staging=Path(tempfile.mkdtemp(prefix='brepjob_',dir=project.root/'.cadgit/staging'))
    committed=False
    try:
        (staging/'inputs').mkdir();entries=[];warnings=[]
        for path,part in sorted(parts.items()):
            check_cancel()
            poly=pv.PolyData(part['points'],part['faces']).triangulate().clean(tolerance=0,absolute=True)
            if not poly.n_cells or poly.n_verts or poly.n_lines:raise CadgitError('No usable triangles in '+path)
            faces=poly.faces.reshape(-1,4)[:,1:];points=np.asarray(poly.points)
            area=np.linalg.norm(np.cross(points[faces[:,1]]-points[faces[:,0]],points[faces[:,2]]-points[faces[:,0]]),axis=1)
            if not np.isfinite(area).all() or (area<=0).any():raise CadgitError('Degenerate triangles in '+path)
            labels=face_components(faces,check_cancel);regions=np.unique(labels)
            if len(regions)>1 and not split_components:
                raise CadgitError(path+' contains '+str(len(regions))+' disconnected components. Split explicitly; nested shells may represent cavities.')
            for region in regions:
                check_cancel();piece=poly.extract_cells(np.flatnonzero(labels==region)).extract_surface(algorithm='dataset_surface').triangulate()
                piece.clear_data();name='part'+str(len(entries)+1).zfill(4);relative='inputs/'+name+'.ply'
                write_mesh_ply(staging/relative,piece)
                # write_mesh_ply writes these exact float64 values. Do not use
                # vtkPLYReader here: it downcasts even double PLY coordinates.
                p=np.asarray(piece.points,dtype=np.float64)
                lower=p.min(0);upper=p.max(0);center=(lower+upper)/2;scale=float(np.max(upper-lower))/1.8
                if not np.isfinite(scale) or scale<=0:raise CadgitError('Invalid normalization bounds: '+path)
                edges=piece.extract_feature_edges(boundary_edges=True,non_manifold_edges=True,feature_edges=False,manifold_edges=False).n_cells
                note=[]
                if edges:note.append(str(edges)+' open/nonmanifold edges; reconstruction quality requires review')
                if len(regions)>1:note.append('Explicit shell splitting may change cavity/body interpretation')
                if part['subdivision']!='none':note.append('Authored base polygons only; subdivision not evaluated')
                entries.append({'id':name,'input':relative,'source_prim':path,'component_index':int(region),
                    'source_component_count':len(regions),'points':len(p),'triangles':piece.n_cells,
                    'input_units':'m','world_up_axis':'Z','bounds_m':[lower.tolist(),upper.tolist()],
                    'normalization':{'mode':'upstream_uniform_0.9','center_m':center.tolist(),'scale_m':scale,
                      'normalized_to_world_m':'point * scale_m + center_m',
                      'normalized_to_step_mm':'(point * scale_m + center_m) * 1000'},
                    'expected_normalized_step':'brep/'+name+'.step','warnings':note})
                warnings.extend(path+': '+n for n in note)
        request={'schema_version':1,'required_features':[BREP_JOB_FEATURE],'status':'prepared',
            'source_id':record['id'],'source_manifest_sha256':file_digest(Path(record['_directory'])/'manifest.json'),
            'source_inventory':record['files'],'selections':selected,'parts':entries,
            'material_associations':{'native':record.get('bindings',[]),'library':record.get('library_bindings',[])},
            'provider':{'name':'dualbrep','repository':UPSTREAM,'revision':REVISION,
                        'code_license':'Apache-2.0','checkpoint_license':'not established; review model terms separately'},
            'parameters':{'pipeline':'pointcloud_autoencoder','per_axis_norm':False,'id_aug':3,'test_res':256,
                          'rotations':'all','seed':0,'split_components':split_components,'allow_base_mesh':allow_base_mesh},
            'runtime':{'optional':True,'preferred_device':'cuda','execution':'not implemented in this preparation-only release',
                       'checkpoints':['pc_vae.ckpt','parametrizer.ckpt'],'checkpoint_hashes':None},
            'output_contract':{'format':'STEP','units':'mm','assembly':'separate validated solids; no automatic boolean union',
                'required_checks':['expected output for every part','OCC parse and solid validity','apply inverse normalization',
                    'explicit STEP units and re-read bounds','component count and assembly placement','source-to-result deviation in physical units'],
                'original_nurbs_restored':False,'original_feature_history_restored':False,'materials':'part associations only; no face correspondence promised'}}
        atomic_json(staging/'request.json',request)
        atomic_json(staging/'runtime.example.json',{'enabled':False,'python':'/absolute/path/to/dualbrep-env/bin/python',
                   'checkout':'/absolute/path/to/DualBrep','device':'auto','required_revision':REVISION})
        instructions=Path(__file__).parent/'resources/brep_job_readme.txt'
        shutil.copyfile(instructions,staging/'README.txt')
        with project.lock():
            check_cancel();destination=collection(project,create=True)/uid('brepjob')
            result=project.commit(staging,destination,{'schema_version':1,'required_features':[BREP_JOB_FEATURE],
                'id':destination.name,'created_at':now(),'label':record['label']+' • B-rep inputs',
                'source_id':record['id'],'status':'prepared','entry_layer':'request.json','request':request,'warnings':warnings})
            committed=True;return result
    finally:
        if not committed:shutil.rmtree(staging,ignore_errors=True)


def runtime_status(python=None,checkout=None):
    """Probe an explicit external runtime; never install or import Torch in the UI."""
    python=python or os.environ.get('CADGIT_DUALBREP_PYTHON')
    checkout=checkout or os.environ.get('CADGIT_DUALBREP_CHECKOUT')
    code='''import json,importlib
r={"cuda":False,"mps":False,"missing":[]}
for name in ("torch","torch_cluster","lightning","trimesh","omegaconf","OCC.Core","open3d","ray","timm","x_transformers","mcubes","scipy","networkx","einops","cloudpathlib"):
 try:importlib.import_module(name)
 except Exception as e:r["missing"].append(name+": "+str(e))
try:
 import torch
 r["torch"]=torch.__version__;r["cuda"]=torch.cuda.is_available();r["mps"]=bool(hasattr(torch.backends,"mps") and torch.backends.mps.is_available())
 if r["cuda"]:
  from torch_cluster import fps
  x=torch.rand(64,3,device="cuda");fps(x,ratio=.25);torch.cuda.synchronize()
  r["cuda_device"]=torch.cuda.get_device_name(0)
except Exception as e:r["missing"].append("device probe: "+str(e));r["cuda"]=False
print("CADGIT_RUNTIME="+json.dumps(r))
'''
    result={'preparation_available':True,'execution_available':False,'cuda_prerequisites_ready':False,
            'cuda':False,'mps':False,'missing':[],'release_scope':'job preparation; inference adapter not yet enabled'}
    if not python:
        result['missing'].append('No external reconstruction Python configured')
    else:
        try:
            probe=subprocess.run([str(python),'-I','-c',code],capture_output=True,text=True,timeout=45)
            lines=[line for line in probe.stdout.splitlines() if line.startswith('CADGIT_RUNTIME=')]
            if probe.returncode or not lines:raise ValueError('Runtime probe failed: '+probe.stderr[-1000:])
            payload=json.loads(lines[-1].split('=',1)[1])
            if not isinstance(payload,dict) or type(payload.get('cuda')) is not bool or type(payload.get('mps')) is not bool or not isinstance(payload.get('missing'),list) or any(not isinstance(item,str) for item in payload['missing']):raise ValueError('Invalid runtime probe report')
            if any(key in payload and not isinstance(payload[key],str) for key in ('torch','cuda_device')):raise ValueError('Invalid runtime probe report')
            result.update({key:payload[key] for key in ('cuda','mps','missing','torch','cuda_device') if key in payload})
        except (OSError,ValueError,subprocess.TimeoutExpired) as exc:result['missing'].append(str(exc))
    if not checkout:result['missing'].append('No DualBrep checkout configured')
    else:
        root=Path(checkout).expanduser()
        for name in ('ae_reconstruct.py','rebuild.py','postprocess.py','config_pc.yaml','checkpoints/pc_vae.ckpt','checkpoints/parametrizer.ckpt'):
            if not (root/name).is_file():result['missing'].append('Missing '+name)
        try:
            revision=subprocess.check_output(['git','-C',str(root),'rev-parse','HEAD'],text=True,stderr=subprocess.DEVNULL,timeout=5).strip()
            result['checkout_revision']=revision
            if revision!=REVISION:result['missing'].append('Checkout differs from inspected upstream revision')
            dirty=subprocess.run(['git','-C',str(root),'diff','--quiet','HEAD'],timeout=5).returncode
            if dirty:result['missing'].append('Upstream checkout has tracked modifications or cannot be checked')
        except (OSError,subprocess.SubprocessError):result['missing'].append('Cannot identify upstream checkout revision')
    if not result['cuda']:result['missing'].append('Compatible CUDA device unavailable; upstream CPU/MPS path is not supported')
    result['cuda_prerequisites_ready']=bool(result['cuda'] and not result['missing'])
    return result
