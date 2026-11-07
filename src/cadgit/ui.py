from __future__ import annotations
import json, os
from pathlib import Path
os.environ.setdefault('QT_API','pyside6')
from PySide6 import QtCore, QtGui, QtWidgets as W
from pyvistaqt import QtInteractor
import pyvista as pv
from .store import Project, CadgitError, atomic_json, read_json
from .usd import meshes, stage_info, assemble, export_stl
from .models import Selection

class Signals(QtCore.QObject):
    done=QtCore.Signal(object)
    error=QtCore.Signal(str)

class Job(QtCore.QRunnable):
    def __init__(self,fn):
        super().__init__();self.fn=fn;self.signals=Signals()
    def run(self):
        try:self.signals.done.emit(self.fn())
        except Exception as exc:self.signals.error.emit(str(exc))


def theme(app,light=False):
    tokens=json.loads((Path(__file__).parent/'resources/monad_colors.json').read_text())
    colors=tokens['Light_Mode' if light else 'Default_Colors']['General_UI_Colors']
    c={k:v['hex'] for k,v in colors.items()}
    accent=tokens['Default_Colors']['Information_Indicators']['Information_2']['hex']
    app.setStyle('Fusion')
    app.setStyleSheet(f'''
    QWidget {{ color: {c['Primary_Text']}; font-family: "Helvetica Neue", Helvetica, sans-serif; font-size: 13px; }}
    QMainWindow, QDialog {{ background: {c['Background']}; }}
    QWidget#surface {{ background: {c['Layer_01']}; border: 1px solid {c['Border_Subtle']}; }}
    QLabel#brand {{ font-size: 23px; font-weight: 700; letter-spacing: 2px; }}
    QLabel#eyebrow {{ color: {c['Secondary_Text']}; font-family: Menlo, monospace; font-size: 10px; letter-spacing: 1px; }}
    QLabel#muted {{ color: {c['Secondary_Text']}; }}
    QLabel#title {{ font-size: 19px; font-weight: 600; }}
    QLabel#badge {{ color: #6EAD45; background: {c['Layer_02']}; padding: 7px 10px; font-family: Menlo; font-size: 10px; }}
    QPushButton {{ background: {c['Layer_02']}; border: 1px solid {c['Border']}; padding: 8px 12px; text-align: center; }}
    QPushButton:checked {{ background: {c['Layer_03']}; border-color: {accent}; color: {accent}; }}
    QPushButton:hover {{ background: {c['Layer_03']}; border-color: {accent}; }}
    QPushButton:focus, QTreeWidget:focus, QLineEdit:focus {{ border: 1px solid {accent}; }}
    QPushButton#primary {{ background: {accent}; color: #EEF2F6; border-color: {accent}; font-weight: 600; }}
    QPushButton:disabled {{ color: {c['Disabled_Text']}; }}
    QPushButton#primary:disabled {{ background: {c['Layer_02']}; color: {c['Disabled_Text']}; border-color: {c['Border_Subtle']}; }}
    QTreeWidget, QTableWidget, QTextEdit, QListWidget {{ background: {c['Layer_01']}; border: none; alternate-background-color: {c['Layer_02']}; selection-background-color: {accent}; }}
    QTreeWidget::item {{ padding: 7px 4px; }}
    QTreeWidget::item:selected {{ background: {c['Layer_03']}; color: {c['Primary_Text']}; border-left: 2px solid {accent}; }}
    QHeaderView::section {{ background: {c['Layer_02']}; color: {c['Secondary_Text']}; border: none; padding: 7px; font-size: 11px; }}
    QLineEdit, QComboBox, QDoubleSpinBox {{ background: {c['Layer_02']}; padding: 7px; border: 1px solid {c['Border']}; }}
    QComboBox QAbstractItemView {{ background: {c['Layer_02']}; }}
    QSplitter::handle {{ background: {c['Background']}; width: 8px; height: 8px; }}
    QSplitter::handle:hover {{ background: {accent}; }}
    QScrollArea {{ border: none; background: transparent; }}
    QStatusBar {{ color: {c['Secondary_Text']}; font-family: Menlo; font-size: 11px; }}
    QTabWidget::pane {{ border: 1px solid {c['Border_Subtle']}; }}
    QTabBar::tab {{ background: {c['Layer_01']}; color: {c['Secondary_Text']}; padding: 10px 14px; border-right: 1px solid {c['Border_Subtle']}; }}
    QTabBar::tab:selected {{ background: {c['Layer_03']}; color: {c['Primary_Text']}; border-bottom: 2px solid {accent}; }}
    QToolButton, QMenu, QPlainTextEdit {{ background: {c['Layer_02']}; color: {c['Primary_Text']}; border: 1px solid {c['Border']}; padding: 7px; }}
    QToolButton:checked {{ background: {c['Layer_03']}; border-color: {accent}; color: {accent}; }}
    QToolButton:disabled {{ color: {c['Disabled_Text']}; }}
    QMenu::item:selected {{ background: {accent}; }}
    QToolTip {{ background: {c['Layer_03']}; color: {c['Primary_Text']}; border: 1px solid {c['Border']}; padding: 6px; }}
    ''')
    return c


