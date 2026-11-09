"""Exercise the installed CLI against an unrelated, existing repository folder."""
import tempfile,subprocess,json,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[2];sys.path.insert(0,str(repo/'tests'))
from test_history import box
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);project=root/'other-repo';project.mkdir();(project/'existing.txt').write_text('keep me')
    def run(*args):
        result=subprocess.run([sys.executable,'-m','cadgit.cli',*map(str,args)],capture_output=True,text=True,check=True)
        return json.loads(result.stdout)
    run('init',project);source=box(root/'part.usda',.001)
    snap=run('-p',project,'ingest',source,'--source','rhino')
    assembly=run('-p',project,'compose','--input',snap['id']+':/World/Part','--name','CLI assembly')
    run('-p',project,'main','set',assembly['id'])
    run('-p',project,'export','main','--output',root/'print.stl')
    run('-p',project,'export','main','--format','usdz','--output',root/'assembly.usdz')
    run('-p',project,'import','main','--app','rhino','--output',root/'new.3dm','--no-launch')
    assert run('-p',project,'verify','main')['ok']
    assert (project/'existing.txt').read_text()=='keep me'
    assert (root/'new.3dm.cadgit.json').exists()
    print('CLI_OTHER_REPOSITORY_VERIFIED: init, ingest, compose, main, STL/USD export, new Rhino file, lineage, verification')
