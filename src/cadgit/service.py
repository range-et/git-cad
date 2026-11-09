from __future__ import annotations
import hashlib, json, os, signal, subprocess, sys, time
from pathlib import Path
from .store import CadgitError, Project, atomic_json, file_digest, now, read_json


def input_digest(marker,filename):
    """Identify frozen producer inputs before allowing destructive cleanup."""
    native=marker.parent/'native_capture.3dm'
    values={'ready':file_digest(marker),'usd':file_digest(filename),'native':file_digest(native) if native.exists() else None}
    return hashlib.sha256(json.dumps(values,sort_keys=True).encode()).hexdigest()


def process_inbox(project):
    import fcntl
    count=0
    inbox=project.root/'.cadgit/inbox'
    if (project.root/'.cadgit').is_symlink() or inbox.is_symlink() or not inbox.resolve().is_relative_to(project.root):raise CadgitError('Unsafe inbox directory; no captures processed')
    captured={}
    for record in project.records():
        capture_id=record.get('metadata',{}).get('capture_id')
        if isinstance(capture_id,str) and capture_id:captured.setdefault((record['source'],capture_id),[]).append(record)
    def order(marker):
        try:
            data=read_json(marker);sequence=data.get('metadata',{}).get('sequence',marker.stat().st_mtime_ns)
            if not isinstance(sequence,int):sequence=marker.stat().st_mtime_ns
            return (str(data.get('source') or ''),sequence)
        except Exception:return ('',0)
    for marker in sorted(inbox.glob('*/ready.json'),key=order):
        if marker.is_symlink() or marker.parent.is_symlink() or not marker.parent.resolve().is_relative_to(inbox.resolve()) or (marker.parent/'ingest.lock').is_symlink():
            print('Unsafe inbox capture skipped: '+str(marker.parent),flush=True)
            continue
        with (marker.parent/'ingest.lock').open('a') as claim:
            try:fcntl.flock(claim,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:continue
            receipt=marker.parent/'receipt.json';error=marker.parent/'error.json'
            if receipt.exists():continue
            capture_id=project.config['id']+':'+marker.parent.name
            try:
                # Recover a crash after commit publication but before its receipt.
                # This also repairs the error marker left by a failed receipt write.
                data=read_json(marker)
                if not isinstance(data.get('source'),str) or not data['source']:raise CadgitError('Invalid inbox source')
                filename=(marker.parent/data['file']).resolve()
                if not filename.is_relative_to(marker.parent.resolve()):raise ValueError('Unsafe inbox path')
                fingerprint=input_digest(marker,filename)
                key=(data['source'],capture_id)
                matches=captured.get(key,[])
                if len(matches)>1:raise CadgitError('Ambiguous recovered capture identity; frozen native source retained')
                if matches:
                    record=matches[0]
                    if not project.verify(record)['ok']:raise CadgitError('Recovered capture failed integrity verification; frozen native source retained')
                    saved_digest=record.get('metadata',{}).get('inbox_input_digest')
                    if saved_digest is not None and (saved_digest!=fingerprint or input_digest(marker,filename)!=fingerprint):raise CadgitError('Recovered capture inputs changed; frozen native source retained')
                    recovered={'snapshot_id':record['id'],'committed_at':now(),'recovered':True}
                    if saved_digest is None:recovered['cleanup_warning']='Legacy capture has no frozen-input digest; native input retained'
                    atomic_json(receipt,recovered)
                    error.unlink(missing_ok=True)
                    if saved_digest is not None:(marker.parent/'native_capture.3dm').unlink(missing_ok=True)
                    continue
                if error.exists():continue
                metadata={**data.get('metadata',{}),'capture_id':capture_id,'inbox_input_digest':fingerprint}
                record=project.ingest(filename,data['source'],data.get('label'),branch=data.get('branch'),metadata=metadata)
                captured[key]=[record]
                if input_digest(marker,filename)!=fingerprint:raise CadgitError('Capture inputs changed during ingestion; frozen native source retained')
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
