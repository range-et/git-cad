import tempfile
from cadgit.ui_v2 import *
from cadgit.demo import create
root=Path(tempfile.mkdtemp())/'demo'
create(root)
project=Project(root)
base=next(r for r in project.records() if r['source']=='rhino')
project.branch('rhino','alternative',base['id'],activate=True)
project.ingest(project.stage_path(base),'rhino','Alternative study',metadata={'sample_data':True})
project.name_version(base['id'],'Design baseline')
from PySide6.QtTest import QTest
app=W.QApplication([]);w=Window(project);w.show()
errors=[]
def failed(msg):errors.append(msg);print('UI_ERROR',msg)
w.fail=failed
state={'step':0,'ticks':0}
def tick():
 state['ticks']+=1
 if state['ticks']>80:print('TIMEOUT',state);app.exit(1);return
 if w.jobs:return
 if state['step']==0:
  rs=w.project.records();state['refs']=[rs[0]['id'],rs[-1]['id']]
  assert ('rhino','alternative') in w.history.graph['lanes']
  for splitter,delta in [(w.columns_splitter,QtCore.QPoint(45,0)),(w.workbench_splitter,QtCore.QPoint(0,-45)),(w.inspector_splitter,QtCore.QPoint(0,25))]:
   before=splitter.sizes();handle=splitter.handle(1);point=handle.rect().center()
   QTest.mousePress(handle,QtCore.Qt.LeftButton,pos=point);QTest.mouseMove(handle,point+delta,30);QTest.mouseRelease(handle,QtCore.Qt.LeftButton,pos=point+delta)
   assert splitter.sizes()!=before,('Splitter did not resize',before,splitter.sizes())
  ref=state['refs'][0];w.history.ensureVisible(w.history.rows[ref]);app.processEvents()
  point=w.history.mapFromScene(w.history.positions[ref]);QTest.mouseClick(w.history.viewport(),QtCore.Qt.LeftButton,pos=point)
  assert w.history.selected_ref==ref
  state['step']=1
 elif state['step']==1:
  tab=w.current()
  assert len(tab.plotter.renderer.lights)==3
  for mode in w.mode_buttons:
   w.mode_changed(mode)
   assert 'studio_ground' not in tab.plotter.actors
   assert (tab.plotter.renderer._render_passes._ssao_pass is not None)==(mode=='Rendered preview')
  # Pick a real mesh by projecting its authored vertices into the viewport.
  renderer=tab.plotter.renderer;point=tab.parts[0]['points'][0]
  renderer.SetWorldPoint(*point,1);renderer.WorldToDisplay();x,y,_=renderer.GetDisplayPoint()
  size=tab.plotter.render_window.GetSize()
  click=QtCore.QPoint(round(x*tab.plotter.width()/size[0]),round(tab.plotter.height()-1-y*tab.plotter.height()/size[1]))
  QTest.mouseClick(tab.plotter,QtCore.Qt.LeftButton,pos=click)
  assert tab.selected,'Mesh click did not select geometry'
  # Clicking empty background clears both highlighted geometry and tree selection.
  QTest.mouseClick(tab.plotter,QtCore.Qt.LeftButton,pos=QtCore.QPoint(8,8))
  assert not tab.selected and not w.scene.selectedItems()
  assert all(not actor.prop.show_edges for name,actor in tab.plotter.actors.items() if name.startswith('mesh_'))
  # Dragging across empty space rotates the view without clearing the selection.
  w.pick_path(tab.parts[0]['path'])
  QTest.mousePress(tab.plotter,QtCore.Qt.LeftButton,pos=QtCore.QPoint(8,8));QTest.mouseMove(tab.plotter,QtCore.QPoint(25,25),30);QTest.mouseRelease(tab.plotter,QtCore.Qt.LeftButton,pos=QtCore.QPoint(25,25))
  assert tab.selected
  tab.selected={tab.parts[0]['path']};w.add_selection();w.open_record(state['refs'][1]);state['step']=2
 elif state['step']==2:
  tab=w.current();tab.selected={tab.parts[0]['path']};w.add_selection();assert len(w.draft)==2
  w.preview_draft();state['step']=3
 elif state['step']==3:
  assert len(w.current().parts)==2
  result=assemble(w.project,w.draft,'UI workflow verification');assert w.project.verify(result['id'])['ok']
  assert len(result['selections'])==2
  w.close()
  settings=w.layout_settings();assert settings.value('columns')==w.columns_splitter.saveState()
  print('UI_FLOW_VERIFIED',len(w.mode_buttons),'modes',w.tabs.count(),'tabs',len(w.draft),'pieces; graph click, branch fork, three draggable splitters and layout persistence')
  app.exit(1 if errors else 0)
timer=QtCore.QTimer();timer.timeout.connect(tick);timer.start(300)
raise SystemExit(app.exec())
