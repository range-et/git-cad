"""The gate runner must not publish false-green evidence or orphan timed-out work."""
import importlib.util,json,os,subprocess,sys,time
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('cadgit_build_checks',Path(__file__).resolve().parents[1]/'scripts/check.py')
checks=importlib.util.module_from_spec(spec);spec.loader.exec_module(checks)


def test_source_drift_invalidates_successful_commands(tmp_path,monkeypatch):
    subprocess.run(['git','init','-q',str(tmp_path)],check=True)
    (tmp_path/'.gitignore').write_text('build/\n')
    (tmp_path/'source.txt').write_text('before')
    subprocess.run(['git','-C',str(tmp_path),'add','.'],check=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','fixture'],check=True)
    monkeypatch.setattr(checks,'ROOT',tmp_path);monkeypatch.setattr(sys,'argv',['check.py'])
    def changed(command,stream,timeout):
        if '-m' in command:(tmp_path/'source.txt').write_text('changed during check')
        return 0
    monkeypatch.setattr(checks,'execute',changed)
    assert checks.main()==1
    report=json.loads(next((tmp_path/'build/qa').glob('*/report.json')).read_text())
    assert report['result']=='failed' and 'Source changed' in report['error']
    assert report['diff_sha256']!=report['final_source_state']['diff_sha256']


@pytest.mark.skipif(os.name!='posix',reason='POSIX process-group cleanup contract')
def test_timeout_stops_descendants(tmp_path):
    marker=tmp_path/'orphan'
    child='import time,pathlib;time.sleep(.6);pathlib.Path('+repr(str(marker))+').write_text("orphan")'
    parent='import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",'+repr(child)+']);time.sleep(10)'
    with (tmp_path/'log').open('w') as log:
        with pytest.raises(subprocess.TimeoutExpired):checks.execute([sys.executable,'-c',parent],log,.2)
    time.sleep(.7)
    assert not marker.exists()
