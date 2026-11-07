from __future__ import annotations
import json, os, sys
from pathlib import Path
from typing import Optional
import typer
from .store import Project, CadgitError, read_json, atomic_json

app=typer.Typer(no_args_is_help=True,help='CAD-GIT • local USD history and deliberate assembly')
assembly_app=typer.Typer();app.add_typer(assembly_app,name='assembly')
main_app=typer.Typer();app.add_typer(main_app,name='main')
material_app=typer.Typer();app.add_typer(material_app,name='material')
branch_app=typer.Typer();app.add_typer(branch_app,name='branch')
from .library_cli import app as library_app
app.add_typer(library_app,name='library')

def emit(value):typer.echo(json.dumps(value,indent=2,default=str))

def project(ctx):return Project(ctx.obj['root'])

@app.callback()
def options(ctx:typer.Context,project_path:Path=typer.Option(Path('.'),'--project','-p',help='Project folder')):
    ctx.obj={'root':project_path.resolve()}

@app.command()
def init(path:Path=typer.Argument(Path('.')),name:Optional[str]=None):
    p=Project.init(path,name);emit({'project':str(p.root),'name':p.config['name']})

@app.command()
def demo(path:Path=typer.Argument(Path('demo-project'))):
    """Create a clearly labelled engine sample with five source snapshots."""
    from .demo import create
    p=create(path);emit({'project':str(p.root),'snapshots':len(p.records()),'sample_data':True})

@app.command()
def ingest(ctx:typer.Context,path:Path,source:str='manual',label:Optional[str]=None,branch:Optional[str]=None):
    emit(project(ctx).ingest(path,source,label,branch))

@app.command('log')
def history(ctx:typer.Context,source:Optional[str]=None):
    records=project(ctx).records()
    emit([r for r in records if source is None or r['source']==source])

@app.command()
def status(ctx:typer.Context):
    from .service import status as service_status
    p=project(ctx)
    current=p.root/'main/current.json'
    emit({'project':str(p.root),'snapshots':len(p.records()),'assemblies':len(p.records('assemblies')),'materials':len(p.records('materials')),'main':read_json(current) if current.exists() else None,'service':service_status(p),'capture_errors':[str(x) for x in (p.root/'.cadgit/inbox').glob('*/error.json')]+[str(x) for x in (p.root/'.cadgit/inbox').glob('*/failed.json')]})

@app.command()
def begin(ctx:typer.Context,rhino_endpoint:Optional[str]=None):
    """Start background ingestion and attach native save hooks to open apps."""
    from .connectors import attach
    from .service import start
    p=project(ctx);result={}
    for name in ['rhino','blender']:
        try:attach(p,name,rhino_endpoint);result[name]='save hook attached'
        except Exception as e:result[name]=str(e)
    result['service']=start(p);emit(result)

@app.command()
def stop(ctx:typer.Context):
    from .service import stop as stop_service
    from .connectors import detach
    p=project(ctx);r={}
    for name in ['rhino','blender']:
        try:detach(p,name);r[name]='detached'
        except Exception as e:r[name]=str(e)
    r['service']=stop_service(p);emit(r)

@app.command()
def snapshot(ctx:typer.Context,source:str=typer.Option(...)):
    from .connectors import capture
    from .service import process_inbox
    p=project(ctx);capture(p,source);emit({'snapshots_committed':process_inbox(p)})

@app.command()
def ui(ctx:typer.Context,screenshot:Optional[Path]=None):
    from .ui_v2 import launch
    raise typer.Exit(launch(project(ctx).root,str(screenshot) if screenshot else None))

@app.command()
def view(ctx:typer.Context,ref:str):
    # UI initially opens main; select a ref through a transient launch hint.
    p=project(ctx);r=p.resolve(ref)
    from .ui_v2 import launch
    os.environ['CADGIT_INITIAL_REF']=r['id'];raise typer.Exit(launch(p.root))

@app.command()
def compose(ctx:typer.Context,inputs:list[str]=typer.Option(...,'--input'),name:str='New assembly',library_material:Optional[str]=None):
    from .usd import assemble
    selections=[]
    for value in inputs:
        if ':/' not in value:raise typer.BadParameter('Use SNAPSHOT:/Prim/Path')
        ref,prim=value.split(':',1)
        selections.append({'snapshot_id':project(ctx).resolve(ref)['id'],'prim_path':prim,'label':prim.split('/')[-1],'library_material_revision':library_material})
    emit(assemble(project(ctx),selections,name))

