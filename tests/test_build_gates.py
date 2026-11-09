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


def test_success_banner_before_native_abort_does_not_pass_gate(tmp_path,monkeypatch):
    """A Qt teardown abort after scenario assertions is still a failed process."""
    monkeypatch.setattr(checks,'ROOT',tmp_path)
    monkeypatch.setattr(checks,'source_state',lambda: {'git_head':'fixture','git_status':'','diff_sha256':'fixture'})
    monkeypatch.setattr(sys,'argv',['check.py','--ui','--mcp'])
    def abort_after_banner(command,stream,timeout):
        if command[-1].endswith('dialog_workflows.py'):
            stream.write('DIALOG_WORKFLOWS_VERIFIED: 46 cases\n')
            return -6
        return 0
    monkeypatch.setattr(checks,'execute',abort_after_banner)
    assert checks.main()==1
    report=json.loads(next((tmp_path/'build/qa').glob('*/report.json')).read_text())
    assert report['result']=='failed'
    assert report['checks'][-1]['name']=='dialog_workflows'
    assert report['checks'][-1]['exit_code']==-6
    assert report['pending_checks']==['legacy_workflows','mcp_workflow_smoke']


def test_all_requested_gate_commands_are_reported_and_no_checks_remain_pending(tmp_path,monkeypatch):
    monkeypatch.setattr(checks,'ROOT',tmp_path)
    monkeypatch.setattr(checks,'source_state',lambda:{'git_head':'fixture','git_status':'','diff_sha256':'fixture'})
    monkeypatch.setattr(sys,'argv',['check.py','--build','--ui','--mcp','--mutation'])
    commands=[]
    def passed(command,stream,timeout):
        commands.append(command)
        if command[:2]==['uv','build']:
            dist=Path(command[-1]);dist.mkdir();(dist/'fixture.whl').write_bytes(b'gate orchestration fixture, not a wheel qualification')
        return 0
    monkeypatch.setattr(checks,'execute',passed)
    assert checks.main()==0
    report=json.loads(next((tmp_path/'build/qa').glob('*/report.json')).read_text())
    assert report['pending_checks']==[]
    assert [item['name'] for item in report['checks']]==report['planned_checks']
    assert {'build','wheel-install','wheel-smoke','mutation','mcp_workflow_smoke'}.issubset(item['name'] for item in report['checks'])
    assert any(command[:3]==['uv','pip','install'] for command in commands)


@pytest.mark.parametrize('failure',[subprocess.TimeoutExpired('fixture',1),KeyboardInterrupt()])
def test_timeout_or_interrupt_keeps_remaining_gates_pending(tmp_path,monkeypatch,failure):
    monkeypatch.setattr(checks,'ROOT',tmp_path)
    monkeypatch.setattr(checks,'source_state',lambda:{'git_head':'fixture','git_status':'','diff_sha256':'fixture'})
    monkeypatch.setattr(sys,'argv',['check.py','--build'])
    def failed(command,stream,timeout):raise failure
    monkeypatch.setattr(checks,'execute',failed)
    assert checks.main()==1
    report=json.loads(next((tmp_path/'build/qa').glob('*/report.json')).read_text())
    assert report['result']==('interrupted' if isinstance(failure,KeyboardInterrupt) else 'failed')
    assert 'core' in report['pending_checks'] and 'wheel-smoke' in report['pending_checks']
