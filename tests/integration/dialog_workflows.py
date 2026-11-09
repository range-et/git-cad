"""Finite dialog/filter workflows; real Qt dialogs, scripted file-picker responses.

No native applications are launched. Every case uses a disposable project.
"""
import copy
import json
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from PySide6.QtTest import QTest
import cadgit.ui_v2 as ui
from cadgit.demo import create

app = ui.W.QApplication([])
app.setQuitOnLastWindowClosed(False)
cases = []
errors = []
callback_errors = []

with tempfile.TemporaryDirectory(prefix='cadgit-dialog-workflows-') as temporary:
    project = create(Path(temporary) / 'project')
    second = None
    window = ui.Window(project)
    window.fail = lambda message: errors.append(str(message))
    window.show()

    def settle():
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
            if not window.jobs and not window.library_browser.jobs:
                return
        raise AssertionError('UI work timed out')

    def modal(action, invoke):
        def interact():
            dialog = app.activeModalWidget()
            try:
                assert dialog is not None, 'Expected modal dialog'
                action(dialog)
            except BaseException as exc:
                callback_errors.append(repr(exc))
                if dialog:
                    dialog.reject()
        ui.QtCore.QTimer.singleShot(50, interact)
        invoke()
        assert not callback_errors, callback_errors

    def record(name):
        cases.append(name)
        print('DIALOG_CASE_PASS', name, flush=True)

    try:
        QTest.qWait(140)
        settle()
        source = window.current().record
        original_records = {r['id']: copy.deepcopy(r) for r in project.records()}
        original_config = (project.root / 'cadgit.json').read_bytes()
        window.pick_path(window.current().parts[0]['path'])
        window.add_selection()
        original_draft = copy.deepcopy(window.draft)
        counts = (len(project.records('assemblies')), len(window.library_browser.library.records()))

        # All file-picker cancellation paths leave draft/history intact.
        target = {'label': 'Test app', 'kind': 'external', 'extension': '.usdz', 'command': ['unused', '{usd}']}
        for name, invoke in [('save', window.save_assembly), ('stl', window.export_stl_dialog),
                             ('handoff', lambda: window.open_target(target))]:
            with patch.object(ui.W.QFileDialog, 'getSaveFileName', return_value=('', '')):
                invoke()
            settle()
            assert window.draft == original_draft
            assert len(project.records('assemblies')) == counts[0]
            record('cancel-' + name)
        with patch.object(ui.W.QFileDialog, 'getOpenFileName', return_value=('', '')):
            window.ingest_dialog()
        assert set(original_records) == {r['id'] for r in project.records()}
        record('cancel-ingest')

        # Overwrite rejection happens before any assembly publication.
        output = project.root / 'exports/existing.usdz'
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(b'preserve this existing file')
        with patch.object(ui.W.QFileDialog, 'getSaveFileName', return_value=(str(output), '')):
            window.save_assembly()
        assert output.read_bytes() == b'preserve this existing file'
        assert len(project.records('assemblies')) == counts[0]
        assert 'not overwritten' in errors.pop()
        record('save-existing-output')

        modal(lambda dialog: dialog.reject(), window.settings)
        assert (project.root / 'cadgit.json').read_bytes() == original_config
        record('settings-cancel')
        for text in ['{broken', '{}', '[{"label":"Missing command","kind":"external","extension":".usd"}]']:
            warnings = []
            def invalid(dialog):
                dialog.findChild(ui.W.QPlainTextEdit).setPlainText(text)
                with patch.object(ui.W.QMessageBox, 'warning', side_effect=lambda *args: warnings.append(args[2])):
                    dialog.findChild(ui.W.QDialogButtonBox).button(ui.W.QDialogButtonBox.Save).click()
                assert dialog.isVisible() and warnings
                assert (project.root / 'cadgit.json').read_bytes() == original_config
                dialog.reject()
            modal(invalid, window.settings)
            record('settings-invalid-' + str(len(cases)))
        def valid(dialog):
            dialog.findChild(ui.W.QPlainTextEdit).setPlainText(json.dumps([target]))
            with patch.object(ui.W.QMessageBox, 'warning', side_effect=lambda *args: (_ for _ in ()).throw(AssertionError(args[2]))):
                dialog.findChild(ui.W.QDialogButtonBox).button(ui.W.QDialogButtonBox.Save).click()
        modal(valid, window.settings)
        assert json.loads((project.root / 'cadgit.json').read_text())['open_targets'] == [target]
        assert 'Test app…' in [a.text() for a in window.open_menu.menu().actions()]
        record('settings-save-updates-target-menu')

        import cadgit.store as storage
        configured=storage.read_json(project.root/'cadgit.json')
        configured['future_setting']={'nested':[1,2]};storage.atomic_json(project.root/'cadgit.json',configured)
        before_settings=(project.root/'cadgit.json').read_bytes()
        before_events={p.name for p in (project.root/'history/events').iterdir()}
        revised_target={**target,'label':'Recovered app'}
        write_config=storage.atomic_json;sync_config=storage.fsync_dir
        def denied_config(path,value,*args,**kwargs):
            if Path(path)==project.root/'cadgit.json':raise OSError('Injected settings save denial')
            return write_config(path,value,*args,**kwargs)
        def failed_settings(dialog):
            dialog.findChild(ui.W.QPlainTextEdit).setPlainText(json.dumps([revised_target]))
            notices=[]
            with patch.object(storage,'atomic_json',side_effect=denied_config),patch.object(ui.W.QMessageBox,'warning',side_effect=lambda *args:notices.append(args[2])):
                dialog.findChild(ui.W.QDialogButtonBox).button(ui.W.QDialogButtonBox.Save).click()
            assert dialog.isVisible() and 'Injected settings save denial' in notices[-1]
            dialog.reject()
        modal(failed_settings,window.settings)
        assert (project.root/'cadgit.json').read_bytes()==before_settings
        assert {p.name for p in (project.root/'history/events').iterdir()}==before_events
        record('settings-failed-save-keeps-config-and-no-success-event')
        def uncertain_config_sync(path):
            if Path(path)==project.root:raise OSError('Injected settings sync warning')
            return sync_config(path)
        def published_settings(dialog):
            dialog.findChild(ui.W.QPlainTextEdit).setPlainText(json.dumps([revised_target]))
            with patch.object(storage,'fsync_dir',side_effect=uncertain_config_sync),patch.object(ui.W.QMessageBox,'warning',side_effect=lambda *args:(_ for _ in ()).throw(AssertionError(args[2]))):
                dialog.findChild(ui.W.QDialogButtonBox).button(ui.W.QDialogButtonBox.Save).click()
        modal(published_settings,window.settings)
        assert storage.read_json(project.root/'cadgit.json')['open_targets']==[revised_target]
        assert storage.read_json(project.root/'cadgit.json')['future_setting']=={'nested':[1,2]}
        assert 'Injected settings sync warning' in window.statusBar().currentMessage()
        assert 'Recovered app…' in [a.text() for a in window.open_menu.menu().actions()]
        record('settings-published-sync-warning-retains-new-target-and-extensions')

        # Cancel naming/branching; invalid names fail; successful branch does not change main.
        before_main = project.config.get('main')
        with patch.object(ui.W.QInputDialog, 'getText', return_value=('unused', False)):
            window.create_branch(source)
            window.name_version(source)
        assert project.config.get('main') == before_main
        record('branch-and-name-cancel')

        browser = window.library_browser
        window.workspace_tabs.setCurrentIndex(1)
        material = next(r for r in browser.library.records() if r['kind'] == 'material')
        for name in ['new_material', 'new_revision', 'derive', 'recombine']:
            browser.select_revision(material['id'])
            before = {r['id'] for r in browser.library.records()}
            modal(lambda dialog: dialog.reject(), getattr(browser, name))
            settle()
            assert {r['id'] for r in browser.library.records()} == before
            record('material-cancel-' + name)

        # A validation exception must invalidate a previously usable selection.
        emissions=[]
        browser.materialSelected.connect(emissions.append)
        for boundary in ['indexed','verify','thumbnail']:
            browser.select_revision(material['id'])
            assert browser._valid_selection and browser.use_button.isEnabled()
            target=browser.library if boundary=='verify' else browser
            with patch.object(target,boundary,side_effect=OSError('Injected selection read failure')):
                browser.revision_selected()
            assert not browser._valid_selection
            assert all(not control.isEnabled() for control in [browser.use_button,browser.revise_button,browser.derive_button,browser.recombine_button])
            browser.use_material()
            assert not emissions
            assert 'Injected selection read failure' in browser.status.text()
            browser.select_revision(material['id'])
            assert browser._valid_selection and browser.use_button.isEnabled()
            record('material-selection-failure-recovery-'+boundary)
        browser.materialSelected.disconnect(emissions.append)

        # Real material creation, revision and derivation through dialog buttons.
        def save_material(dialog):
            dialog.name.setText('Dialog-created material')
            dialog.findChild(ui.W.QDialogButtonBox).button(ui.W.QDialogButtonBox.Save).click()
        modal(save_material, browser.new_material)
        settle()
        created = copy.deepcopy(browser.record)
        assert created['label'] == 'Dialog-created material'
        record('material-create')
        modal(save_material, browser.new_revision)
        settle()
        revised = copy.deepcopy(browser.record)
        assert revised['asset_id'] == created['asset_id'] and revised['id'] != created['id']
        assert len(browser.library.history(created['asset_id'])) == 2
        record('material-revise')
        modal(save_material, browser.derive)
        settle()
        derived = copy.deepcopy(browser.record)
        assert derived['asset_id'] != revised['asset_id']
        assert any(p['revision_id'] == revised['id'] for p in derived['parents'])
        record('material-derive')
        def recombine(dialog):
            combos = dialog.findChildren(ui.W.QComboBox)
            assert len(combos) == 2
            combos[0].setCurrentIndex(combos[0].findData(created['id']))
            combos[1].setCurrentIndex(combos[1].findData(revised['id']))
            dialog.findChild(ui.W.QDialogButtonBox).button(ui.W.QDialogButtonBox.Save).click()
        modal(recombine, browser.recombine)
        settle()
        combined = browser.record
        assert {created['id'], revised['id']} <= {p['revision_id'] for p in combined['parents']}
        assert browser.library.verify(combined['id'])['ok']
        record('material-recombine-pinned-donors')

        # Every kind filter crossed with empty/matching/no-match queries; no stale use action.
        for row in range(browser.kinds.count()):
            for query in ['', 'Dialog-created', 'no-such-asset-987654']:
                browser.select_revision(combined['id'])
                browser.kinds.setCurrentRow(row)
                browser.search.setText(query)
                QTest.qWait(230)
                if browser.grid.count() == 0:
                    assert browser.record is None and not browser.use_button.isEnabled()
                if browser.record:
                    assert browser.record['id'] in browser._index
                    assert browser.use_button.isEnabled() == (browser.record['kind'] == 'material' and browser._valid_selection)
                record(f'filter-{row}-query-{query or "empty"}')
        # Start operations, then change context before the worker is released.
        from threading import Event
        window.workspace_tabs.setCurrentIndex(0)
        window.open_record(source['id'])
        settle()
        frozen = copy.deepcopy(window.draft)
        gate = Event()
        real_assemble = ui.assemble
        def delayed_assemble(*args, **kwargs):
            assert gate.wait(10), 'Save worker gate timed out'
            return real_assemble(*args, **kwargs)
        saved_path = project.root / 'exports/frozen.usdz'
        try:
            with patch.object(ui, 'assemble', side_effect=delayed_assemble), patch.object(
                    ui.W.QFileDialog, 'getSaveFileName', return_value=(str(saved_path), '')):
                window.save_assembly()
                window.draft[0]['translation'] = [9, 0, 0]
                window.update_tray()
                window.close_tab(window.tabs.currentIndex())
                gate.set()
                settle()
        finally:
            gate.set()
        saved = project.resolve(json.loads(Path(str(saved_path) + '.cadgit.json').read_text())['source_id'])
        assert list(saved['selections'][0]['translation']) == list(frozen[0]['translation'])
        assert list(window.draft[0]['translation']) == [9, 0, 0]
        assert project.verify(saved['id'])['ok']
        record('save-freezes-recipe-across-edit-and-close')
        window.set_main()
        assert project.resolve('main')['id'] == saved['id']
        record('saved-assembly-set-main')

        window.open_record(source['id'])
        settle()
        window.pick_path(window.current().parts[0]['path'])
        selected = next(iter(window.current().selected))
        stl_path = project.root / 'exports/frozen.stl'
        with patch.object(ui.W.QFileDialog, 'getSaveFileName', return_value=(str(stl_path), '')), patch.object(
                ui.W.QMessageBox, 'question', return_value=ui.W.QMessageBox.No):
            window.export_stl_dialog()
        assert not stl_path.exists()
        record('stl-confirmation-no')
        gate = Event()
        actual = []
        real_export = ui.export_stl
        def delayed_export(*args, **kwargs):
            assert gate.wait(10), 'Export worker gate timed out'
            actual.append((args[1], args[3]))
            return real_export(*args, **kwargs)
        try:
            with patch.object(ui, 'export_stl', side_effect=delayed_export), patch.object(
                    ui.W.QFileDialog, 'getSaveFileName', return_value=(str(stl_path), '')), patch.object(
                    ui.W.QMessageBox, 'question', return_value=ui.W.QMessageBox.Yes):
                window.export_stl_dialog()
                window.close_tab(window.tabs.currentIndex())
                gate.set()
                settle()
        finally:
            gate.set()
        assert actual == [(source['id'], selected)] and stl_path.exists()
        record('stl-freezes-source-across-tab-close')

        # Publication failure after the assembly commit must expose its durable ID.
        failed_path = project.root / 'exports/failed.usdz'
        before_ids = {r['id'] for r in project.records('assemblies')}
        with patch('cadgit.usd.export_usd', side_effect=OSError('Injected destination failure')), patch.object(
                ui.W.QFileDialog, 'getSaveFileName', return_value=(str(failed_path), '')):
            window.save_assembly()
            settle()
        new_ids = {r['id'] for r in project.records('assemblies')} - before_ids
        assert len(new_ids) == 1 and next(iter(new_ids)) in errors.pop()
        assert not failed_path.exists() and not window._saving_assembly
        assert project.resolve('main')['id'] == saved['id']
        record('save-partial-publication-surfaces-committed-id')

        # Committed outcomes retain both sync and event-log warnings in the UI.
        import cadgit.store as store
        real_sync=store.fsync_dir
        def fail_library_sync(path):
            if Path(path)==browser.library.root/'revisions':raise OSError('Injected library directory sync failure')
            return real_sync(path)
        with patch.object(store,'fsync_dir',side_effect=fail_library_sync), patch.object(project,'event',side_effect=OSError('Injected audit event failure')):
            warned=browser.library.create_material('Committed with warning')
        browser.changed_record(warned)
        assert warned['id'] in browser.status.text()
        assert 'directory sync' in browser.status.text() and 'audit event' in browser.status.text()
        assert browser.library.verify(warned['id'])['ok']
        record('library-shows-accumulated-publication-warnings')
        branch_source=project.records()[0]
        with patch.object(project,'event',side_effect=OSError('Injected config event failure')):
            window.activate_branch(branch_source['source'],branch_source.get('branch','main'))
            assert 'config event failure' in window.statusBar().currentMessage()
            record('activate-branch-publication-warning')
            with patch.object(ui.W.QInputDialog,'getText',return_value=('warning-branch',True)):
                window.create_branch(branch_source)
            assert 'config event failure' in window.statusBar().currentMessage()
            record('create-branch-publication-warning')
            with patch.object(ui.W.QInputDialog,'getText',return_value=('Warning version',True)):
                window.name_version(source)
            assert 'config event failure' in window.statusBar().currentMessage()
            record('name-version-publication-warning')
            def choose_main():
                menu=app.activePopupWidget()
                try:
                    assert isinstance(menu,ui.W.QMenu), 'Expected history context menu'
                    next(action for action in menu.actions() if action.text()=='Set as main').trigger()
                except BaseException as exc:callback_errors.append(repr(exc))
                finally:
                    if menu:menu.close()
            ui.QtCore.QTimer.singleShot(50,choose_main)
            window.history_menu(saved['id'],ui.QtCore.QPoint())
            assert not callback_errors,callback_errors
            assert 'config event failure' in window.statusBar().currentMessage()
            assert project.resolve('main')['id']==saved['id']
            record('context-main-shows-publication-warning')
        warning_export=project.root/'exports/warning.usdz'
        def fail_assembly_sync(path):
            if Path(path)==project.root/'assemblies':raise OSError('Injected assembly directory sync failure')
            return real_sync(path)
        with patch.object(store,'fsync_dir',side_effect=fail_assembly_sync), patch.object(project,'event',side_effect=OSError('Injected assembly event failure')), patch.object(ui.W.QFileDialog,'getSaveFileName',return_value=(str(warning_export),'')):
            window.save_assembly()
            settle()
        assert warning_export.exists() and project.verify(window.latest_assembly['id'])['ok']
        assert 'assembly directory sync' in window.statusBar().currentMessage()
        assert 'event log failed' in window.statusBar().currentMessage()
        record('assembly-retains-sync-and-export-event-warnings')

        # Exercise publication messages through real background completion paths.
        incoming=project.stage_path(source)
        with patch.object(ui.W.QFileDialog,'getOpenFileName',return_value=(str(incoming),'')),patch.object(ui.W.QInputDialog,'getText',return_value=('warningprobe',True)),patch.object(project,'event',side_effect=OSError('Injected ingest event warning')):
            window.ingest_dialog();settle()
        deadline=time.monotonic()+20
        while window.current().load_state!='ready' and time.monotonic()<deadline:
            app.processEvents();time.sleep(.01)
        assert window.current().load_state=='ready'
        assert 'Injected ingest event warning' in window.statusBar().currentMessage()
        record('ingest-warning-survives-background-presentation')
        window.current().selected={window.current().parts[0]['path']}
        warned_stl=project.root/'exports/warning.stl'
        with patch.object(ui.W.QFileDialog,'getSaveFileName',return_value=(str(warned_stl),'')),patch.object(ui.W.QMessageBox,'question',return_value=ui.W.QMessageBox.Yes),patch.object(project,'event',side_effect=OSError('Injected STL event warning')):
            window.export_stl_dialog();settle()
        assert warned_stl.exists() and 'Injected STL event warning' in window.statusBar().currentMessage(), (errors,window.statusBar().currentMessage())
        record('stl-warning-visible-after-completion')
        from cadgit.brep import list_jobs,verify_job
        before_jobs=len(list_jobs(project));messages=[]
        window.current().selected={window.current().parts[0]['path']}
        def brep_message(dialog):messages.append(dialog.text());return ui.W.QMessageBox.Close
        with patch.object(ui.W.QDialog,'exec',return_value=ui.W.QDialog.Accepted),patch.object(ui.W.QMessageBox,'exec',brep_message),patch.object(project,'event',side_effect=OSError('Injected B-rep event warning')):
            window.prepare_brep_dialog();settle()
        assert 'Injected B-rep event warning' in window.statusBar().currentMessage()
        assert 'Injected B-rep event warning' in messages[-1]
        assert len(list_jobs(project))==before_jobs+1 and all(verify_job(project,j['id'])['ok'] for j in list_jobs(project))
        record('brep-warning-in-status-and-dialog')
        with patch.object(ui.W.QDialog,'exec',return_value=ui.W.QDialog.Accepted),patch('cadgit.brep.prepare_job',side_effect=OSError('Injected B-rep precommit failure')):
            window.prepare_brep_dialog();settle()
        assert errors.pop()=='Injected B-rep precommit failure' and not window._brep_preparations
        assert len(list_jobs(project))==before_jobs+1
        with patch.object(ui.W.QDialog,'exec',return_value=ui.W.QDialog.Accepted),patch.object(ui.W.QMessageBox,'exec',brep_message):
            window.prepare_brep_dialog();settle()
        assert len(list_jobs(project))==before_jobs+2 and window._publication_notice is None
        record('brep-failed-save-retry-clears-prior-warning')
        # A handoff may publish successfully while durability and app launch fail.
        handoff=project.root/'exports/warning-handoff.usdz'
        target={'kind':'external','label':'Viewer','extension':'.usdz','command':['viewer','{usd}']}
        def fail_handoff_sync(path):
            if Path(path)==handoff.parent:raise OSError('Injected handoff sync warning')
            return real_sync(path)
        with patch.object(ui.W.QFileDialog,'getSaveFileName',return_value=(str(handoff),'')),patch.object(store,'fsync_dir',side_effect=fail_handoff_sync),patch('cadgit.handoff.subprocess.Popen',side_effect=OSError('Injected launch failure')):
            window.open_target(target);settle()
        assert handoff.exists() and Path(str(handoff)+'.cadgit.json').exists()
        assert 'Injected handoff sync warning' in window.statusBar().currentMessage()
        assert 'Injected launch failure' in window.statusBar().currentMessage()
        record('handoff-retains-lineage-and-both-warning-outcomes')

        # Empty projects and multiple open projects keep drafts/history isolated.
        empty = ui.Project.init(Path(temporary) / 'empty')
        second = ui.Window(empty)
        second.show()
        QTest.qWait(150)
        assert not second.draft and second.tabs.count() == 0
        assert not second.add_button.isEnabled() and not second.save_button.isEnabled()
        assert not second.library_browser.library.records()
        second.close()
        assert window.draft and project.resolve('main')['id'] == saved['id']
        record('empty-project-and-cross-project-isolation')

        for ref, manifest in original_records.items():
            assert project.resolve(ref) == manifest
            assert project.verify(ref)['ok']
        assert not errors, errors
    finally:
        # close() hides these top-level widgets; it does not destroy their Qt
        # children. Drain workers and deferred deletions while QApplication is
        # alive, rather than leaving retained wrappers to Python finalization.
        window.close()
        if second is not None:
            second.close()
        for pool in (ui.VIEWPORT_POOL, ui.QtCore.QThreadPool.globalInstance()):
            assert pool.waitForDone(20_000), 'UI worker pool did not finish during cleanup'
        app.processEvents()
        window.deleteLater()
        if second is not None:
            second.deleteLater()
        ui.QtCore.QCoreApplication.sendPostedEvents(None, ui.QtCore.QEvent.DeferredDelete)
        app.processEvents()
    print(f'DIALOG_WORKFLOWS_VERIFIED: {len(cases)} cases; originals immutable; cleanup completed')
