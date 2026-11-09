"""Project-local immutable materials, images, native graphs and documents."""
from __future__ import annotations
import copy,json,mimetypes,shutil
from pathlib import Path
from urllib.parse import urlparse
from .models import AssetRevision,RevisionLink
from .store import CadgitError,atomic_json,read_json,uid,now,publish_file,order_key
from .compatibility import check_compatibility

FEATURE='cadgit.material-library.v1'
KINDS={'material','image','document','shader','texture_set','other'}


def infer_kind(path):
    suffix=Path(path).suffix.lower()
    if suffix in {'.png','.jpg','.jpeg','.tif','.tiff','.bmp','.webp','.exr','.hdr'}:return 'image'
    if suffix in {'.blend','.mtlx','.sbsar'}:return 'shader'
    if suffix in {'.pdf','.txt','.md','.csv','.json','.html'}:return 'document'
    return 'other'


def reference(value):
    if isinstance(value,str):return value
    if isinstance(value,dict) and isinstance(value.get('revision_id'),str):return value['revision_id']
    raise CadgitError('Asset reference must contain an exact revision_id')


def web_url(value):
    if not isinstance(value,str):return False
    try:parsed=urlparse(value)
    except ValueError:return False
    return parsed.scheme in {'http','https'} and bool(parsed.netloc)


