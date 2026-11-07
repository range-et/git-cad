"""Agent-independent operations for the project Materials & Assets workspace."""
from pathlib import Path
from typing import Optional
import json,typer
from .library import Library
from .store import Project,read_json

app=typer.Typer(help='Versioned project materials, images, graphs and documents')

def library(ctx):return Library(Project(ctx.obj['root']))
def emit(value):typer.echo(json.dumps(value,indent=2,default=str))

@app.command('list')
def listing(ctx:typer.Context,kind:Optional[str]=None,query:str=''):emit(library(ctx).summaries(kind,query))

@app.command()
def show(ctx:typer.Context,revision:str):emit(library(ctx).get(revision))

@app.command()
def history(ctx:typer.Context,asset_id:str):emit(library(ctx).history(asset_id))

@app.command()
def verify(ctx:typer.Context,revision:str):
    result=library(ctx).verify(revision);emit(result)
    if not result['ok']:raise typer.Exit(5)

@app.command('import')
def importing(ctx:typer.Context,file:Path,label:Optional[str]=None,kind:Optional[str]=None,asset_id:Optional[str]=None,previous:Optional[str]=typer.Option(None,'--from'),parent:list[str]=typer.Option([],'--parent'),source_url:Optional[str]=None,provider:Optional[str]=None,license_name:Optional[str]=None,note:str=''):
    provenance={}
    if provider is not None:provenance['provider']=provider
    if source_url is not None:provenance['source_url']=source_url
    if license_name is not None:provenance['license']={'name':license_name}
    emit(library(ctx).import_asset(file,label,kind,asset_id,previous,parents=[{'revision_id':ref,'role':'derived_from'} for ref in parent],provenance=provenance or None,note=note))

@app.command('material')
def material(ctx:typer.Context,label:str,definition:Optional[Path]=None,asset_id:Optional[str]=None,previous:Optional[str]=typer.Option(None,'--from'),note:str=''):
    emit(library(ctx).create_material(label,read_json(definition) if definition else None,asset_id,previous,note=note))

@app.command()
def recombine(ctx:typer.Context,label:str,physical_from:str=typer.Option(...),appearance_from:str=typer.Option(...),note:str=''):
    emit(library(ctx).recombine(label,physical_from,appearance_from,note))

@app.command('used-by')
def used_by(ctx:typer.Context,revision:str):emit(library(ctx).used_by(revision))

@app.command('export')
def exporting(ctx:typer.Context,revision:str,output:Path=typer.Option(...)):emit({'output':library(ctx).export(revision,output),'revision':revision})
