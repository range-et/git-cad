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
        print(f'DIALOG_WORKFLOWS_VERIFIED: {len(cases)} cases; originals immutable')
    finally:
        window.close()
        app.processEvents()