class Library:
    def __init__(self,project):
        self.project=project;self.root=project.root/'library';self.issues=[]
    def _ownership(self,write=False):
        marker=self.root/'library.json'
        for path in [self.root,marker,self.root/'revisions']:
            if path.is_symlink():raise CadgitError('Library storage cannot use symlinks: '+str(path))
        if not self.root.resolve().is_relative_to(self.project.root.resolve()):raise CadgitError('Library storage escapes the project')
        if marker.exists():
            data=read_json(marker);check_compatibility(data,'Asset library')
            if data.get('project_id')!=self.project.config['id']:raise CadgitError('Asset library belongs to a different project')
        elif self.root.exists() and any(self.root.iterdir()):raise CadgitError('Existing library/ is not a Git CAD library; its files were not changed')
        elif write:
            self.root.mkdir(parents=True,exist_ok=True)
            atomic_json(marker,{'schema_version':1,'project_id':self.project.config['id'],'kind':'asset_library'},replace=False)
        if write:(self.root/'revisions').mkdir(exist_ok=True)
    def records(self,strict=False):
        records=[];self.issues=[]
        try:self._ownership()
        except CadgitError as exc:
            if strict:raise
            self.issues.append(str(exc));return []
        for file in (self.root/'revisions').glob('*/manifest.json'):
            if not (file.parent/'COMMITTED').exists():continue
            try:
                if file.is_symlink() or file.parent.is_symlink() or not file.resolve().is_relative_to(self.root.resolve()):raise CadgitError('Revision path escapes library storage')
                data=read_json(file);check_compatibility(data,str(file))
                AssetRevision.model_validate(data)
                if file.parent.name!=data['id']:raise CadgitError('Revision directory does not match its ID')
                records.append({**data,'_directory':str(file.parent)})
            except (CadgitError,ValueError) as exc:
                if strict:raise CadgitError(str(exc)) from exc
                self.issues.append(str(file)+': '+str(exc))
        return sorted(records,key=lambda r:(r['revision_number'],r['created_at'],r['id']))
    def legacy(self):
        result=[]
        for record in self.project.records('materials',strict=False):
            result.append({**record,'created_at':record.get('created_at',''),'asset_id':'legacy:'+record['id'],'kind':'shader','revision_number':1,'legacy':True,'parents':[],'dependencies':[],'definition':{},'provenance':{'provider':record.get('provider','blender'),'license':{'name':'unknown'}},'tags':['captured','legacy']})
        return result
    def get(self,revision):
        matches=[record for record in self.records()+self.legacy() if record['id']==revision]
        if len(matches)==1:return matches[0]
        raise CadgitError('Unknown, ambiguous or unreadable library revision: '+str(revision))
    def history(self,asset_id):
        return [r for r in self.records()+self.legacy() if r['asset_id']==asset_id]
    def summaries(self,kind=None,query='',records=None):
        grouped={}
        for record in (records if records is not None else self.records()+self.legacy()):grouped.setdefault(record['asset_id'],[]).append(record)
        result=[]
        for identity,history in grouped.items():
            previous={p.get('revision_id') for r in history for p in r.get('parents',[]) if p.get('role')=='previous'}
            heads=[r for r in history if r['id'] not in previous]
            head=max(heads or history,key=lambda r:(r['revision_number'],r['id']))
            if kind and head['kind']!=kind:continue
            text=' '.join([head['label'],head['kind'],*head.get('tags',[]),str(head.get('provenance',{}))]).lower()
            if query.lower() not in text:continue
            result.append({'asset_id':identity,'label':head['label'],'kind':head['kind'],'head':head['id'],'heads':[r['id'] for r in heads],'revision_count':len(history),'legacy':head.get('legacy',False)})
        return sorted(result,key=lambda r:(r['label'].lower(),r['asset_id']))
    def verify(self,revision,stack=None):
        try:record=self.get(revision)
        except CadgitError as exc:return {'id':revision,'ok':False,'errors':[str(exc)]}
        from .verification import verify_dependencies
        return verify_dependencies(self.project,record,library=True,ancestors=stack)
    def _verify_local(self,record):
        errors=[]
        if not record.get('legacy') and record.get('entry_layer')=='definition.json':
            try:
                if read_json(self.project.stage_path(record))!=record.get('definition',{}):errors.append('Definition differs from its hashed payload')
            except CadgitError as exc:errors.append(str(exc))
        links=[('library',dependency['revision_id'],dependency['role']) for dependency in [*record.get('parents',[]),*record.get('dependencies',[])]]
        return errors,links
    def _require(self,revision,kinds=None):
        record=self.get(revision)
        if kinds and record['kind'] not in kinds:raise CadgitError('Wrong asset kind for reference '+revision)
        result=self.verify(revision)
        if not result['ok']:raise CadgitError('Asset integrity failed: '+'; '.join(result['errors']))
        return record
    def _base(self,asset_id,expected_revision,kind):
        if not asset_id:
            if expected_revision:raise CadgitError('An existing asset_id is required for a new revision')
            return None
        history=[r for r in self.records(strict=True) if r['asset_id']==asset_id]
        if not history:raise CadgitError('Unknown managed asset identity; derive captured assets into a new library identity')
        parents={p['revision_id'] for r in history for p in r.get('parents',[]) if p.get('role')=='previous'}
        heads=[r for r in history if r['id'] not in parents]
        if len(heads)!=1:raise CadgitError('Asset has divergent heads; derive a new identity from an explicit revision')
        if heads[0]['id']!=expected_revision:raise CadgitError('Asset changed or historical revision selected; reload its current revision or derive a new asset')
        if heads[0]['kind']!=kind:raise CadgitError('An asset identity cannot change kind')
        return self._require(expected_revision)
    def _provenance(self,base,value):
        result=copy.deepcopy(base.get('provenance',{}) if base else {})
        if not isinstance(result,dict) or (value is not None and not isinstance(value,dict)):
            raise CadgitError('Asset provenance must be an object')
        for provenance in [result,value or {}]:
            if 'license' in provenance and not isinstance(provenance['license'],dict):
                raise CadgitError('Asset license must be an object with name and optional URL fields')
        if value is not None:
            for key,item in value.items():
                if key=='license' and isinstance(item,dict):result[key]={**result.get(key,{}),**item}
                else:result[key]=item
        result.setdefault('license',{'name':'unknown'})
        for url in [result.get('source_url',''),result.get('license',{}).get('url','')]:
            if url and not web_url(url):raise CadgitError('Source/license URLs must be http or https')
        return result
    def _write(self,kind,label,definition=None,file=None,asset_id=None,expected_revision=None,parents=None,dependencies=None,provenance=None,tags=None,note=''):
        with self.project.lock():
            self._ownership(write=True);base=self._base(asset_id,expected_revision,kind)
            identity=asset_id or uid('asset');revision=uid('assetrev')
            links=copy.deepcopy(parents or [])
            if base:links.insert(0,{'revision_id':base['id'],'role':'previous'})
            for link in [*links,*(dependencies or [])]:
                try:RevisionLink.model_validate(link)
                except ValueError as exc:raise CadgitError('Invalid revision relationship: '+str(exc)) from exc
                self._require(link['revision_id'])
                if link['role']=='previous' and (not base or link['revision_id']!=base['id']):raise CadgitError('Previous links are reserved for the selected current revision')
            record={k:copy.deepcopy(v) for k,v in (base or {}).items() if not k.startswith('_')}
            record.update(schema_version=1,required_features=list(dict.fromkeys([*(base or {}).get('required_features',[]),FEATURE])),id=revision,asset_id=identity,kind=kind,revision_number=(base['revision_number']+1 if base else 1),label=label or (base or {}).get('label') or 'Untitled asset',created_at=now(),parents=links,dependencies=copy.deepcopy(dependencies or []),provenance=self._provenance(base,provenance),definition=copy.deepcopy(definition if definition is not None else (base or {}).get('definition',{})),tags=copy.deepcopy(tags if tags is not None else (base or {}).get('tags',[])),change_note=note)
            staging=self.project.root/'.cadgit/staging'/revision;staging.mkdir()
            try:
                if file:
                    source=Path(file).expanduser().resolve()
                    if not source.is_file():raise CadgitError('Missing asset file: '+str(source))
                    target=staging/'payload'/source.name;target.parent.mkdir();shutil.copy2(source,target)
                    record['entry_layer']=str(target.relative_to(staging));record['provenance']['import_path']=str(source)
                else:
                    record['entry_layer']='definition.json';atomic_json(staging/'definition.json',record['definition'])
                try:
                    json.dumps(record,allow_nan=False);AssetRevision.model_validate(record)
                except (TypeError,ValueError) as exc:raise CadgitError('Invalid asset revision: '+str(exc)) from exc
                return self.project.commit(staging,self.root/'revisions'/revision,record)
            finally:
                # Library imports are copies of user-owned files. Failed attempts
                # can discard their partial copy; native capture recovery is separate.
                if staging.exists():shutil.rmtree(staging)
    def import_asset(self,file,label=None,kind=None,asset_id=None,expected_revision=None,parents=None,provenance=None,tags=None,note=''):
        file=Path(file).expanduser().resolve();kind=kind or infer_kind(file)
        if kind not in KINDS-{'material','texture_set'}:raise CadgitError('Import files as image, document, shader or other')
        return self._write(kind,label or file.stem,file=file,asset_id=asset_id,expected_revision=expected_revision,parents=parents,provenance=provenance,tags=tags,note=note)
    def _material_dependencies(self,definition):
        if not isinstance(definition,dict):raise CadgitError('Material definition must be an object')
        physical=definition.get('physical',{})
        if not isinstance(physical,dict):raise CadgitError('Physical data must be an object')
        properties=physical.get('properties',{})
        if not isinstance(properties,dict):raise CadgitError('Physical properties must be a mapping')
        dependencies=[]
        for key,value in properties.items():
            if not isinstance(value,dict):raise CadgitError('Each physical property needs value, unit and source/status fields')
            if value.get('value') is not None and not isinstance(value.get('unit'),str):raise CadgitError('Property '+key+' requires a unit')
            if value.get('value') is not None and not value.get('unit','').strip():raise CadgitError('Property '+key+' requires a unit (use 1 for dimensionless quantities)')
            if key.lower() in {'density','mass_density','youngs_modulus','elastic_modulus','tensile_strength','yield_strength','thermal_conductivity','specific_heat','heat_capacity'} and value.get('value') is not None:
                if type(value['value']) not in (int,float) or value['value']<=0:raise CadgitError('Physical property '+key+' must be a positive numeric value')
            value.setdefault('status','unverified')
            if value.get('source_asset_revision'):dependencies.append({'revision_id':reference(value['source_asset_revision']),'role':'physical:'+key})
        appearance=definition.get('appearance',{})
        if not isinstance(appearance,dict):raise CadgitError('Appearance must be an object')
        preview=appearance.get('preview',{})
        if not isinstance(preview,dict):raise CadgitError('Preview must be an object')
        for field in ['maps','graph_images']:
            if not isinstance(appearance.get(field,{}),dict):raise CadgitError(field+' must be an object')
        if not isinstance(definition.get('documents',[]),list):raise CadgitError('Documents must be a list of revision references')
        if 'base_color' in preview:
            color=preview['base_color']
            if not isinstance(color,list) or len(color)!=3 or any(type(v) not in (float,int) or not 0<=v<=1 for v in color):raise CadgitError('Preview base_color must have three values from 0 to 1')
        for key in ['metallic','roughness','opacity']:
            if key in preview and (type(preview[key]) not in (float,int) or not 0<=preview[key]<=1):raise CadgitError('Preview '+key+' must be from 0 to 1')
        if appearance.get('native_graph'):
            ref=reference(appearance['native_graph']);self._require(ref,{'shader'});dependencies.append({'revision_id':ref,'role':'native_graph'})
        for role,value in appearance.get('maps',{}).items():
            if not role.strip():raise CadgitError('Image map roles cannot be empty')
            if isinstance(value,dict):
                for field in ['color_space','uv_set']:
                    if field in value and (not isinstance(value[field],str) or not value[field].strip()):raise CadgitError(field+' must be a nonempty string')
            ref=reference(value);self._require(ref,{'image'});dependencies.append({'revision_id':ref,'role':'map:'+role})
        for name,ref in appearance.get('graph_images',{}).items():
            if not name.strip():raise CadgitError('Native graph image bindings require an image name')
            ref=reference(ref);self._require(ref,{'image'});dependencies.append({'revision_id':ref,'role':'graph_image:'+name})
        for ref in definition.get('documents',[]):dependencies.append({'revision_id':reference(ref),'role':'document'})
        return dependencies
    def create_material(self,label,definition=None,asset_id=None,expected_revision=None,parents=None,provenance=None,tags=None,note=''):
        # Full definition is supplied by editors after cloning the selected revision,
        # so intentionally removed properties disappear while unknown fields survive.
        if definition is None:
            if asset_id:
                if not expected_revision:raise CadgitError('Expected revision is required when revising a material')
                definition=self.get(expected_revision)['definition']
            else:definition={'physical':{'properties':{}},'appearance':{},'documents':[]}
        definition=copy.deepcopy(definition)
        try:json.dumps(definition,allow_nan=False)
        except (ValueError,TypeError) as exc:raise CadgitError('Material properties must be finite JSON values') from exc
        dependencies=self._material_dependencies(definition)
        return self._write('material',label,definition,asset_id=asset_id,expected_revision=expected_revision,parents=parents,dependencies=dependencies,provenance=provenance,tags=tags,note=note)
    def recombine(self,label,physical_from,appearance_from,note='',provenance=None):
        physical=self._require(physical_from,{'material'});appearance=self._require(appearance_from,{'material'})
        definition=copy.deepcopy(physical['definition']);definition['appearance']=copy.deepcopy(appearance['definition'].get('appearance',{}))
        docs=[*physical['definition'].get('documents',[]),*appearance['definition'].get('documents',[])]
        definition['documents']=list(dict.fromkeys(reference(ref) for ref in docs))
        return self.create_material(label,definition,parents=[{'revision_id':physical_from,'role':'physical_from'},{'revision_id':appearance_from,'role':'appearance_from'}],provenance=provenance,note=note)
    def used_by(self,revision):
        result=[]
        for record in self.records():
            for link in [*record.get('dependencies',[]),*record.get('parents',[])]:
                if link['revision_id']==revision:result.append({'id':record['id'],'label':record['label'],'kind':record['kind'],'role':link['role']})
        for record in self.project.records('assemblies',strict=False)+self.project.records(strict=False):
            for binding in record.get('library_bindings',[]):
                if binding.get('library_material_revision')==revision:result.append({'id':record['id'],'label':record['label'],'kind':'snapshot' if record.get('source') else 'assembly','role':binding['prim_path']+(' (captured appearance)' if binding.get('appearance_source')=='captured_native' else '')})
        return result
    def export(self,revision,output):
        record=self._require(revision);return str(publish_file(self.project.stage_path(record),output))
    def native_shader(self,material_revision):
        material=self._require(material_revision,{'material'});appearance=material['definition'].get('appearance',{})
        if not appearance.get('native_graph'):return None
        graph=self._require(reference(appearance['native_graph']),{'shader'})
        path=self.project.stage_path(graph)
        if path.suffix.lower()!='.blend':raise CadgitError('Native appearance is archived but Blender restoration requires a .blend graph')
        images={}
        if graph.get('legacy'):
            images={key:str(Path(graph['_directory'])/value) for key,value in graph.get('images',{}).items()}
        for name,value in images.items():
            image_path=Path(value).resolve()
            if not image_path.is_relative_to(Path(graph['_directory']).resolve()):raise CadgitError('Captured image path escapes its archive')
            if str(image_path.relative_to(Path(graph['_directory']).resolve())) not in {f['path'] for f in graph['files']}:raise CadgitError('Captured image is not covered by its inventory')
        for name,ref in appearance.get('graph_images',{}).items():images[name]=str(self.project.stage_path(self._require(reference(ref),{'image'})))
        return {'path':str(path),'material_name':appearance.get('material_name') or None,'images':images,'label':material['label']}
