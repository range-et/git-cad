"""Adversarial Qt workflow checks. Requires an active graphical session."""
import sys,time,tempfile
from pathlib import Path
import cadgit.ui_v2 as ui
from cadgit.demo import create
from PySide6.QtTest import QTest

app=ui.W.QApplication([]);app.setQuitOnLastWindowClosed(False)
project=create(Path(tempfile.mkdtemp())/'ui-robustness')
errors=[];unhandled=[]
sys.excepthook=lambda kind,error,tb:unhandled.append(str(error))
window=ui.Window(project);window.fail=lambda message:errors.append(str(message));window.show()

def settle(window):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
        if not window.jobs:return
    raise AssertionError('GUI job did not finish')

QTest.qWait(140);settle(window)
real_meshes=ui.meshes
try:
    # Failure is visible, the tab is disabled, and the same graph version retries.
    source=project.records()[0]
    ui.meshes=lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError('Transient read failure'))
    window.open_record(source['id']);settle(window)
    assert window.current().load_state=='error' and not window.add_button.isEnabled()
    ui.meshes=real_meshes;window.open_record(source['id']);settle(window)
    assert window.current().load_state=='ready' and window.current().parts

    # Two historical meshes with identical prim paths remain independently selectable.
    sources=[r for r in project.records() if r['source']=='rhino']
    window.draft=[ui.Selection(snapshot_id=sources[0]['id'],prim_path='/Engine/Block').model_dump(),ui.Selection(snapshot_id=sources[1]['id'],prim_path='/Engine/Block',translation=(.2,0,0)).model_dump()]
    window.preview_draft();settle(window);preview=window.current()
    assert len(preview.parts)==2 and len({p['path'] for p in preview.parts})==2
    assert window.scene.topLevelItemCount()>0
    window.pick_path(preview.parts[0]['path'])
    assert sum(actor.prop.show_edges for name,actor in preview.plotter.actors.items() if name.startswith('mesh_'))==1
    assert not window.export_action.isEnabled() and not window.main_action.isEnabled()

    # Closing a preview during loading must not touch its deleted renderer.
    def slow_meshes(*args,**kwargs):time.sleep(.1);return real_meshes(*args,**kwargs)
    ui.meshes=slow_meshes;window.preview_draft();window.close_tab(window.tabs.currentIndex());settle(window)
    assert not unhandled,unhandled
    ui.meshes=real_meshes

    # Callback exceptions are surfaced through the normal error path.
    window.job(lambda:True,lambda result:(_ for _ in ()).throw(RuntimeError('Callback failed')));settle(window)
    assert any('Callback failed' in error for error in errors)
    assert not unhandled,unhandled

    # Assembly save targets the draft, publishes its lineage, and ignores repeat clicks.
    window.update_tray();output=project.root/'exports/ui-save.usdz';before=len(project.records('assemblies'))
    original_dialog=ui.W.QFileDialog.getSaveFileName
    ui.W.QFileDialog.getSaveFileName=lambda *args,**kwargs:(str(output),'USD package (*.usdz)')
    try:
        window.save_assembly();assert window._saving_assembly and not window.save_button.isEnabled()
        window.save_assembly();settle(window)
    finally:ui.W.QFileDialog.getSaveFileName=original_dialog
    assert output.exists() and Path(str(output)+'.cadgit.json').exists()
    assert len(project.records('assemblies'))==before+1
    assert window.current().record['id']==ui.read_json(Path(str(output)+'.cadgit.json'))['source_id']

    # Search is navigable and the graph supports keyboard focus/opening.
    graph=window.history;graph.setFocus();graph.select_ref(graph.graph['nodes'][0]['id'])
    before=graph.selected_ref;QTest.keyClick(graph,ui.QtCore.Qt.Key_Down)
    assert graph.selected_ref!=before
    window.search.setText('Cooling');app.processEvents()
    assert graph.selected_ref in graph.matched_ids() and window.search_summary.isVisible()
    QTest.keyClick(window.search,ui.QtCore.Qt.Key_Return);settle(window)
    assert window.current().record['id']==graph.selected_ref
    window.resize(1000,640);app.processEvents();window.grab().save('/tmp/cadgit-ui-robustness-small.png')

    # Window closure ignores late callbacks, while the background operation finishes.
    completed=[];window.job(lambda:(time.sleep(.1),True)[1],lambda value:completed.append(value));window.close();settle(window)
    assert not completed and not unhandled

    # Unreadable saved draft bytes remain in place, with an exact recovery copy.
    draft=project.root/'.cadgit/drafts/current.json';damaged=b'{incomplete original draft';draft.write_bytes(damaged)
    recovered=ui.Window(project);assert draft.read_bytes()==damaged
    backups=list(draft.parent.glob('unreadable_*.json'));assert backups and backups[-1].read_bytes()==damaged
    broken=project.root/'history/sources/rhino/broken';broken.mkdir(parents=True);(broken/'manifest.json').write_text('{broken record');(broken/'COMMITTED').write_text('broken')
    recovered.refresh();assert 'unreadable records' in recovered.graph_warning.text()
    assert recovered.history.graph['nodes']
    recovered.close();app.processEvents()
    assert not unhandled,unhandled
    print('UI_ROBUSTNESS_VERIFIED: retry, unique preview selection, closed-tab/window callbacks, callback errors, graph search/keyboard, draft preservation')
finally:
    ui.meshes=real_meshes
    window.close()
