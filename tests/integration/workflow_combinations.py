"""Finite GUI transition coverage, not every possible user action sequence.

Domain: 4 start modes x 4 end modes x 2 edge states x 2 selection states,
with A -> B -> A switching in each case (64 cases), then concrete draft lifecycle
and tab lifecycle cases. Real Qt actions/widgets and rendered VTK properties are
checked. Dialog input is injected; native applications are not exercised.
"""
import hashlib
import itertools
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PySide6.QtTest import QTest
import cadgit.ui_v2 as ui
from cadgit.demo import create


def main():
    app = ui.W.QApplication.instance() or ui.W.QApplication([])
    app.setQuitOnLastWindowClosed(False)
    errors, unhandled, passed = [], [], []
    old_hook = sys.excepthook
    sys.excepthook = lambda kind, value, tb: unhandled.append(str(value))
    window = None
    with tempfile.TemporaryDirectory(prefix='cadgit-workflow-combinations-') as temporary:
        project = create(Path(temporary) / 'project')
        sources = [r for r in project.records() if r['source'] == 'rhino'][:2]
        assert len(sources) == 2
        source_files = sorted((project.root / 'history/sources').rglob('*'))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files if p.is_file()}
        window = ui.Window(project)
        window.fail = lambda message: errors.append(str(message))
        window.show()
        window.resize(1000, 640)

        def settle():
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                app.processEvents()
                if not window.jobs and all(window.tabs.widget(i).load_state != 'loading' for i in range(window.tabs.count())):
                    assert not unhandled, unhandled
                    return
                QTest.qWait(10)
            raise AssertionError('Pending GUI work did not settle')

        def case(name):
            assert not unhandled, unhandled
            passed.append(name)
            print('CASE_PASS', name, flush=True)

        def selected_paths():
            return {item.data(0, ui.QtCore.Qt.UserRole) for item in window.scene.selectedItems()}

        def select_paths(paths):
            window.scene.clearSelection()
            iterator = ui.W.QTreeWidgetItemIterator(window.scene)
            found = set()
            while iterator.value():
                item = iterator.value()
                value = item.data(0, ui.QtCore.Qt.UserRole)
                if value in paths:
                    item.setSelected(True)
                    found.add(value)
                iterator += 1
            assert found == set(paths), (found, paths)
            assert window.current().selected == set(paths)

        def draft_on_disk():
            return json.loads((project.root / '.cadgit/drafts/current.json').read_text())

        try:
            QTest.qWait(150)
            settle()
            for source in sources:
                window.open_record(source['id'])
                settle()
            a, b = [window.tabs_by_id[r['id']] for r in sources]
            window.tabs.setCurrentWidget(b)
            window.mode_buttons['X-ray'].trigger()
            window.edge_check.setChecked(True)
            select_paths({b.parts[0]['path']})
            b_selection = set(b.selected)
            modes = tuple(window.mode_buttons)
            # Exhaustive only within this explicit 64-element product domain.
            for start, end, edges, selected in itertools.product(modes, modes, (False, True), (False, True)):
                window.tabs.setCurrentWidget(a)
                window.mode_buttons[start].trigger()
                window.edge_check.setChecked(edges)
                expected = {a.parts[0]['path']} if selected else set()
                select_paths(expected)
                window.mode_buttons[end].trigger()
                window.tabs.setCurrentWidget(b)
                assert b.mode == 'X-ray' and b.edges and b.selected == b_selection
                assert window.mode_buttons['X-ray'].isChecked() and window.edge_check.isChecked()
                assert selected_paths() == b_selection
                window.tabs.setCurrentWidget(a)
                assert a.mode == end and a.edges == edges and a.selected == expected
                assert window.mode_buttons[end].isChecked() and window.edge_check.isChecked() == edges
                assert selected_paths() == expected
                assert window.add_button.isEnabled() == selected
                assert window.export_action.isEnabled() and not window.main_action.isEnabled()
                for index, part in enumerate(a.parts):
                    prop = a.plotter.actors['mesh_' + str(index)].prop
                    assert prop.GetRepresentation() == (1 if end == 'Wireframe' else 2)
                    assert prop.show_edges == ((edges or part['path'] in expected) and end != 'Wireframe')
                    if end == 'X-ray':
                        assert abs(prop.opacity - .2) < 1e-6
                assert (a.plotter.renderer._render_passes._ssao_pass is not None) == (end == 'Rendered preview')
                case(f'VIEW-{start}->{end}-edges{int(edges)}-selected{int(selected)}')
            assert len(passed) == 64

            # Tabs can be reordered, and closing an inactive one keeps active context.
            window.tabs.tabBar().moveTab(window.tabs.indexOf(a), window.tabs.indexOf(b))
            window.tabs.setCurrentWidget(a)
            active_id = a.record['id']
            window.close_tab(window.tabs.indexOf(b))
            assert window.current() is a and window.history.selected_ref == active_id
            assert selected_paths() == a.selected
            window.open_record(sources[1]['id'])
            settle()
            b = window.current()
            assert b is not a and b.record['id'] == sources[1]['id']
            assert not b.selected
            window.tabs.setCurrentWidget(a)
            case('TABS-reorder-close-inactive-reopen')

            # Hierarchical selection must not double-count a child under its parent.
            window.draft = []
            window.update_tray()
            path = '/Engine/Block'
            assert any(part['path'] == path for part in a.parts)
            select_paths({'/Engine', path})
            window.add_button.click()
            assert len(window.draft) == 1 and window.draft[0]['prim_path'] == '/Engine'
            assert draft_on_disk() == json.loads(json.dumps(window.draft))
            case('DRAFT-parent-child-deduplicated')
            window.table.selectRow(0)
            window.remove_button.click()
            assert not window.draft and not draft_on_disk()
            select_paths({path})
            window.add_button.click()
            window.add_button.click()
            assert len(window.draft) == 2 and window.draft[0] == window.draft[1]
            window.preview_button.click()
            settle()
            preview = window.current()
            assert len(preview.parts) == 2 and len({part['path'] for part in preview.parts}) == 2
            select_paths({preview.parts[0]['path']})
            assert not window.add_button.isEnabled() and not window.export_action.isEnabled()
            assert not window.main_action.isEnabled() and not window.open_menu.isEnabled()
            case('DRAFT-duplicate-pieces-independent-preview-restrictions')

            window.table.selectRow(0)
            original_draft = json.loads(json.dumps(window.draft))
            original_disk = draft_on_disk()
            for value, accepted, label in [('1,2,3', False, 'cancel'), ('nan,0,0', True, 'nan'), ('inf,0,0', True, 'inf'), ('1,2', True, 'short'), ('a,0,0', True, 'text')]:
                old_error_count = len(errors)
                with patch.object(ui.W.QInputDialog, 'getText', return_value=(value, accepted)):
                    window.move_button.click()
                assert json.loads(json.dumps(window.draft)) == original_draft and draft_on_disk() == original_disk
                assert len(errors) == old_error_count + int(accepted)
                case('MOVE-' + label + '-preserves-draft')
            with patch.object(ui.W.QInputDialog, 'getText', return_value=('0.2, -0.1, 0.03', True)):
                window.move_button.click()
            assert window.draft[0]['translation'] == [.2, -.1, .03]
            assert preview.preview_stale and preview.load_notice.isVisible()
            assert draft_on_disk() == json.loads(json.dumps(window.draft))
            original_points = preview.parts[0]['points'].copy()
            window.preview_button.click()
            settle()
            fresh = window.current()
            assert not fresh.preview_stale
            assert np.allclose(fresh.parts[0]['points'], original_points + [.2, -.1, .03])
            case('MOVE-valid-stales-old-preview-refreshes-placement')

            # Cancel clear is non-mutating; confirmed clear changes only the draft.
            keep = json.loads(json.dumps(window.draft))
            with patch.object(ui.W.QMessageBox, 'question', return_value=ui.W.QMessageBox.No):
                window.clear_button.click()
            assert json.loads(json.dumps(window.draft)) == keep and draft_on_disk() == keep
            case('DRAFT-clear-cancel')
            window.table.selectRow(1)
            window.remove_button.click()
            assert len(window.draft) == 1 and window.draft[0]['translation'] == [.2, -.1, .03]
            case('DRAFT-remove-second-retains-first-placement')
            with patch.object(ui.W.QMessageBox, 'question', return_value=ui.W.QMessageBox.Yes):
                window.clear_button.click()
            assert not window.draft and not draft_on_disk()
            assert not window.save_button.isEnabled() and not window.preview_button.isEnabled()
            assert fresh.preview_stale and not fresh.record
            case('DRAFT-clear-confirm-only-draft')
            while window.tabs.count():
                window.close_tab(0)
            assert not window.add_button.isEnabled() and not window.export_action.isEnabled()
            assert not window.open_menu.isEnabled() and not window.main_action.isEnabled()
            window.open_record(sources[0]['id'])
            settle()
            assert window.current().load_state == 'ready'
            case('TABS-close-all-reopen')

            assert all(hashlib.sha256(p.read_bytes()).hexdigest() == digest for p, digest in before.items())
            assert all(project.verify(record['id'])['ok'] for record in sources)
            assert len(errors) == 4, errors
            case('INVARIANT-source-history-byte-identical-and-verifies')
            print('WORKFLOW_COMBINATIONS_VERIFIED', json.dumps({'cases': len(passed), 'mode_product_cases': 64, 'case_ids': passed}), flush=True)
        finally:
            if window:
                window.close()
                app.processEvents()
            sys.excepthook = old_hook


if __name__ == '__main__':
    main()
