"""Optional B-rep reconstruction preparation and external-runtime diagnostics."""
from pathlib import Path
from typing import Optional
import json,typer
from .store import Project
from .brep import prepare_job,list_jobs,get_job,verify_job,runtime_status

app=typer.Typer(help='Prepare optional DualBrep jobs; inference/STEP generation is not enabled yet')
def emit(value):typer.echo(json.dumps(value,indent=2,default=str))
def project(ctx):return Project(ctx.obj['root'])

@app.command('prepare')
def prepare(ctx:typer.Context,ref:str,select:list[str]=typer.Option([],'--select'),split_components:bool=False,allow_base_mesh:bool=False):
    """Archive per-part PLY inputs and lineage from a saved version. No inference."""
    emit(prepare_job(project(ctx),ref,select,split_components,allow_base_mesh))

@app.command('list')
def listing(ctx:typer.Context):emit(list_jobs(project(ctx)))

@app.command('show')
def show(ctx:typer.Context,job:str):emit(get_job(project(ctx),job))

@app.command('verify')
def verify(ctx:typer.Context,job:str):
    result=verify_job(project(ctx),job);emit(result)
    if not result['ok']:raise typer.Exit(5)

@app.command('doctor')
def doctor(python:Optional[Path]=None,checkout:Optional[Path]=None):
    """Check an external CUDA environment; readiness is not completed inference."""
    emit(runtime_status(python,checkout))
