"""Project material/image browsing, editor preservation and geometry assignment."""
import copy,tempfile,time,sys
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets as W
from PySide6.QtTest import QTest
from cadgit.app_identity import configure_application_identity
configure_application_identity()
from cadgit.store import Project
from cadgit.demo import create
from cadgit.library import Library
from cadgit.library_ui import MaterialEditor
from cadgit.ui_v2 import Window

app=W.QApplication([]);app.setQuitOnLastWindowClosed(False)
p=create(Path(tempfile.mkdtemp())/'project');lib=Library(p);errors=[]
window=Window(p);window.fail=lambda value:errors.append(str(value));window.show()
def wait():
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        app.processEvents();time.sleep(.01)
        if not window.jobs and not window.library_browser.jobs:return
    raise AssertionError('Library/geometry work did not complete')
QTest.qWait(140);wait();browser=window.library_browser
try:
    assert app.applicationName()=='cad-git'
    current=window.current();current.selected={current.parts[0]['path']};window.add_selection();original=copy.deepcopy(window.draft)
    material=next(r for r in lib.records() if r['label']=='PLA + blue surface')
    window.workspace_tabs.setCurrentIndex(1);browser.select_revision(material['id']);app.processEvents()
    assert browser.record['id']==material['id'] and browser.use_button.isEnabled()
    browser.kinds.setCurrentRow(2);app.processEvents()
    assert browser.record is None and not browser.use_button.isEnabled()
    browser.search.setText('no-matching-asset');QTest.qWait(230)
    assert browser.grid.count()==0 and browser.record is None
    browser.select_revision(material['id']);browser.use_button.click();app.processEvents()
    assert window.workspace_tabs.currentIndex()==0 and window.current() is current and window.draft==original
    current.selected={current.parts[0]['path']};window.add_selection()
    assert window.draft[-1]['library_material_revision']==material['id']
    assert not window.draft[0]['library_material_revision']
    # Entire unfamiliar metadata/precise values survive an untouched material editor.
    image=next(r for r in lib.records() if r['kind']=='image');doc=next(r for r in lib.records() if r['kind']=='document')
    shader=p.root/'source/graph.mtlx';shader.write_text('<materialx/>');graph=lib.import_asset(shader)
    definition={'physical':{'properties':{'density':{'value':1234,'unit':'kg/m3','source':'Synthetic fixture only','status':'fixture','conditions':{'temperature':23},'future_extra':True}}},'appearance':{'native_graph':{'revision_id':graph['id'],'future_provider':'x'},'preview':{'base_color':[.111123456,.222234567,.333345678],'roughness':.456789123,'metallic':.123456789},'maps':{'base_color':{'revision_id':image['id'],'color_space':'ACEScg','uv_set':'custom_uv','extensions':{'future':1}}}},'documents':[{'revision_id':doc['id'],'note':'keep reference metadata'}]}
    revision=lib.create_material('Preservation fixture',definition);editor=MaterialEditor(lib,revision)
    assert editor.value()==definition
    editor.add_map('base_color',image['id'],'raw')
    try:editor.value();raise AssertionError('Duplicate map role accepted')
    except Exception as exc:assert 'Duplicate' in str(exc)
    editor.close()
    # A partial import remains explicit after async completion and any debounce.
    browser.select_revision(material['id']);imagefile=p.stage_path(image)
    old_exec=W.QDialog.exec;W.QDialog.exec=lambda self:W.QDialog.Accepted
    try:browser.import_paths([str(imagefile),str(p.root/'does-not-exist.png')]);wait();QTest.qWait(230)
    finally:W.QDialog.exec=old_exec
    assert 'import stopped' in browser.status.text() and 'successful IDs' in browser.status.text()
    assert not errors,errors
    print('MATERIAL_LIBRARY_UI_VERIFIED: per-project browser, revisions, editor losslessness, filter safety, material assignment, partial import, cad-git app identity')
finally:window.close();app.processEvents()