@assembly_app.command('list')
def assemblies(ctx:typer.Context):emit(project(ctx).records('assemblies'))

@main_app.command('set')
def main_set(ctx:typer.Context,ref:str):emit(project(ctx).set_main(ref))

@app.command('export')
def export(ctx:typer.Context,ref:str,output:Path=typer.Option(...),format:str='stl',select:Optional[str]=None,units:str='mm',allow_issues:bool=False,allow_base_mesh:bool=False):
    p=project(ctx)
    if format=='stl':
        from .usd import export_stl
        emit(export_stl(p,ref,output,select,units,allow_issues,allow_base_mesh))
    elif format in ['usd','usda','usdc','usdz']:
        if select:raise CadgitError('Save the selected subtree as an assembly before USD export')
        from .usd import export_usd
        emit(export_usd(p,ref,output))
    else:raise CadgitError('Supported formats: stl, usd, usda, usdc, usdz')

@app.command('import')
def import_native(ctx:typer.Context,ref:str,output:Path=typer.Option(...,'--output'),app_name:str=typer.Option('blender','--app'),launch:bool=typer.Option(True,'--launch/--no-launch')):
    from .handoff import create_native,targets
    p=project(ctx)
    target=next((t for t in targets(p) if t['kind']==app_name),None)
    if not target:raise CadgitError('Configure an application target first')
    emit(create_native(p,ref,target,output,launch))

@app.command()
def verify(ctx:typer.Context,ref:str):
    result=project(ctx).verify(ref);emit(result)
    if not result['ok']:raise typer.Exit(5)

@app.command()
def show(ctx:typer.Context,ref:str):emit(project(ctx).resolve(ref))

@material_app.command('list')
def materials(ctx:typer.Context):emit(project(ctx).records('materials'))

@app.command()
def doctor(ctx:typer.Context):
    import importlib.metadata as m
    p=project(ctx)
    result={'python':sys.version,'project':str(p.root),'packages':{}}
    for name in ['usd-core','PySide6','pyvista','pyvistaqt']:
        try:result['packages'][name]=m.version(name)
        except m.PackageNotFoundError:result['packages'][name]='missing'
    from .connectors import rhino_endpoint,blender_rpc
    try:result['rhino']=rhino_endpoint()
    except Exception as e:result['rhino']=str(e)
    try:result['blender']=blender_rpc("import bpy\nprint(bpy.app.version_string)")
    except Exception as e:result['blender']=str(e)
    result['limitations']=['Static polygon-mesh display/export; base-mesh subdivision requires acknowledgement','No per-face native material restoration yet','Save hooks last for the current app session; reconnect after app restart','Generalized third-party executable plugin loading is not implemented; reference adapters are bundled']
    emit(result)

@branch_app.command('create')
def branch_create(ctx:typer.Context,name:str,source:str=typer.Option(...),base:Optional[str]=typer.Option(None,'--from')):
    emit(project(ctx).branch(source,name,base))

@branch_app.command('use')
def branch_use(ctx:typer.Context,name:str,source:str=typer.Option(...)):
    emit(project(ctx).branch(source,name,activate=True))

@app.command()
def autosnapshot(ctx:typer.Context,mode:str,interval:int=300):
    if mode not in ['on','off'] or interval<30:raise CadgitError('Use on/off with an interval of at least 30 seconds')
    p=project(ctx)
    with p.lock():
        config=read_json(p.root/'cadgit.json');config['tool_interval_seconds']=interval if mode=='on' else None
        p.event('autosnapshot_configured',{'interval':config['tool_interval_seconds']});atomic_json(p.root/'cadgit.json',config)
    emit({'interval':config['tool_interval_seconds'],'requires_service':'Run begin to monitor apps'})

@app.command('mcp')
def mcp_server(ctx:typer.Context):
    from .mcp_server import run
    run(project(ctx))

# Keep CLI errors concise without masking native tracebacks in tests/imports.
def main():
    try:app()
    except CadgitError as exc:
        typer.echo(f'CAD-GIT: {exc}',err=True);raise SystemExit(1)

if __name__=='__main__':main()
