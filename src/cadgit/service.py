from __future__ import annotations
import json, os, signal, subprocess, sys, time
from pathlib import Path
from .store import Project, atomic_json, now, read_json


def process_inbox(project):
    import fcntl
    count=0
    captured={r.get('metadata',{}).get('capture_id'):r for r in project.records() if r.get('metadata',{}).get('capture_id')}
    def order(marker):
        try:
            data=read_json(marker);sequence=data.get('metadata',{}).get('sequence',marker.stat().st_mtime_ns)
            if not isinstance(sequence,int):sequence=marker.stat().st_mtime_ns
            return (str(data.get('source') or ''),sequence)
        except Exception:return ('',0)
    for marker in sorted((project.root/'.cadgit/inbox').glob('*/ready.json'),key=order):
        with (marker.parent/'ingest.lock').open('a') as claim:
            try:fcntl.flock(claim,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:continue
            receipt=marker.parent/'receipt.json';error=marker.parent/'error.json'
            if receipt.exists():continue
            capture_id=project.config['id']+':'+marker.parent.name
            try:
                # Recover a crash after commit publication but before its receipt.
                # This also repairs the error marker left by a failed receipt write.
                if capture_id in captured:
                    record=captured[capture_id]
                    atomic_json(receipt,{'snapshot_id':record['id'],'committed_at':now(),'recovered':True})
                    error.unlink(missing_ok=True);(marker.parent/'native_capture.3dm').unlink(missing_ok=True)
                    continue
                if error.exists():continue
                data=read_json(marker);filename=(marker.parent/data['file']).resolve()
                if not filename.is_relative_to(marker.parent.resolve()):raise ValueError('Unsafe inbox path')
                metadata={**data.get('metadata',{}),'capture_id':capture_id}
                record=project.ingest(filename,data['source'],data.get('label'),branch=data.get('branch'),metadata=metadata)
                captured[capture_id]=record
                atomic_json(receipt,{'snapshot_id':record['id'],'committed_at':now()})
                (marker.parent/'native_capture.3dm').unlink(missing_ok=True);count+=1
            except Exception as exc:
                atomic_json(error,{'error':str(exc),'at':now()})
    return count


def run(root):
    project=Project(root)
    import fcntl
    lock=(project.root/'.cadgit/service.lock').open('a')
    try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: return
    running=True
    def stop(*_):
        nonlocal running
        running=False
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    last_snapshot=time.monotonic()
    while running:
        try:
            atomic_json(project.root/".cadgit/service.json",{'pid':os.getpid(),'heartbeat':now(),'project':str(project.root),'phase':'ingesting'})
            process_inbox(project)
            interval=read_json(project.root/'cadgit.json').get('tool_interval_seconds')
            if interval and time.monotonic()-last_snapshot>=max(30,interval):
                from .connectors import capture
                last_snapshot=time.monotonic()
                for app in ['rhino','blender']:
                    try: capture(project,app,respect_binding=True)
                    except Exception as exc: project.event('autosnapshot_failed',{'app':app,'error':str(exc)})
            atomic_json(project.root/'.cadgit/service.json',{'pid':os.getpid(),'heartbeat':now(),'project':str(project.root)})
        except Exception as exc:
            print(now(),str(exc),flush=True)
        time.sleep(0.75)
    (project.root/'.cadgit/service.json').unlink(missing_ok=True)


def start(project):
    if status(project).get('running'): return status(project)
    log=(project.root/'.cadgit/logs/service.log').open('a')
    proc=subprocess.Popen([sys.executable,'-m','cadgit.service',str(project.root)],stdout=log,stderr=log,start_new_session=True)
    log.close()
    for _ in range(25):
        time.sleep(0.1)
        if status(project).get('running'): break
    return status(project)


def _lock_held(project):
    import fcntl
    with (project.root/'.cadgit/service.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return True
        fcntl.flock(lock,fcntl.LOCK_UN);return False


def _process_matches(pid,project):
    try:
        command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True,timeout=2,check=True).stdout.strip()
        return ' -m cadgit.service ' in command and command.endswith(str(project.root))
    except (OSError,subprocess.SubprocessError):return False


def status(project):
    path=project.root/'.cadgit/service.json'
    if not path.exists():return {'running':False}
    try:
        data=read_json(path);pid=data['pid']
        if type(pid) is not int or pid<=0:return {'running':False}
        os.kill(pid,0)
        if not _process_matches(pid,project) or not _lock_held(project):return {'running':False,'reason':'stale service ownership'}
        import datetime as dt
        stamp=dt.datetime.fromisoformat(data['heartbeat'].replace('Z','+00:00'))
        age=(dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()
        # A busy live daemon remains stoppable even while an export/RPC blocks
        # heartbeat updates. The lock and process command establish ownership.
        return {**data,'running':True,'healthy':age<10,'busy':age>=10}
    except Exception:return {'running':False}


def stop(project):
    current=status(project)
    if current.get('running'):os.kill(current['pid'],signal.SIGTERM)
    return {'stopping':current.get('running',False)}

if __name__=='__main__':run(sys.argv[1])
