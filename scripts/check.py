"""Run repeatable CAD-GIT gates and retain scoped machine-readable evidence."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,platform,signal,subprocess,sys,tempfile,time

ROOT=Path(__file__).resolve().parents[1]
UI_SUITES=('ui_smoke','ui_robustness','material_library_smoke','texture_preview_smoke','viewport_responsiveness','brep_preparation_smoke','workflow_combinations','dialog_workflows')


def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)


def source_state():
    digest=hashlib.sha256(git('diff','HEAD','--binary'))
    for name in sorted(filter(None,git('ls-files','--others','--exclude-standard','-z').decode().split('\0'))):
        digest.update(name.encode()+b'\0');digest.update((ROOT/name).read_bytes())
    return {'git_head':git('rev-parse','HEAD').decode().strip(),
            'git_status':git('status','--short').decode(),'diff_sha256':digest.hexdigest()}


def execute(command,stream,timeout):
    """Timeout/cancellation must stop subprocesses spawned by the check too."""
    process=subprocess.Popen(command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                             start_new_session=os.name=='posix')
    try:return process.wait(timeout=timeout)
    except (subprocess.TimeoutExpired,KeyboardInterrupt):
        try:
            if os.name=='posix':os.killpg(process.pid,signal.SIGKILL)
            else:process.kill()
        except ProcessLookupError:pass
        process.wait()
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ui',action='store_true',help='Run actual Qt/VTK workflow gates (requires a desktop session)')
    parser.add_argument('--build',action='store_true',help='Build distributions and smoke-test the installed wheel')
    parser.add_argument('--mcp',action='store_true',help='Run the real stdio MCP workflow (requires the mcp extra)')
    args=parser.parse_args()
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    output=ROOT/'build/qa'/stamp;output.mkdir(parents=True)
    initial=source_state();planned=['diff','core','cli']
    if args.build:planned+=['build','wheel-install','wheel-smoke']
    if args.ui:planned+=list(UI_SUITES)
    if args.mcp:planned+=['mcp_workflow_smoke']
    report={'started_at':stamp,**initial,'planned_checks':planned,
            'python':sys.version,'platform':platform.platform(),'checks':[],'result':'running',
            'not_run':['Independent architecture/UX/QA review (record separately)',
                       'Live native-application roundtrips']}
    if not args.mcp:report['not_run'].append('MCP protocol smoke (required when affected)')
    if not args.ui:report['not_run'].append('Graphical workflow suites')
    if not args.build:report['not_run'].append('Distribution build/install check')
    report_path=output/'report.json'
    def save():report_path.write_text(json.dumps(report,indent=2)+'\n')
    def run(name,command,timeout=300):
        print(name+': '+subprocess.list2cmdline(command),flush=True)
        start=time.monotonic();log=output/(name+'.log');code=1
        with log.open('w') as stream:
            try:code=execute(command,stream,timeout)
            except (OSError,subprocess.TimeoutExpired) as exc:stream.write(str(exc)+'\n')
        report['checks'].append({'name':name,'command':command,'exit_code':code,'seconds':round(time.monotonic()-start,3),'log':str(log)})
        save();print(log.read_text(),end='',flush=True)
        if code:raise RuntimeError(name+' failed; see '+str(log))
    save()
    try:
        run('diff',['git','diff','--check','HEAD'])
        run('core',[sys.executable,'-m','pytest','-q'])
        run('cli',[sys.executable,str(ROOT/'tests/integration/cli_smoke.py')])
        if args.build:
            with tempfile.TemporaryDirectory(prefix='cadgit-build-gate-') as temporary:
                directory=Path(temporary);dist=directory/'dist';installed=directory/'installed'
                run('build',['uv','build','--out-dir',str(dist)])
                wheel=next(dist.glob('*.whl'))
                run('wheel-install',['uv','pip','install','--python',sys.executable,'--no-deps','--target',str(installed),str(wheel)])
                run('wheel-smoke',[sys.executable,'-I',str(ROOT/'scripts/check_wheel.py'),str(installed)])
        if args.ui:
            for suite in UI_SUITES:run(suite,[sys.executable,str(ROOT/'tests/integration'/f'{suite}.py')])
        if args.mcp:run('mcp_workflow_smoke',[sys.executable,str(ROOT/'tests/integration/mcp_workflow_smoke.py')])
        report['final_source_state']=source_state()
        if report['final_source_state']!=initial:
            raise RuntimeError('Source changed while gates ran; rerun on a stable tree')
        report['result']='passed selected automated gates'
    except KeyboardInterrupt:
        report['result']='interrupted';print('Gate run interrupted',file=sys.stderr)
    except Exception as exc:
        report['result']='failed';report['error']=str(exc);print(str(exc),file=sys.stderr)
    finally:
        completed={check['name'] for check in report['checks']}
        report['pending_checks']=[name for name in planned if name not in completed]
        report['finished_at']=datetime.now(timezone.utc).isoformat();save()
        print('QA report: '+str(report_path),flush=True)
    return 0 if report['result']=='passed selected automated gates' else 1


if __name__=='__main__':raise SystemExit(main())
