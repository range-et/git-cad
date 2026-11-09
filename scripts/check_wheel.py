"""Inspect an installed wheel without resolving CAD-GIT from the source tree."""
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
sys.argv=['cad-git','--help']
entries=[entry for distribution in distributions(path=[str(installed)])
         for entry in distribution.entry_points
         if entry.group=='console_scripts' and entry.name=='cad-git']
assert len(entries)==1,'Wheel must declare exactly one cad-git console entry point'
entries[0].load()()