def label(text,kind=None):
    w=W.QLabel(text)
    if kind:w.setObjectName(kind)
    return w

def button(text,slot,primary=False):
    w=W.QPushButton(text);w.clicked.connect(slot)
    if primary:w.setObjectName('primary')
    return w


def panel(title):
    frame=W.QWidget();frame.setObjectName('surface')
    layout=W.QVBoxLayout(frame);layout.setContentsMargins(12,12,12,12);layout.setSpacing(10)
    layout.addWidget(label(title,'eyebrow'))
    return frame,layout

class Window(W.QMainWindow):
    def __init__(self,project,screenshot=None):
        super().__init__();self.project=project;self.record=None;self.parts=[];self.actor_paths={};self.draft=[];self.jobs=[];self.loading=0;self.light=False;self.screenshot=screenshot
        self.setWindowTitle('CAD-GIT • '+project.config['name']);self.resize(1430,930);self.setMinimumSize(1120,760)
        self.colors=theme(W.QApplication.instance())
        root=W.QWidget();self.setCentralWidget(root);layout=W.QVBoxLayout(root);layout.setContentsMargins(20,18,20,10);layout.setSpacing(14)
        header=W.QHBoxLayout();header.addWidget(label('CAD—GIT','brand'));header.addSpacing(20)
        title=W.QVBoxLayout();title.addWidget(label(project.config['name'],'title'));title.addWidget(label('USD SNAPSHOT HISTORY / ASSEMBLY','eyebrow'));header.addLayout(title);header.addStretch()
        header.addWidget(label('●  LOCAL PROJECT','badge'));header.addWidget(button('Open folder',self.open_folder));header.addWidget(button('Light / dark',self.toggle_theme));layout.addLayout(header)
        # Main workbench: history | geometry | inspector.
        split=W.QSplitter();layout.addWidget(split,1)
        left,left_layout=panel('SOURCE HISTORY');left.setMinimumWidth(250)
        self.history=W.QTreeWidget();self.history.setHeaderHidden(True);self.history.itemClicked.connect(self.history_clicked);left_layout.addWidget(self.history,1)
        self.source_combo=W.QComboBox();self.source_combo.addItems(['rhino','blender','manual']);left_layout.addWidget(self.source_combo)
        left_layout.addWidget(button('Import USD snapshot…',self.ingest_dialog))
        left_layout.addWidget(button('Connect save hooks',self.connect_apps))
        left_layout.addWidget(button('Capture current app',self.capture_app));split.addWidget(left)
        center=W.QWidget();cl=W.QVBoxLayout(center);cl.setContentsMargins(0,0,0,0);cl.setSpacing(8)
        top=W.QHBoxLayout();self.record_title=label('Select a snapshot','title');top.addWidget(self.record_title);top.addStretch();top.addWidget(button('Fit',lambda:self.plotter.reset_camera()));top.addWidget(button('Inspect main',self.load_main));cl.addLayout(top)
        self.subhead=label('Pick geometry in the viewport or scene tree.','muted');cl.addWidget(self.subhead)
        self.plotter=QtInteractor(center,auto_update=False);cl.addWidget(self.plotter.interactor,1)
        self.plotter.set_background('#0F1113');self.plotter.add_axes();self.plotter.enable_mesh_picking(callback=self.pick_actor,use_actor=True,show=False,show_message=False,left_clicking=True)
        footer=W.QHBoxLayout();footer.addWidget(label('INSPECTION VIEW  ·  meters  ·  basic appearance','eyebrow'));footer.addStretch();footer.addWidget(button('Export STL…',self.export_dialog));cl.addLayout(footer)
        split.addWidget(center)
        right,rl=panel('SCENE / PROVENANCE');right.setMinimumWidth(265)
        self.scene=W.QTreeWidget();self.scene.setMinimumHeight(150);self.scene.setHeaderHidden(True);self.scene.itemClicked.connect(self.scene_clicked);rl.addWidget(self.scene,2)
        self.details=W.QTextEdit();self.details.setReadOnly(True);self.details.setMaximumHeight(115);rl.addWidget(self.details)
        rl.addWidget(label('MATERIAL OVERRIDE','eyebrow'));self.material_combo=W.QComboBox();self.material_combo.addItem('Keep source materials',None);rl.addWidget(self.material_combo)
        rl.addWidget(button('+ Add selection to assembly',self.add_selection,True))
        self.issues=label('Source snapshots are immutable. Main changes only when you choose.','muted');self.issues.setWordWrap(True);rl.addWidget(self.issues)
        split.addWidget(right);split.setSizes([270,820,285])
        # A compact temporal lane of source snapshots.
        timeline,tl=panel('RECENT SNAPSHOTS  /  CLICK TO INSPECT');self.lane=W.QHBoxLayout();tl.addLayout(self.lane);layout.addWidget(timeline)
        draft,dl=panel('ASSEMBLY DRAFT  /  MIX GEOMETRY AND MATERIAL REVISIONS')
        self.tray=W.QTableWidget(0,4);self.tray.setHorizontalHeaderLabels(['PIECE / SOURCE PRIM','SOURCE SNAPSHOT','PLACEMENT (m)','MATERIAL']);self.tray.horizontalHeader().setSectionResizeMode(0,W.QHeaderView.Stretch);self.tray.setColumnWidth(1,180);self.tray.setColumnWidth(2,170);self.tray.setColumnWidth(3,180);self.tray.setMaximumHeight(110);self.tray.setSelectionBehavior(W.QAbstractItemView.SelectRows);self.tray.setEditTriggers(W.QAbstractItemView.NoEditTriggers);dl.addWidget(self.tray)
        actions=W.QHBoxLayout();actions.addWidget(button('Remove selected',self.remove_selection));actions.addWidget(button('Move piece…',self.move_piece));actions.addWidget(button('Preview draft',self.preview_draft));actions.addStretch();actions.addWidget(button('Save assembly…',self.save_assembly,True));actions.addWidget(button('Set current as main',self.set_main));actions.addWidget(button('Import into Blender',self.import_blender));dl.addLayout(actions);layout.addWidget(draft)
        self.statusBar().showMessage('Ready • local files only • no automatic native refresh')
        self.refresh()
        draft_path=project.root/'.cadgit/drafts/current.json'
        if draft_path.exists():
            try:self.draft=read_json(draft_path);self.update_tray()
            except Exception:pass
        QtCore.QTimer.singleShot(100,self.load_main)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(1800)

    def job(self,fn,done):
        j=Job(fn);self.jobs.append(j);self.statusBar().showMessage('Working…')
        def complete(value):
            if j in self.jobs:self.jobs.remove(j)
            done(value)
        def failed(error):
            if j in self.jobs:self.jobs.remove(j)
            self.fail(error)
        j.signals.done.connect(complete);j.signals.error.connect(failed);QtCore.QThreadPool.globalInstance().start(j)

    def fail(self,message):
        self.statusBar().showMessage('Issue: '+message);W.QMessageBox.warning(self,'CAD-GIT',message)

    def refresh(self):
        self.history.clear();records=self.project.records();assemblies=self.project.records('assemblies')
        self._record_count=len(records)+len(assemblies)
        sources={}
        for record in records:
            key=record['source']+' / '+record.get('branch','main')
            if key not in sources:
                sources[key]=W.QTreeWidgetItem(self.history,[key.upper()]);sources[key].setExpanded(True)
            item=W.QTreeWidgetItem(sources[key],[record['label']]);item.setData(0,QtCore.Qt.UserRole,record['id']);item.setToolTip(0,record['created_at']+'\n'+record['id'])
        group=W.QTreeWidgetItem(self.history,['SAVED ASSEMBLIES']);group.setExpanded(True)
        for record in assemblies:
            item=W.QTreeWidgetItem(group,[record['label']]);item.setData(0,QtCore.Qt.UserRole,record['id'])
        while self.lane.count():
            item=self.lane.takeAt(0)
            if item.widget():item.widget().deleteLater()
        for r in records[-5:]:
            text=r['source'].upper()+'  /  '+r['id'][-4:]+'\n'+r['label'].split('•')[-1].strip()
            b=button(text,lambda _=False,ref=r['id']:self.load_record(ref));b.setToolTip(r['created_at']);self.lane.addWidget(b)
        self.material_combo.clear();self.material_combo.addItem('Keep source materials',None)
        for m in self.project.records('materials'):self.material_combo.addItem(m['label']+' · '+m['id'][-6:],m['id'])

    def poll(self):
        from .service import status
        count=len(self.project.records())+len(self.project.records('assemblies'))
        if count!=self._record_count:self.refresh()
        errors=list((self.project.root/'.cadgit/inbox').glob('*/error.json'))+list((self.project.root/'.cadgit/inbox').glob('*/failed.json'))
        if errors:self.issues.setText(f'{len(errors)} capture/export issue(s). See .cadgit/inbox for exact errors; history remains intact.')
        self.setWindowTitle('CAD-GIT • '+self.project.config['name']+(' • watching saves' if status(self.project).get('running') else ''))

    def history_clicked(self,item,column):
        ref=item.data(0,QtCore.Qt.UserRole)
        if ref:self.load_record(ref)

    def load_main(self):
        try:self.load_record(os.environ.pop('CADGIT_INITIAL_REF','main'))
        except CadgitError:
            r=self.project.records()
            if r:self.load_record(r[-1]['id'])

    def load_record(self,ref):
        record=self.project.resolve(ref);path=self.project.stage_path(record);self.loading+=1;generation=self.loading
        def show(result):
            if generation!=self.loading:return
            self.record=record;self.parts=result[0];info=result[1]
            self.record_title.setText(record['label']);self.subhead.setText(('Assembly' if record['id'].startswith('assembly_') else record['source'].capitalize()+' snapshot')+' · '+record['id'][-8:]+' · '+str(len(self.parts))+' mesh objects')
            self.scene.clear();nodes={}
            for prim in info['prims']:
                parent='/'.join(prim['path'].split('/')[:-1]);container=nodes.get(parent,self.scene)
                item=W.QTreeWidgetItem(container,[prim['name']+('  ◇' if prim['type']=='Mesh' else '')]);item.setData(0,QtCore.Qt.UserRole,prim['path']);nodes[prim['path']]=item
            self.scene.expandToDepth(1)
            if self.scene.topLevelItemCount():self.scene.setCurrentItem(self.scene.topLevelItem(0))
            self.render(self.parts)
            unsupported=info['unsupported_types']
            self.issues.setText('Basic material preview. '+('Unsupported display types: '+', '.join(unsupported) if unsupported else 'Original USD is retained; rendered mesh is only for inspection.'))
            self.details.setPlainText('ID  '+record['id']+'\n'+record['created_at']+'\n\n'+('Sample data • generated scene' if record.get('metadata',{}).get('sample_data') else 'Source lineage: '+str(record.get('parent') or 'baseline')))
            self.statusBar().showMessage('Snapshot loaded • source data is unchanged')
            if self.screenshot:QtCore.QTimer.singleShot(800,self.save_screenshot)
        self.job(lambda:(meshes(path),stage_info(path)),show)

    def render(self,parts):
        self.plotter.clear();self.actor_paths={}
        for index,p in enumerate(parts):
            mesh=pv.PolyData(p['points'],p['faces'])
            actor=self.plotter.add_mesh(mesh,color=p['color'],smooth_shading=False,show_edges=False,metallic=0.25,roughness=0.5,pbr=True,name='part_'+str(index))
            self.actor_paths[actor.GetAddressAsString('')]=p['path']
        self.plotter.add_axes();self.plotter.view_isometric();self.plotter.reset_camera();self.plotter.render()

    def pick_actor(self,actor):
        path=self.actor_paths.get(actor.GetAddressAsString(''))
        if not path:return
        iterator=W.QTreeWidgetItemIterator(self.scene)
        while iterator.value():
            item=iterator.value()
            if item.data(0,QtCore.Qt.UserRole)==path:self.scene.setCurrentItem(item);self.scene_clicked(item,0);break
            iterator+=1

    def scene_clicked(self,item,column):
        path=item.data(0,QtCore.Qt.UserRole);parts=[p for p in self.parts if p['path']==path or p['path'].startswith(path+'/')]
        self.details.setPlainText(path+'\n\n'+str(len(parts))+' mesh object(s)\n'+(self.record['id'] if self.record else '')+'\n\n'+('\n'.join(sorted({w for p in parts for w in p['warnings']}))))
        for key,actor in self.plotter.actors.items():
            if key.startswith('part_'):
                selected=self.actor_paths.get(actor.GetAddressAsString(''),'').startswith(path)
                actor.prop.show_edges=selected;actor.prop.edge_color='#2B9ED1'
        self.plotter.render()

    def selected_path(self):
        item=self.scene.currentItem()
        return item.data(0,QtCore.Qt.UserRole) if item else None

    def add_selection(self):
        path=self.selected_path()
        if not self.record or not path:return
        sel=Selection(snapshot_id=self.record['id'],prim_path=path,label=path.split('/')[-1],material_revision=self.material_combo.currentData()).model_dump()
        self.draft.append(sel);self.update_tray()

    def update_tray(self):
        self.tray.setRowCount(len(self.draft))
        for row,s in enumerate(self.draft):
            for col,text in enumerate([s['label']+' · '+s['prim_path'],s['snapshot_id'][-10:],str(s.get('translation',[0,0,0])),s.get('material_revision') or 'Source materials']):self.tray.setItem(row,col,W.QTableWidgetItem(str(text)))
        atomic_json(self.project.root/'.cadgit/drafts/current.json',self.draft)

    def remove_selection(self):
        row=self.tray.currentRow()
        if row>=0:self.draft.pop(row);self.update_tray()

    def move_piece(self):
        row=self.tray.currentRow()
        if row<0:return
        text,ok=W.QInputDialog.getText(self,'Piece placement','Translation X, Y, Z in meters:',text=', '.join(map(str,self.draft[row].get('translation',[0,0,0]))))
        if ok:
            try:
                values=[float(x.strip()) for x in text.split(',')]
                if len(values)!=3:raise ValueError('Enter three values')
                self.draft[row]['translation']=values;self.update_tray()
            except ValueError as e:self.fail(str(e))

    def preview_draft(self):
        if not self.draft:return
        draft=json.loads(json.dumps(self.draft))
        def compute():
            parts=[]
            import numpy as np
            for s in draft:
                record=self.project.resolve(s['snapshot_id'])
                for p in meshes(self.project.stage_path(record),s['prim_path']):
                    p['points']=p['points']+np.array(s.get('translation',[0,0,0]));parts.append(p)
            return parts
        def show(parts):
            self.render(parts);self.record=None;self.scene.clear();self.record_title.setText('Assembly draft');self.subhead.setText(f'{len(draft)} selections · unsaved preview · main unchanged');self.statusBar().showMessage('Draft preview • Save assembly to create immutable output')
        self.job(compute,show)

    def save_assembly(self):
        if not self.draft:return
        text,ok=W.QInputDialog.getText(self,'Save assembly','Assembly name:',text='New study')
        if not ok or not text.strip():return
        selections=list(self.draft)
        def done(r):self.refresh();self.load_record(r['id']);self.statusBar().showMessage('Assembly saved. Main remains unchanged until Set current as main.')
        self.job(lambda:assemble(self.project,selections,text.strip()),done)

    def set_main(self):
        if not self.record or not self.record['id'].startswith('assembly_'):return self.fail('Inspect a saved assembly first.')
        try:self.project.set_main(self.record['id']);self.statusBar().showMessage('Main now points to '+self.record['label'])
        except Exception as exc:self.fail(str(exc))

    def ingest_dialog(self):
        path,_=W.QFileDialog.getOpenFileName(self,'Ingest a USD snapshot','','USD files (*.usd *.usda *.usdc *.usdz)')
        if not path:return
        source=self.source_combo.currentText()
        self.job(lambda:self.project.ingest(path,source),lambda r:(self.refresh(),self.load_record(r['id'])))

    def export_dialog(self):
        if self.record_title.text()=='Assembly draft':return self.fail('Save the draft as an assembly before exporting.')
        if not self.record:return
        path,_=W.QFileDialog.getSaveFileName(self,'Export selected geometry as STL',str(self.project.root/'part.stl'),'STL (*.stl)')
        if not path:return
        selection=self.selected_path();ref=self.record['id']
        answer=W.QMessageBox.question(self,'Print export settings','Export authored polygon meshes in millimeters?\n\nSubdivision is exported as the base mesh. Open/nonmanifold geometry is rejected. Shader bump/displacement is not evaluated.\n\nSelection: '+str(selection or 'whole scene'))
        if answer!=W.QMessageBox.Yes:return
        def done(r):self.statusBar().showMessage('STL saved • '+str(r['report']['dimensions'])+' mm');W.QMessageBox.information(self,'Print artifact saved',path+'\n\n'+json.dumps(r['report'],indent=2))
        self.job(lambda:export_stl(self.project,ref,path,selection,allow_base_mesh=True),done)

    def connect_apps(self):
        from .connectors import attach
        from .service import start
        def work():
            results={}
            for app in ['rhino','blender']:
                try:attach(self.project,app);results[app]='save hook connected'
                except Exception as exc:results[app]=str(exc)
            results['service']=start(self.project);return results
        self.job(work,lambda r:W.QMessageBox.information(self,'Save monitoring',json.dumps(r,indent=2)))

    def capture_app(self):
        from .connectors import capture
        from .service import process_inbox
        app=self.source_combo.currentText()
        if app not in ['rhino','blender']:return self.fail('Choose Rhino or Blender first.')
        def work():capture(self.project,app);return process_inbox(self.project)
        self.job(work,lambda n:(self.refresh(),self.statusBar().showMessage(f'Captured {n} snapshot(s)')))

    def import_blender(self):
        if not self.record:return
        if W.QMessageBox.question(self,'Import into Blender','Append this snapshot/assembly into the current Blender scene?\n\nExisting objects stay. Native materials are restored where mapped. The native file is not saved.')!=W.QMessageBox.Yes:return
        from .connectors import restore_blender
        ref=self.record['id'];self.job(lambda:restore_blender(self.project,ref),lambda r:W.QMessageBox.information(self,'Blender import result',json.dumps(r,indent=2)))

    def open_folder(self):QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.project.root)))

    def toggle_theme(self):
        self.light=not self.light;self.colors=theme(W.QApplication.instance(),self.light);self.plotter.set_background(self.colors['Background']);self.plotter.render()

    def save_screenshot(self):
        if not self.screenshot:return
        target=self.screenshot;self.screenshot=None
        self.grab().save(target)


def launch(root,screenshot=None):
    app=W.QApplication.instance() or W.QApplication([])
    app.setApplicationName('CAD-GIT');app.setOrganizationName('CAD-GIT')
    window=Window(Project(root),screenshot);window.show();return app.exec()
