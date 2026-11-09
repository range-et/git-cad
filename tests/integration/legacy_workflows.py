"""Real legacy Qt/VTK workflow coverage using disposable generated scenes."""
import copy
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import cadgit.ui as ui
from cadgit.demo import create

app = ui.W.QApplication([])
app.setQuitOnLastWindowClosed(False)
errors = []
with tempfile.TemporaryDirectory(prefix='git-cad-legacy-') as temporary:
    root = Path(temporary)
    project = create(root / 'project')
    original = {r['id']: copy.deepcopy(r) for r in project.records()}
    window = ui.Window(project)
    window.fail = errors.append
    window.show()

    def settle():
        end = time.monotonic() + 30
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(.01)
            if not window.jobs:
                return
        raise AssertionError('Legacy UI worker timed out')

    def load(ref):
        window.load_record(ref)
        settle()
        assert window.record['id'] == ref

    try:
        time.sleep(.15)
        settle()
        window.timer.stop()
        assert 'Git CAD' in window.windowTitle()
        assert any(w.text() == 'Git CAD' for w in window.findChildren(ui.W.QLabel))
        main = project.resolve('main')['id']
        assert window.record['id'] == main and window.parts
        source = project.records()[0]
        load(source['id'])
        actor = next(a for k, a in window.plotter.actors.items() if k.startswith('part_'))
        window.pick_actor(actor)
        selected = window.selected_path()
        assert selected and selected in {p['path'] for p in window.parts}
        window.add_selection()
        assert window.draft[0]['snapshot_id'] == source['id']
        assert window.draft[0]['prim_path'] == selected
        window.tray.selectRow(0)
        for text, ok in [('ignored', False), ('1, 2', True), ('bad,0,0', True), ('0.01, 0, 0', True)]:
            with patch.object(ui.W.QInputDialog, 'getText', return_value=(text, ok)):
                window.move_piece()
        assert len(errors) == 2
        errors.clear()
        assert window.draft[0]['translation'] == [.01, 0., 0.]
        persisted = ui.read_json(project.root / '.cadgit/drafts/current.json')
        assert persisted == window.draft
        window.preview_draft()
        settle()
        assert window.record is None and window.record_title.text() == 'Assembly draft'
        window.export_dialog()
        assert 'Save the draft' in errors.pop()
        assert project.resolve('main')['id'] == main
        for text, ok in [('', True), ('cancel', False)]:
            with patch.object(ui.W.QInputDialog, 'getText', return_value=(text, ok)):
                window.save_assembly()
        with patch.object(ui.W.QInputDialog, 'getText', return_value=('Legacy saved', True)):
            window.save_assembly()
        settle()
        saved = window.record
        assert saved['label'] == 'Legacy saved' and project.verify(saved['id'])['ok']
        assert project.resolve('main')['id'] == main
        # The queued recipe is frozen before subsequent UI edits. A publication
        # warning must survive the asynchronous load of the committed record.
        queued = []
        frozen = copy.deepcopy(window.draft)
        original_assemble = ui.assemble
        def published(*args):
            result = original_assemble(*args)
            result['publication_warning'] = 'Committed; directory durability uncertain'
            return result
        with patch.object(window, 'job', side_effect=lambda work, done: queued.append((work, done))), patch.object(ui.W.QInputDialog, 'getText', return_value=('Frozen recipe', True)):
            window.save_assembly()
        window.draft[0]['translation'][0] = 99
        with patch.object(ui, 'assemble', side_effect=published):
            result = queued[0][0]()
        assert json.loads(json.dumps(result['selections'])) == frozen
        queued[0][1](result)
        settle()
        assert 'durability uncertain' in window.statusBar().currentMessage()
        saved = window.record
        original_main = project.set_main
        def warned_main(ref):
            result = original_main(ref)
            result['publication_warning'] = 'Main committed; event log unavailable'
            return result
        with patch.object(project, 'set_main', side_effect=warned_main):
            window.set_main()
        assert 'event log unavailable' in window.statusBar().currentMessage()
        assert project.resolve('main')['id'] == saved['id']
        with patch.object(ui.W.QFileDialog, 'getSaveFileName', return_value=('', '')):
            window.export_dialog()
        stl = root / 'part.stl'
        with patch.object(ui.W.QFileDialog, 'getSaveFileName', return_value=(str(stl), '')), patch.object(ui.W.QMessageBox, 'question', return_value=ui.W.QMessageBox.No):
            window.export_dialog()
        assert not stl.exists()
        with patch.object(ui.W.QFileDialog, 'getSaveFileName', return_value=(str(stl), '')), patch.object(ui.W.QMessageBox, 'question', return_value=ui.W.QMessageBox.Yes), patch.object(ui.W.QMessageBox, 'information') as info:
            window.export_dialog()
            settle()
            assert info.called and stl.stat().st_size > 84
        load(source['id'])
        window.set_main()
        assert 'saved assembly' in errors.pop()
        window.source_combo.setCurrentText('manual')
        window.capture_app()
        assert 'Choose Rhino or Blender' in errors.pop()
        with patch.object(ui.W.QFileDialog, 'getOpenFileName', return_value=('', '')):
            window.ingest_dialog()
        with patch.object(ui.W.QFileDialog, 'getOpenFileName', return_value=(str(project.stage_path(source)), '')):
            window.ingest_dialog()
            settle()
        assert window.record['source'] == 'manual'
        # A late preview cannot replace a newer selected history record.
        preview = []
        with patch.object(window, 'job', side_effect=lambda work, done: preview.append((work, done))):
            window.preview_draft()
        load(source['id'])
        preview[0][1](preview[0][0]())
        assert window.record['id'] == source['id']
        assert window.record_title.text() == source['label']
        window.toggle_theme()
        assert window.light
        window.toggle_theme()
        assert not window.light
        with patch.object(ui.QtGui.QDesktopServices, 'openUrl', return_value=True) as opened:
            window.open_folder()
        assert opened.call_args.args[0].toLocalFile() == str(project.root)
        window.screenshot = str(root / 'legacy.png')
        window.save_screenshot()
        window.save_screenshot()
        assert (root / 'legacy.png').stat().st_size > 1000
        window.poll()
        window.tray.selectRow(0)
        window.remove_selection()
        assert not window.draft
        window.preview_draft()
        window.save_assembly()
        window.move_piece()
        window.job(lambda: 1 / 0, lambda _: None)
        settle()
        assert 'division by zero' in errors.pop()
        assert not errors, errors
        for ref, record in original.items():
            assert project.resolve(ref) == record and project.verify(ref)['ok']
    finally:
        window.timer.stop()
        window.close()
        assert ui.QtCore.QThreadPool.globalInstance().waitForDone(20_000)
        app.processEvents()
        window.plotter.close()
        window.deleteLater()
        ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)
        app.processEvents()
print('LEGACY_WORKFLOWS_VERIFIED: load, select, draft, save, main, export, ingest, recovery; originals immutable')
