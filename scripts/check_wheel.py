"""Inspect an installed wheel without resolving Git CAD from the source tree."""
from pathlib import Path
import importlib,sys
from importlib.metadata import distributions

installed=Path(sys.argv[1]).resolve();sys.path.insert(0,str(installed))
import cadgit
assert Path(cadgit.__file__).resolve().is_relative_to(installed),cadgit.__file__
for name in ('cli','store','usd','library','ui_v2','viewport_data','mcp_server'):
    importlib.import_module('cadgit.'+name)
resources=Path(cadgit.__file__).parent/'resources'
for name in ('blender_hook.py','rhino_hook.py','monad_colors.json','MONAD_LICENSE.txt',
             'cad-git.svg','cad-git.png','cad-git.icns','brep_job_readme.txt'):
    assert (resources/name).is_file(),name
installed_distributions=list(distributions(path=[str(installed)]))
project=[distribution for distribution in installed_distributions
         if distribution.metadata['Name']=='git-cad']
assert len(project)==1,'Wheel distribution must be named git-cad'
for command in ('git-cad','cad-git'):
    entries=[entry for distribution in installed_distributions
             for entry in distribution.entry_points
             if entry.group=='console_scripts' and entry.name==command]
    assert len(entries)==1,f'Wheel must declare exactly one {command} console entry point'
    assert entries[0].value=='cadgit.cli:main',entries[0].value
    sys.argv=[command,'--help']
    try:
        entries[0].load()()
    except SystemExit as exc:
        assert exc.code in (None,0),exc.code
