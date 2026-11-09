"""Real USD load: worker CPU preparation, batched GUI upload and close safety.

Requires a graphical session. Reports heartbeat gaps rather than imposing a
machine-dependent frame-rate threshold. Explicit thread/render assertions catch
the former synchronous preparation and per-object rendering regressions.
"""
import tempfile,time,threading
from pathlib import Path
import numpy as np
from pxr import Usd,UsdGeom,Vt
import cadgit.ui_v2 as ui
from cadgit.store import Project

app=ui.W.QApplication([]);app.setQuitOnLastWindowClosed(False)
main_thread=threading.get_ident();prep_threads=[];uploads=[];beats=[];errors=[]
real_prepare=ui.prepare_parts;real_add=ui.QtInteractor.add_mesh
def prepare(*args,**kwargs):
    prep_threads.append(threading.get_ident())
    return real_prepare(*args,**kwargs)
def add(plotter,*args,**kwargs):
    if kwargs.get('name','').startswith('mesh_'):
        assert threading.get_ident()==main_thread
        assert kwargs.get('render') is False and kwargs.get('reset_camera') is False
        assert kwargs.get('smooth_shading') is False
        uploads.append(time.monotonic())
    return real_add(plotter,*args,**kwargs)
ui.prepare_parts=prepare;ui.QtInteractor.add_mesh=add
timer=ui.QtCore.QTimer();timer.setInterval(10);timer.timeout.connect(lambda:beats.append(time.monotonic()))

with tempfile.TemporaryDirectory(prefix='cadgit-large-load-') as folder:
    root=Path(folder);path=root/'large.usda';stage=Usd.Stage.CreateNew(str(path))
    UsdGeom.SetStageMetersPerUnit(stage,1);UsdGeom.SetStageUpAxis(stage,'Z')
    UsdGeom.Xform.Define(stage,'/Scene')
    grid=ui.pv.Plane(i_resolution=350,j_resolution=350).triangulate()
    cube=ui.pv.Cube().triangulate()
    for i in range(401):
        poly=grid if i==0 else cube;mesh=UsdGeom.Mesh.Define(stage,'/Scene/Mesh_'+str(i))
        points=poly.points+(np.array([i%20,i//20,0])*1.3 if i else 0)
        mesh.CreatePointsAttr(Vt.Vec3fArray.FromNumpy(points.astype(np.float32)))
        faces=poly.faces.reshape(-1,4)
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray.FromNumpy(faces[:,0].astype(np.int32)))
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray.FromNumpy(faces[:,1:].reshape(-1).astype(np.int32)))
        mesh.CreateSubdivisionSchemeAttr('none')
    stage.GetRootLayer().Save();project=Project.init(root/'project');record=project.ingest(path)
    window=ui.Window(project);window.fail=lambda value:errors.append(str(value));window.show();timer.start()
    try:
        start=time.monotonic();deadline=start+60
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.002)
            if window.current() and window.current().load_state=='ready' and not window.jobs:break
        tab=window.current()
        assert tab and tab.load_state=='ready',errors or (tab.load_notice.text() if tab else 'No tab')
        assert len(tab.parts)==401 and len(uploads)==401
        assert prep_threads and all(t!=main_thread for t in prep_threads)
        assert sum(uploads[0]<t<uploads[-1] for t in beats)>=5,'GUI never yielded during upload'
        assert not errors,errors
        print(f'LARGE_LOAD_VERIFIED: 401 meshes, 249800 triangles, {time.monotonic()-start:.2f}s, '
              f'{len(beats)} UI heartbeats, max heartbeat gap {max(np.diff(beats)):.3f}s')
        # Mode changes still work after batched preparation; sources stay intact.
        original=tab.parts[0]['points'].copy()
        for mode in ('Wireframe','Rendered preview','X-ray','Shaded'):window.mode_changed(mode)
        assert np.array_equal(original,tab.parts[0]['points'])
        assert project.verify(record['id'])['ok']
        # Close after CPU preparation but before the next GUI upload batch.
        window.close_tab(window.tabs.currentIndex());window.open_record(record['id'])
        pending=window.current();deadline=time.monotonic()+30
        while not pending.upload_timer.isActive() and time.monotonic()<deadline:
            app.processEvents();time.sleep(.002)
        assert pending.upload_timer.isActive()
        window.close_tab(window.tabs.indexOf(pending));count=len(uploads)
        for _ in range(20):app.processEvents();time.sleep(.005)
        assert len(uploads)==count and not window.jobs
        print('CLOSE_DURING_UPLOAD_VERIFIED: no stale actors or callbacks')
    finally:
        timer.stop();window.close();app.processEvents()
        ui.prepare_parts=real_prepare;ui.QtInteractor.add_mesh=real_add
