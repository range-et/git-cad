from __future__ import annotations
import contextlib, datetime as dt, fcntl, hashlib, json, os, shutil, uuid,sys
from pathlib import Path

from .errors import CadgitError
from .compatibility import check_compatibility

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")

def uid(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"

def read_json(path):
    try:return json.loads(Path(path).read_text())
    except (OSError,ValueError) as exc:raise CadgitError(f'Cannot read JSON {path}: {exc}') from exc

def atomic_write(path, data, replace=True):
    """Publish complete bytes atomically; no-replace publication never clobbers."""
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(f'.{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('xb') as file:
            file.write(data);file.flush();os.fsync(file.fileno())
        if replace:os.replace(temporary,path)
        else:
            try:os.link(temporary,path)
            except FileExistsError:raise CadgitError(f'Output already exists: {path}')
        fsync_dir(path.parent)
    finally:temporary.unlink(missing_ok=True)


def atomic_json(path,value,replace=True):
    atomic_write(path,(json.dumps(value,indent=2,allow_nan=False)+'\n').encode(),replace)


def publish_file(source,destination):
    """Copy through a destination-local temporary file, then publish exclusively."""
    destination=Path(destination).expanduser().absolute();destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.tmp')
    try:
        with Path(source).open('rb') as src,temporary.open('xb') as dst:
            shutil.copyfileobj(src,dst);dst.flush();os.fsync(dst.fileno())
        try:os.link(temporary,destination)
        except FileExistsError:raise CadgitError(f'Output already exists: {destination}')
        fsync_dir(destination.parent)
    finally:temporary.unlink(missing_ok=True)
    return destination


def order_key(record):
    sequence=record.get('commit_sequence')
    return (isinstance(sequence,int),sequence or 0,record.get('committed_at') or record.get('created_at',''),record['id'])


def branch_tip(records,source,branch='main'):
    matching=[r for r in records if r.get('source')==source and r.get('branch','main')==branch]
    parents={r.get('parent') for r in matching}
    tips=[r for r in matching if r['id'] not in parents]
    if len(tips)>1:raise CadgitError(f'Ambiguous branch {source}/{branch}: multiple heads; preserve history and choose a new branch from an explicit version')
    if matching and not tips:raise CadgitError(f'Cycle in branch ancestry: {source}/{branch}')
    return tips[0] if tips else None


def capture_time(value):
    if value is None:return now()
    try:
        parsed=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:raise ValueError('timezone required')
        return parsed.astimezone(dt.timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
    except (ValueError,TypeError,AttributeError):raise CadgitError('captured_at must be an ISO-8601 timestamp with a timezone')

def fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)

def file_digest(path):
    """Hash large native payloads without loading their complete bytes."""
    digest=hashlib.sha256()
    with Path(path).open('rb') as file:
        for block in iter(lambda:file.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()

def inventory(directory):
    result = []
    for path in sorted(Path(directory).rglob("*")):
        if path.is_symlink():raise CadgitError(f"Symlinks are not allowed inside committed records: {path}")
        if path.is_file() and path not in {Path(directory)/"manifest.json",Path(directory)/"COMMITTED"}:
            result.append({"path": str(path.relative_to(directory)), "sha256": file_digest(path), "bytes": path.stat().st_size})
    return result

class Project:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        if not (self.root / "cadgit.json").exists():
            raise CadgitError(f"No CAD-GIT project at {self.root}. Run cad-git init first.")
        self.record_issues={}
        self.config = read_json(self.root / "cadgit.json")
        check_compatibility(self.config,"Project config")
        self.repair_main()

    @classmethod
    def init(cls, root, name=None):
        root = Path(root).expanduser().resolve(); root.mkdir(parents=True, exist_ok=True)
        if (root / "cadgit.json").exists(): return cls(root)
        # Init must not commandeer another tool's folders or overwrite files.
        reserved=['library','history','assemblies','materials','artifacts','main','.cadgit','mcp.example.json']
        conflicts=[str(root/name) for name in reserved if (root/name).exists() or (root/name).is_symlink()]
        if conflicts:raise CadgitError('Initialization would conflict with existing paths: '+', '.join(conflicts)+'. Choose an empty project subfolder.')
        source=root/'source'
        source_exists=source.exists() or source.is_symlink()
        if source_exists and not source.is_dir():raise CadgitError('Initialization requires source/ to be a directory: '+str(source))
        # Read and validate user-owned Git rules before publishing any project
        # state. Keep their exact bytes for both appending and failure rollback.
        rules={}
        for filename,section in [('.gitignore','# CAD-GIT runtime only; history is durable\n.cadgit/\n*.blend1\n*.blend2\n*.3dmbak\n.DS_Store\n'),('.gitattributes','# CAD-GIT native binary formats\n*.3dm binary\n*.blend binary\n*.usdc binary\n*.usdz binary\n')]:
            file=root/filename;before=None
            if file.exists() or file.is_symlink():
                if file.is_symlink() or not file.is_file():raise CadgitError('Initialization requires a regular Git rules file: '+str(file))
                try:before=file.read_bytes();current=before.decode('utf-8')
                except (OSError,UnicodeError) as exc:raise CadgitError('Cannot read Git rules '+str(file)+': '+str(exc)) from exc
            else:current=''
            if '# CAD-GIT' not in current:rules[filename]=(before,(before or b'')+(b'\n' if before else b'')+section.encode())
        import tempfile
        with tempfile.TemporaryDirectory(prefix='.cadgit-init-',dir=root) as temporary:
            prepared=Path(temporary)
            for directory in ['history/events','history/sources','assemblies','materials','artifacts/prints','main','.cadgit/staging','.cadgit/inbox','.cadgit/logs']:(prepared/directory).mkdir(parents=True,exist_ok=True)
            if not source_exists:(prepared/'source').mkdir()
            from pxr import Usd,UsdGeom
            stage=Usd.Stage.CreateNew(str(prepared/'main/empty.usda'));world=UsdGeom.Xform.Define(stage,'/World');stage.SetDefaultPrim(world.GetPrim())
            UsdGeom.SetStageUpAxis(stage,'Z');UsdGeom.SetStageMetersPerUnit(stage,1.0);stage.GetRootLayer().Save();del stage
            atomic_write(prepared/'main/scene.usda',b'#usda 1.0\n( upAxis = "Z"\n metersPerUnit = 1\n defaultPrim = "World"\n subLayers = [@./empty.usda@] )\n')
            atomic_json(prepared/'mcp.example.json',{'mcpServers':{'cad-git':{'command':sys.executable,'args':['-m','cadgit.cli','--project',str(root),'mcp']}}})
            config={'schema_version':1,'schema_minor':0,'required_features':[],'extensions':{},'id':uid('project'),'name':name or root.name,'sources':['rhino','blender'],'material_policy':'native_asset_with_portable_fallback'}
            event_id=now().replace(':','-')+'_'+uid('evt')
            atomic_json(prepared/'history/events'/(event_id+'.json'),{'schema_version':1,'id':event_id,'created_at':now(),'kind':'project_initialized','data':{'project_id':config['id']}})
            published=[];changed_rules=[]
            try:
                for item in prepared.iterdir():
                    if (root/item.name).exists() or (root/item.name).is_symlink():raise CadgitError('Initialization path appeared concurrently: '+str(root/item.name))
                    os.rename(item,root/item.name);published.append(root/item.name)
                for filename,(before,after) in rules.items():
                    file=root/filename
                    if before is not None and (file.is_symlink() or not file.is_file() or file.read_bytes()!=before):raise CadgitError('Git rules changed during initialization: '+str(file))
                    changed_rules.append(filename)
                    atomic_write(file,after,replace=before is not None)
                # The config is the init commit marker and is published last.
                atomic_json(root/'cadgit.json',config,replace=False)
            except Exception:
                # A post-publication fsync can fail after the config appeared.
                # Remove only our own commit marker, never a concurrent project.
                try:
                    if (root/'cadgit.json').is_file() and read_json(root/'cadgit.json').get('id')==config['id']:(root/'cadgit.json').unlink()
                except (OSError,CadgitError):pass
                for filename in reversed(changed_rules):
                    file=root/filename;before,after=rules[filename]
                    # Do not undo another writer's edits or a competing file.
                    if file.is_file() and not file.is_symlink() and file.read_bytes()==after:
                        if before is None:file.unlink()
                        else:atomic_write(file,before)
                for item in reversed(published):
                    if item.is_dir():shutil.rmtree(item)
                    else:item.unlink(missing_ok=True)
                raise
        return cls(root)

    @contextlib.contextmanager
    def lock(self):
        path = self.root / ".cadgit/writer.lock"; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                check_compatibility(read_json(self.root / "cadgit.json"),"Project config")
                yield
            finally: fcntl.flock(f, fcntl.LOCK_UN)

    def event(self, kind, data):
        path = self.root / "history/events" / f"{now().replace(':','-')}_{uid('evt')}.json"
        atomic_json(path, {"schema_version": 1, "id": path.stem, "created_at": now(), "kind": kind, "data": data})

    def records(self,kind='snapshots',strict=True):
        from .models import Snapshot,Assembly
        if kind not in {'snapshots','assemblies','materials','artifacts/prints','artifacts/brep_jobs'}:raise CadgitError('Unknown record collection: '+str(kind))
        paths=(self.root/'history/sources').rglob('manifest.json') if kind=='snapshots' else self.root.glob(f'{kind}/*/manifest.json')
        records=[];issues=[]
        for path in paths:
            if not (path.parent/'COMMITTED').exists():continue
            try:
                record=read_json(path)
                if not isinstance(record,dict):raise CadgitError('Manifest must be an object')
                check_compatibility(record,str(path),legacy=True)
                if kind=='snapshots':Snapshot.model_validate(record)
                elif kind=='assemblies':Assembly.model_validate(record)
                elif not isinstance(record.get('id'),str) or not isinstance(record.get('label'),str):raise CadgitError('Manifest needs a string ID and label')
                sequence=record.get('commit_sequence')
                if sequence is not None and (type(sequence) is not int or sequence<1):raise CadgitError('Invalid commit_sequence')
                record['_directory']=str(path.parent);records.append(record)
            except (CadgitError,ValueError,TypeError) as exc:issues.append({'path':str(path),'error':str(exc)})
        self.record_issues[kind]=issues
        if strict and issues:raise CadgitError('History record needs attention: '+issues[0]['path']+': '+issues[0]['error'])
        return sorted(records,key=order_key)

    def resolve(self, ref):
        if ref == "main":
            current = self.root / "main/current.json"
            if not current.exists(): raise CadgitError("Main is empty. Save an assembly and select Set main.")
            pointer=read_json(current);check_compatibility(pointer,"Main pointer",legacy=True)
            ref = pointer["assembly_id"]
        records = self.records(strict=False) + self.records("assemblies",strict=False)
        if '~' in ref:
            source,offset=ref.rsplit('~',1)
            try:offset=int(offset)
            except ValueError:raise CadgitError(f'Invalid history offset: {ref}')
            if offset<0:raise CadgitError('History offsets must be nonnegative')
            branch=None
            if '/' in source:source,branch=source.split('/',1)
            branch=branch or read_json(self.root/'cadgit.json').get('active_branches',{}).get(source,'main')
            record=branch_tip(records,source,branch)
            for _ in range(offset):
                if not record:break
                record=next((r for r in records if r['id']==record.get('parent')),None)
            if not record:raise CadgitError(f'No history for {ref}')
            return record
        exact = [r for r in records if r["id"] == ref]
        if len(exact) == 1: return exact[0]
        matches = [r for r in records if r["id"].startswith(ref)]
        if len(matches)!=1:
            issues=[i for group in self.record_issues.copy().values() for i in group]
            detail=('; unreadable records: '+issues[0]['error']) if issues else ''
            raise CadgitError(f'Unknown or ambiguous reference: {ref}'+detail)
        return matches[0]

    def stage_path(self, record):
        base=Path(record['_directory']).resolve();entry=record.get('entry_layer','scene.usda')
        if not isinstance(entry,str) or not entry:raise CadgitError('Invalid record entry_layer')
        relative=Path(entry)
        if relative.is_absolute() or '..' in relative.parts:raise CadgitError('Unsafe record entry_layer: '+entry)
        path=(base/relative).resolve()
        if not path.is_relative_to(base):raise CadgitError('Record entry_layer escapes its archive')
        return path

    def commit(self, staging, destination, record):
        check_compatibility(record,"New record",legacy=True)
        record["files"] = inventory(staging)
        atomic_json(staging / "manifest.json", record)
        (staging / "COMMITTED").write_text(record["id"])
        for path in staging.rglob("*"):
            if path.is_file():
                with path.open("rb") as f: os.fsync(f.fileno())
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging, destination); fsync_dir(destination.parent)
        result={**record,'_directory':str(destination)}
        try:self.event('record_committed',{'id':record['id'],'path':str(destination.relative_to(self.root))})
        except OSError as exc:result['publication_warning']='Record committed; event could not be written: '+str(exc)
        return result

    def ingest(self, filepath, source="manual", label=None, branch=None, metadata=None):
        from pxr import Sdf, Usd, UsdUtils
        from .models import Snapshot
        filepath = Path(filepath).expanduser().resolve()
        if not filepath.is_file(): raise CadgitError(f"Missing USD: {filepath}")
        if not source or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in source):
            raise CadgitError("Source must contain only letters, digits, underscore, or dash")
        timestamp=capture_time((metadata or {}).get('captured_at'))
        with self.lock():
            branch=branch or read_json(self.root/'cadgit.json').get('active_branches',{}).get(source,'main')
            if not branch or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in branch):raise CadgitError('Invalid branch name')
            existing=self.records();capture_id=(metadata or {}).get('capture_id')
            if capture_id:
                repeated=next((r for r in existing if r.get('source')==source and r.get('metadata',{}).get('capture_id')==capture_id),None)
                if repeated:return repeated
            tip=branch_tip(existing,source,branch)
            sid = uid("snap"); staging = self.root / ".cadgit/staging" / sid; staging.mkdir()
            try:
                source_layer = Sdf.Layer.FindOrOpen(str(filepath))
                if not source_layer: raise CadgitError("Unsupported or invalid USD file")
                source_layer.Reload()
                layers, assets, unresolved = UsdUtils.ComputeAllDependencies(Sdf.AssetPath(str(filepath)))
                if unresolved: raise CadgitError(f"Unresolved USD dependencies: {list(unresolved)}")
                ok = UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(filepath)), str(staging / "scene.usdz"))
                if not ok or not Usd.Stage.Open(str(staging / "scene.usdz")): raise CadgitError("USD packaging/validation failed")
                # Sidecars emitted by native hooks, tied to this exact export event.
                meta = dict(metadata or {})
                material_files = sorted(filepath.parent.glob("material_*.blend")) if meta.get("native_capture") else []
                native_materials = {}
                mapping_path = filepath.parent / "materials.json"
                mapping = read_json(mapping_path) if material_files and mapping_path.exists() else {}
                for path in material_files:
                    entry = mapping.get(path.name, path.stem)
                    if isinstance(entry, str): entry = {"name": entry, "images": {}}
                    image_inputs = {name: Path(filename) for name, filename in entry.get("images", {}).items() if Path(filename).is_file()}
                    image_hashes = {name: hashlib.sha256(filename.read_bytes()).hexdigest() for name, filename in image_inputs.items()}
                    digest = hashlib.sha256(path.read_bytes() + json.dumps(image_hashes, sort_keys=True).encode()).hexdigest()
                    mid = "mat_" + digest[:20]
                    material_dir = self.root / "materials" / mid
                    if not material_dir.exists():
                        ms = self.root / ".cadgit/staging" / mid; ms.mkdir(exist_ok=True)
                        shutil.copy2(path, ms / "material.blend")
                        image_map = {}
                        for image_name, filename in image_inputs.items():
                            relative = "images/" + image_hashes[image_name][:16] + filename.suffix
                            target = ms / relative; target.parent.mkdir(exist_ok=True)
                            shutil.copy2(filename, target); image_map[image_name] = relative
                        material_record = {"schema_version": 1, "id": mid, "created_at": now(), "label": entry["name"], "provider": "blender", "snapshot_id": sid, "entry_layer": "material.blend", "images": image_map}
                        self.commit(ms, material_dir, material_record)
                    native_materials[entry["name"]] = mid
                meta["native_materials"] = native_materials
                r = Snapshot(id=sid, source=source, branch=branch, parent=tip["id"] if tip else read_json(self.root / "cadgit.json").get("branches", {}).get(source, {}).get(branch, {}).get("base"), created_at=timestamp, committed_at=now(),commit_sequence=max((r.get("commit_sequence",0) or 0 for r in existing),default=0)+1, label=label or filepath.stem, trigger=meta.pop("trigger", "ingest"), metadata=meta).model_dump()
                from .library import Library,FEATURE
                from pxr import UsdGeom,UsdShade,Tf
                library_bindings=[];native_bindings=[];native_by_prim={};aliases={}
                for name,revision in native_materials.items():aliases.setdefault(Tf.MakeValidIdentifier(name),[]).append(revision)
                captured_stage=Usd.Stage.Open(Usd.Stage.Open(str(staging/'scene.usdz')).Flatten());canonicalized=False
                for prim in captured_stage.Traverse():
                    if not prim.IsA(UsdGeom.Mesh):continue
                    logical=prim.GetAttribute('userProperties:cadgit:library_material_revision').Get()
                    captured_revision=None
                    if native_materials:
                        bound=UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
                        if bound:
                            name=bound.GetPrim().GetName();candidates=aliases.get(name,[])
                            if len(candidates)!=1:raise CadgitError('Cannot map captured native material unambiguously: '+name+'. Capture retained for recovery; material names may collide after USD sanitization.')
                            captured_revision=candidates[0]
                        elif logical:
                            raise CadgitError('Logical material capture has no single bound native material; per-face native graph restoration is unsupported')
                    elif not (meta.get('native_capture') and source=='blender'):
                        captured_revision=prim.GetAttribute('userProperties:cadgit:material_revision').Get()
                        if captured_revision:
                            material=next((m for m in self.records('materials') if m['id']==captured_revision),None)
                            if material is None or not self.verify(material)['ok']:raise CadgitError('Referenced captured shader is missing or corrupt: '+captured_revision)
                    if captured_revision:
                        prim.CreateAttribute('userProperties:cadgit:material_revision',Sdf.ValueTypeNames.String).Set(captured_revision);canonicalized=True
                        native_by_prim[str(prim.GetPath())]=captured_revision
                        native_bindings.append({'prim_path':str(prim.GetPath()),'material_revision':captured_revision})
                    elif meta.get('native_capture') and source=='blender' and prim.HasAttribute('userProperties:cadgit:material_revision'):
                        prim.RemoveProperty('userProperties:cadgit:material_revision');canonicalized=True
                    if logical:
                        Library(self)._require(logical,{'material'})
                        policy=prim.GetAttribute('userProperties:cadgit:library_appearance_source').Get()
                        if policy not in (None,'library','captured_native'):raise CadgitError('Unsupported logical appearance policy: '+str(policy))
                        captured=bool(captured_revision) or (meta.get('native_capture') and source=='blender') or policy=='captured_native'
                        policy='captured_native' if captured else 'library'
                        prim.CreateAttribute('userProperties:cadgit:library_appearance_source',Sdf.ValueTypeNames.String).Set(policy);canonicalized=True
                        library_bindings.append({'prim_path':str(prim.GetPath()),'library_material_revision':logical,'appearance_source':policy})
                if canonicalized:
                    canonical=staging/'canonical.usda';captured_stage.Export(str(canonical))
                    if not UsdUtils.CreateNewUsdzPackage(Sdf.AssetPath(str(canonical)),str(staging/'canonical.usdz')):raise CadgitError('Cannot package canonical material bindings')
                    os.replace(staging/'canonical.usdz',staging/'scene.usdz');canonical.unlink()
                if native_bindings:r['bindings']=native_bindings
                r['metadata']['native_materials_by_prim']=native_by_prim
                if library_bindings:r.update(library_bindings=library_bindings,required_features=[FEATURE])
                dest = self.root / "history/sources" / source / (r["created_at"].replace(":", "-") + "_" + sid)
                return self.commit(staging, dest, r)
            except Exception as e:
                try:self.event("export_failed", {"id": sid, "error": str(e), "staging": str(staging)})
                except OSError:pass
                raise

    def main_scene_bytes(self,record):
        target=os.path.relpath(self.stage_path(record),self.root/'main')
        # The JSON pointer is authoritative; this USD is a recoverable projection.
        return f'#usda 1.0\n( upAxis = "Z"\n metersPerUnit = 1\n defaultPrim = "World"\n subLayers = [@{target}@] )\n'.encode()

    def repair_main(self):
        pointer=self.root/'main/current.json'
        if not pointer.exists():return
        with self.lock():
            current=read_json(pointer);check_compatibility(current,'Main pointer',legacy=True)
            record=self.resolve(current['assembly_id'])
            if not record['id'].startswith('assembly_'):raise CadgitError('Main pointer must identify an assembly')
            if not self.verify(record)['ok']:raise CadgitError('Main assembly failed integrity verification')
            scene=self.root/'main/scene.usda';expected=self.main_scene_bytes(record)
            if not scene.exists() or scene.read_bytes()!=expected:atomic_write(scene,expected)

    def set_main(self,ref):
        record=self.resolve(ref)
        if not record['id'].startswith('assembly_'):raise CadgitError('Main must point to a saved assembly')
        with self.lock():
            if not self.verify(record)['ok']:raise CadgitError('Main assembly failed integrity verification')
            pointer=self.root/'main/current.json';scene=self.root/'main/scene.usda'
            current=read_json(pointer) if pointer.exists() else {};check_compatibility(current,'Main pointer',legacy=True)
            before=scene.read_bytes() if scene.exists() else None
            try:
                atomic_write(scene,self.main_scene_bytes(record))
                atomic_json(pointer,{**current,'assembly_id':record['id'],'selected_at':now()})
            except Exception:
                # If rollback itself fails, the unchanged pointer repairs its USD
                # projection when the project is reopened.
                if before is not None:
                    try:atomic_write(scene,before)
                    except OSError:pass
                raise
            try:self.event('main_selected',{'assembly_id':record['id']})
            except OSError as exc:record={**record,'publication_warning':'Main selected; event could not be written: '+str(exc)}
        return record

    def branch(self, source, name, base=None, activate=False):
        if not name or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in name):
            raise CadgitError("Branch names use letters, digits, dash, underscore")
        with self.lock():
            config = read_json(self.root / "cadgit.json")
            branches = config.setdefault("branches", {}).setdefault(source, {"main": {"base": None}})
            if base:
                resolved = self.resolve(base)
                if resolved.get("source") != source: raise CadgitError("Branch base must be a snapshot of this source")
                if name in branches: raise CadgitError("Branch already exists")
                branches[name] = {"base": resolved["id"]}
            elif name not in branches:
                branches[name] = {"base": None}
            if activate: config.setdefault("active_branches", {})[source] = name
            self.event("branch_selected" if activate else "branch_created", {"source": source, "name": name, "base": branches[name]["base"]})
            atomic_json(self.root / "cadgit.json", config)
            self.config = config
            return {"source": source, "branch": name, "base": branches[name]["base"], "active": activate}

    def name_version(self,ref,name):
        name=name.strip()
        if not name or len(name)>100:raise CadgitError('Version name must have 1–100 characters')
        record=self.resolve(ref)
        with self.lock():
            config=read_json(self.root/'cadgit.json');versions=config.setdefault('versions',{})
            if name in versions:raise CadgitError('Version name already exists; choose a new name')
            versions[name]=record['id']
            self.event('version_named',{'name':name,'snapshot_id':record['id']})
            atomic_json(self.root/'cadgit.json',config);self.config=config
        return {'name':name,'snapshot_id':record['id']}

    def verify(self, ref, _stack=None):
        if isinstance(ref,dict):record=ref
        elif isinstance(ref,str) and ref.startswith('print_'):
            # Export returns an artifact ID, not a scene reference. Keep this
            # exact-ID lookup separate so artifacts never enter scene resolution.
            matches=[r for r in self.records('artifacts/prints',strict=False) if r['id']==ref]
            if len(matches)!=1:raise CadgitError('Unknown or ambiguous print artifact: '+ref)
            record=matches[0];directory=Path(record['_directory'])
            collection=self.root/'artifacts/prints'
            if (self.root/'artifacts').is_symlink() or collection.is_symlink() or directory.is_symlink() or directory.name!=ref or not directory.resolve().is_relative_to(collection.resolve()):
                raise CadgitError('Unsafe print artifact archive: '+ref)
        else:record=self.resolve(ref)
        errors=[];base=Path(record['_directory']).resolve()
        stack=set(_stack or ())
        if record['id'] in stack:return {'id':record['id'],'ok':False,'errors':['Cyclic asset dependency']}
        stack.add(record['id'])
        try:entry=self.stage_path(record).relative_to(base).as_posix()
        except CadgitError as exc:errors.append(str(exc));entry=None
        files=record.get('files')
        if not isinstance(files,list):return {'id':record.get('id'),'ok':False,'errors':['Missing files inventory']}
        listed=set()
        for file in files:
            if not isinstance(file,dict):errors.append('Invalid file inventory entry');continue
            relative=file.get('path','')
            if not isinstance(relative,str):errors.append('Invalid inventory path');continue
            path=(base/relative).resolve()
            if not relative or Path(relative).is_absolute() or '..' in Path(relative).parts or not path.is_relative_to(base):errors.append('Unsafe path: '+relative);continue
            if relative in listed:errors.append('Duplicate inventory path: '+relative)
            listed.add(relative)
            try:
                if not path.is_file() or file_digest(path)!=file.get('sha256'):errors.append('Hash mismatch: '+relative)
            except OSError as exc:errors.append('Cannot read archived payload '+relative+': '+str(exc))
        images=record.get('images',{})
        if not isinstance(images,dict):errors.append('Invalid image inventory mapping')
        else:
            for relative in images.values():
                if not isinstance(relative,str) or Path(relative).is_absolute() or '..' in Path(relative).parts or relative not in listed:errors.append('Image reference is not covered by the archive inventory: '+str(relative))
        if entry and entry not in listed:errors.append('Entry layer is not covered by the files inventory: '+entry)
        marker=base/'COMMITTED'
        try:
            if not marker.is_file() or marker.read_text()!=record['id']:errors.append('Commit marker does not match the record ID')
        except (OSError,UnicodeError):errors.append('Unreadable commit marker')
        try:
            actual={f['path'] for f in inventory(base)}
            if actual!=listed:errors.append('Archive files differ from the committed inventory')
        except (CadgitError,OSError) as exc:errors.append(str(exc))
        bindings=record.get('bindings',[])
        if not isinstance(bindings,list):errors.append('Invalid material bindings');bindings=[]
        revisions={binding['material_revision'] for binding in bindings if isinstance(binding,dict) and isinstance(binding.get('material_revision'),str)}
        native=record.get('metadata',{}).get('native_materials',{})
        if not isinstance(native,dict) or any(not isinstance(value,str) for value in native.values()):errors.append('Invalid native material map')
        else:revisions.update(native.values())
        if revisions:
            materials={material['id']:material for material in self.records('materials',strict=False)}
            for revision in revisions:
                if revision not in materials:errors.append('Missing or incompatible material revision: '+str(revision));continue
                result=self.verify(materials[revision],stack)
                if not result['ok']:errors.append('Material '+str(revision)+': '+'; '.join(result['errors']))
        if record.get('library_bindings'):
            from .library import Library
            library=Library(self)
            for binding in record['library_bindings']:
                result=library.verify(binding['library_material_revision'])
                if not result['ok']:errors.append('Library material: '+'; '.join(result['errors']))
        return {'id':record['id'],'ok':not errors,'errors':errors}
