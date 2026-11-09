"""Temporary-project GUI preparation, closed-source-tab and large-selection checks."""
import tempfile,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_history import box
import cadgit.ui_v2 as ui
from cadgit.store import Project,file_digest
from cadgit.brep import list_jobs,verify_job

app=ui.W.QApplication([]);app.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory(prefix='cadgit-brep-ui-') as folder:
    root=Path(folder);project=Project.init(root/'project');source=project.ingest(box(root/'part.usda'))
    before=file_digest(project.stage_path(source));errors=[];messages=[]
    window=ui.Window(project);window.fail=lambda message:errors.append(str(message));window.show()
    def wait():
        deadline=time.monotonic()+20
        while time.monotonic()<deadline:
            app.processEvents();time.sleep(.005)
            if window.current() and window.current().load_state=='ready' and not window.jobs:return
        raise AssertionError('Preparation/UI did not finish')
    wait();original_dialog=ui.W.QDialog.exec;original_message=ui.W.QMessageBox.exec
    def dialog_exec(dialog):
        if dialog.windowTitle()!='Prepare B-rep reconstruction inputs':return original_dialog(dialog)
        dialog.show();app.processEvents()
        assert not any(box.isChecked() for box in dialog.findChildren(ui.W.QCheckBox))
        paths=dialog.findChild(ui.W.QPlainTextEdit);assert paths and paths.maximumHeight()<=160
        buttons=dialog.findChild(ui.W.QDialogButtonBox);ok=buttons.button(ui.W.QDialogButtonBox.Ok)
        assert dialog.screen().availableGeometry().contains(ok.mapToGlobal(ok.rect().center()))
        note=next(label for label in dialog.findChildren(ui.W.QLabel) if label.text().startswith('Preparation only:'))
        assert note.height()>=note.heightForWidth(note.width())
        dialog.hide();return ui.W.QDialog.Accepted
    def message_exec(message):messages.append(message.text());return ui.W.QMessageBox.Close
    ui.W.QDialog.exec=dialog_exec;ui.W.QMessageBox.exec=message_exec
    try:
        tab=window.current();tab.selected={'/World/Part'}
        window.prepare_brep_dialog();window.close_tab(window.tabs.currentIndex())
        deadline=time.monotonic()+20
        while window.jobs and time.monotonic()<deadline:app.processEvents();time.sleep(.005)
        jobs=list_jobs(project);assert len(jobs)==1 and not window.jobs
        assert jobs[0]['source_id']==source['id'] and jobs[0]['request']['selections']==['/World/Part']
        assert verify_job(project,jobs[0]['id'])['ok'] and file_digest(project.stage_path(source))==before
        assert messages and 'no STEP exists' in messages[-1]
        assert not list(Path(jobs[0]['_directory']).rglob('*.step'))
        window.open_record(source['id']);wait();window.current().selected={'/World/Part'+str(i) for i in range(151)}
        # Exercise the large dialog layout without submitting fictitious paths.
        def large(dialog):dialog_exec(dialog);return ui.W.QDialog.Rejected
        ui.W.QDialog.exec=large;window.prepare_brep_dialog()
        assert len(list_jobs(project))==1 and not errors,errors
        print('BREP_PREPARATION_UI_VERIFIED: frozen selection, closed source tab, immutable inputs, no STEP claim, 151-selection layout')
    finally:
        ui.W.QDialog.exec=original_dialog;ui.W.QMessageBox.exec=original_message
        window.close();app.processEvents()
