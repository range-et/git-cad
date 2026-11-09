"""File-first workbench: snapshot tabs -> mesh selection -> saved USD assembly."""
from __future__ import annotations
import json, os, uuid, time
from threading import Event
from pathlib import Path
os.environ.setdefault('QT_API','pyside6')
import numpy as np
import pyvista as pv
from PySide6 import QtCore,QtGui,QtWidgets as W
from pyvistaqt import QtInteractor
from vtkmodules.vtkRenderingCore import vtkCellPicker
from .ui import Job,theme,label,button,panel
from .store import Project,CadgitError,read_json,atomic_json
from .usd import meshes,stage_info,assemble,export_stl,open_stage
from .models import Selection
from .viewport_data import prepare_parts
from .history_graph import build_graph
from .history_view import HistoryGraph

# Limit simultaneous scene preparation so opening many tabs does not launch a
# full set of large USD/texture allocations for every CPU core.
VIEWPORT_POOL=QtCore.QThreadPool()
VIEWPORT_POOL.setMaxThreadCount(2)


def tip(widget,text):
    widget.setToolTip(text);return widget

class SnapshotTab(W.QWidget):
    loaded=QtCore.Signal()
    picked=QtCore.Signal(str)
    display_finished=QtCore.Signal()
    def __init__(self,record=None):
        super().__init__();self.record=record;self.closed=False;self.load_state='loading';self.parts=[];self.paths={};self.selected=set();self.info={};self.mode=os.environ.get('CADGIT_VIEWPORT_MODE','Shaded');self.edges=False
        layout=W.QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        self.cancelled=Event();self._prepared=[];self._upload_index=0
        self.upload_timer=QtCore.QTimer(self);self.upload_timer.setInterval(1);self.upload_timer.timeout.connect(self._upload_batch)
        self.load_notice=W.QLabel('Reading USD and preparing geometry / textures…');self.load_notice.setWordWrap(True);layout.addWidget(self.load_notice)
        self.plotter=QtInteractor(self,auto_update=False);layout.addWidget(self.plotter.interactor)
        self.plotter.set_background('#171A1E');self.plotter.add_axes()
        self.picker=vtkCellPicker();self.picker.SetTolerance(.0005);self.picker.PickFromListOn()
        self._press_position=None;self.plotter.installEventFilter(self)
    def eventFilter(self,watched,event):
        if watched is self.plotter and self.load_state=='ready':
            if event.type()==QtCore.QEvent.MouseButtonPress and event.button()==QtCore.Qt.LeftButton:
                self._press_position=event.position().toPoint()
            elif event.type()==QtCore.QEvent.MouseButtonRelease and event.button()==QtCore.Qt.LeftButton:
                start=self._press_position;self._press_position=None
                if start is not None and (event.position().toPoint()-start).manhattanLength()<=4:
                    size=self.plotter.render_window.GetSize();position=event.position()
                    x=position.x()*size[0]/max(self.plotter.width(),1)
                    y=(self.plotter.height()-position.y()-1)*size[1]/max(self.plotter.height(),1)
                    self.picker.Pick(x,y,0,self.plotter.renderer)
                    actor=self.picker.GetActor()
                    path=self.paths.get(actor.GetAddressAsString(''),'') if actor else ''
                    self.picked.emit(path)
        return super().eventFilter(watched,event)
    def display(self,parts,info,prepared):
        self.parts=parts;self.info=info or {};self.plotter.clear();self.paths={};self.material_textures={};self.picker.InitializePickList()
        self._prepared=prepared;self._upload_index=0;self.load_state='loading'
        self.load_notice.setText('Preparing viewport: 0 / '+str(len(parts))+' objects');self.load_notice.show()
        self.upload_timer.start()
    def cancel_load(self):
        self.cancelled.set();self.upload_timer.stop();self._prepared=[];self.display_finished.emit()
    def _upload_batch(self):
        if self.closed or self.cancelled.is_set():self.cancel_load();return
        try:
            deadline=time.monotonic()+.008
            while self._upload_index<len(self._prepared):
                i=self._upload_index;part=self.parts[i];poly,maps=self._prepared[i]
                textures={}
                if maps and len(maps['uv']):
                    for key in ['base_color','orm']:
                        if key not in maps:continue
                        texture=pv.Texture(maps[key]);texture.interpolate=True;texture.mipmap=True
                        texture.SetWrap({'repeat':texture.Repeat,'clamp':texture.ClampToEdge,'black':texture.ClampToBorder,'mirror':texture.MirroredRepeat}[maps['wrap']])
                        texture.SetBorderColor((0,0,0,maps['border_opacity']) if key=='base_color' else maps['orm_border'])
                        texture.SetUseSRGBColorSpace(key=='base_color');textures[key]=texture
                self.material_textures[i]=textures
                actor=self.plotter.add_mesh(poly,color=part['color'],smooth_shading=False,show_edges=False,name='mesh_'+str(i),specular=.35,specular_power=30,render=False,reset_camera=False)
                actor.prop.interpolation='phong'
                for key,texture in textures.items():
                    if key=='base_color':actor.prop.SetBaseColorTexture(texture)
                    elif key=='orm':actor.prop.SetORMTexture(texture)
                self.paths[actor.GetAddressAsString('')]=part['path'];self.picker.AddPickList(actor)
                self._upload_index+=1
                if time.monotonic()>=deadline:break
            self.load_notice.setText('Preparing viewport: '+str(self._upload_index)+' / '+str(len(self.parts))+' objects')
            if self._upload_index<len(self._prepared):return
            self.upload_timer.stop();self._prepared=[]
            self.plotter.add_axes();self.plotter.view_isometric(render=False);self.plotter.reset_camera(render=False)
            self.setup_studio();self.load_state='ready';self.apply_mode();self.load_notice.hide();self.loaded.emit();self.display_finished.emit()
        except Exception as exc:
            self.upload_timer.stop();self._prepared=[];self.load_error(str(exc));self.display_finished.emit()
    def load_error(self,message):
        self.load_state='error';self.load_notice.setText(('Unable to load this version. Click its graph node to retry.' if self.record else 'Unable to load this draft. Click Preview assembly to retry.')+'\n'+str(message));self.load_notice.show()
    def setup_studio(self):
        # clear() removes VTK's light kit as well as actors. Reinstall lights
        # after every file load; relying on the automatic headlight flattens depth.
        self.plotter.remove_all_lights()
        if not self.parts:return
        bounds=np.asarray([bound for part in self.parts for bound in (part.get('_preview_bounds') or [])])
        if not len(bounds):return
        mn=bounds.min(0);mx=bounds.max(0)
        center=(mn+mx)/2;self.scene_scale=max(float(np.linalg.norm(mx-mn)),1e-6)
        for direction,intensity,color in [((-1,-1,2),1.05,'#FFF3E2'),((1,-.4,.6),.45,'#D6E8FF'),((.3,1,1.5),.8,'#FFFFFF')]:
            position=center+np.array(direction)*self.scene_scale
            self.plotter.add_light(pv.Light(position=position,focal_point=center,intensity=intensity,color=color,positional=False))
        # A neutral studio environment provides broad reflections and fill for
        # metallic surfaces, which otherwise go dark between directional lights.
        yy,xx=np.mgrid[0:128,0:256]
        environment=np.zeros((128,256,3),dtype=np.float64)+np.array([105.,116.,132.])
        for x,y,sx,sy,power in [(65,34,25,18,125),(194,42,37,22,85)]:
            softbox=np.exp(-(((xx-x)/sx)**2+((yy-y)/sy)**2)/2)
            environment+=softbox[:,:,None]*power
        environment*=np.linspace(1.0,.65,128)[:,None,None]
        self.environment=pv.Texture(np.ascontiguousarray(np.clip(environment,0,255).astype(np.uint8)))
        self.environment.mipmap=True;self.environment.interpolate=True
        self.plotter.set_environment_texture(self.environment,is_srgb=True,show_background=False)
        self._studio_mode=None
        self.plotter.enable_anti_aliasing('fxaa')
    def apply_mode(self):
        if self.load_state!='ready':return
        rendered=self.mode=='Rendered preview'
        if getattr(self,'_studio_mode',None)!=self.mode:
            self.plotter.set_background('#202731',top='#424D5B')
            if rendered and self.parts:
                self.plotter.enable_ssao(radius=self.scene_scale*.10,bias=self.scene_scale*.001,kernel_size=128,blur=True)
            else:self.plotter.disable_ssao()
            self._studio_mode=self.mode
        for name,actor in self.plotter.actors.items():
            if not name.startswith('mesh_'):continue
            prop=actor.prop
            prop.style='wireframe' if self.mode=='Wireframe' else 'surface'
            prop.interpolation='pbr' if rendered else 'phong'
            index=int(name.split('_')[-1]);part=self.parts[index];textures=self.material_textures.get(index,{})
            prop.color='white' if rendered and 'base_color' in textures else part['color']
            prop.opacity=0.20 if self.mode=='X-ray' else (1. if rendered and 'base_color' in textures else part.get('opacity',1.))
            prop.metallic=(1. if 'orm' in textures else part.get('metallic',.0)) if rendered else 0
            prop.roughness=1. if rendered and 'orm' in textures else part.get('roughness',.4)
            prop.ambient=.16;prop.diffuse=.82;prop.specular=.28;prop.specular_power=35
            prop.lighting=self.mode!='Wireframe'
            path=self.paths.get(actor.GetAddressAsString(''),'')
            active=any(path==p or path.startswith(p+'/') for p in self.selected)
            prop.show_edges=(self.edges or active) and self.mode!='Wireframe'
            prop.edge_color='#55C4F3' if active else '#303943'
            prop.line_width=2 if active else 1
        self.plotter.render()
    def fit(self,selection=False):
        if self.load_state!='ready':return
        if selection and self.selected:
            pts=[p['points'] for p in self.parts if any(p['path']==x or p['path'].startswith(x+'/') for x in self.selected)]
            if pts:
                p=np.concatenate(pts);mn=p.min(0);mx=p.max(0)
                self.plotter.reset_camera(bounds=[mn[0],mx[0],mn[1],mx[1],mn[2],mx[2]]);return
        self.plotter.reset_camera()

class Window(W.QMainWindow):
    def __init__(self,project,screenshot=None):
        super().__init__();self.project=project;self._closing=False;self._saving_assembly=False;self.jobs=[];self.draft=[];self.tabs_by_id={};self.light=False;self.screenshot=screenshot;self.latest_assembly=None
        self.setWindowTitle('CAD-GIT • '+project.config['name']);self.resize(1470,960);self.setMinimumSize(1000,640);self.colors=theme(W.QApplication.instance())
        root=W.QWidget();self.setCentralWidget(root);layout=W.QVBoxLayout(root);layout.setContentsMargins(16,14,16,8);layout.setSpacing(10)
        header=W.QHBoxLayout();header.addWidget(label('CAD—GIT','brand'));header.addSpacing(18);header.addWidget(label(project.config['name'],'title'));header.addStretch()
        self.add_usd_button=tip(button('+ Add USD file…',self.ingest_dialog),'Record a whole USD file as an immutable version. Its meshes can then be selected in a tab.');header.addWidget(self.add_usd_button)
        self.watch_button=tip(button('Watch native saves…',self.connect_apps),'Attach the installed application adapters. Normal native saves create full USD snapshots.');header.addWidget(self.watch_button)
        self.open_menu=W.QToolButton();self.open_menu.setText('Open with…');self.open_menu.setPopupMode(W.QToolButton.InstantPopup);tip(self.open_menu,'Create a new native file from the current USD. Applications do not need to understand CAD-GIT history.');header.addWidget(self.open_menu)
        header.addWidget(tip(button('Settings',self.settings),'Configure external application targets and the light/dark theme.'));layout.addLayout(header)
        self.workbench_splitter=W.QSplitter(QtCore.Qt.Vertical);self.workbench_splitter.setChildrenCollapsible(False);layout.addWidget(self.workbench_splitter,1)
        splitter=W.QSplitter(QtCore.Qt.Horizontal);self.columns_splitter=splitter;splitter.setChildrenCollapsible(False);self.workbench_splitter.addWidget(splitter)
        left,ll=panel('VERSIONS & BRANCHES');left.setMinimumWidth(220)
        self.search=W.QLineEdit();self.search.setPlaceholderText('Find version, branch, file…');tip(self.search,'Highlight matching commits without hiding their ancestry.');self.search.textChanged.connect(self.filter_history);ll.addWidget(self.search)
        self.search_summary=label('','muted');self.search_summary.setWordWrap(True);self.search_summary.hide();ll.addWidget(self.search_summary)
        self.history=HistoryGraph();self.history.openRequested.connect(self.open_record);self.history.menuRequested.connect(self.history_menu);self.history.matchesChanged.connect(self.search_matches);self.search.returnPressed.connect(self.history.open_selected);ll.addWidget(self.history,1)
        self.search_shortcuts=[]
        for sequence,delta in [('F3',1),('Shift+F3',-1)]:
            shortcut=QtGui.QShortcut(QtGui.QKeySequence(sequence),self);shortcut.activated.connect(lambda d=delta:self.history.navigate(d));self.search_shortcuts.append(shortcut)
        self.graph_warning=label('','muted');self.graph_warning.setWordWrap(True);self.graph_warning.hide();ll.addWidget(self.graph_warning)
        legend=label('● save   ◇ assembly    ┄ imported / composed','eyebrow');legend.setWordWrap(True);ll.addWidget(legend)
        graph_actions=W.QHBoxLayout();graph_actions.addWidget(tip(button('Branch…',self.branch_selected),'Create a new branch from the selected snapshot.'));graph_actions.addWidget(tip(button('Version…',self.name_selected),'Bookmark the selected saved state with a permanent version name.'));ll.addLayout(graph_actions)
        ll.addWidget(tip(button('Refresh history',self.refresh),'Reload commits, branch heads, and assembly ancestry.'));splitter.addWidget(left)
        center=W.QWidget();cl=W.QVBoxLayout(center);cl.setContentsMargins(0,0,0,0);cl.setSpacing(8)
        modes=W.QToolBar();modes.setMovable(False);self.mode_buttons={};group=QtGui.QActionGroup(self);group.setExclusive(True)
        for text,explanation in [('Wireframe','Show polygon edges without filled faces.'),('Shaded','Solid geometry with lighting and smooth shading.'),('Rendered preview','Studio lights, PBR surface shading and ambient occlusion. Native Cycles graphs render in Blender.'),('X-ray','Translucent surfaces for inspecting overlapping geometry.')]:
            action=modes.addAction(text);action.setCheckable(True);action.setChecked(text=='Shaded');action.setToolTip(explanation);group.addAction(action);self.mode_buttons[text]=action;action.triggered.connect(lambda _=False,m=text:self.mode_changed(m))
        modes.addSeparator();self.edge_check=modes.addAction('Edges');self.edge_check.setCheckable(True);self.edge_check.setToolTip('Overlay polygon edges on shaded surfaces.');self.edge_check.toggled.connect(self.edges_changed)
        modes.addSeparator();modes.addAction('Frame all',lambda:self.frame(False));modes.addAction('Frame selected',lambda:self.frame(True));cl.addWidget(modes)
        file_actions=W.QToolBar();file_actions.setMovable(False)
        self.view_menu=W.QToolButton();self.view_menu.setText('View…');self.view_menu.setPopupMode(W.QToolButton.InstantPopup);view_options=W.QMenu(self.view_menu)
        for action in modes.actions():view_options.addAction(action)
        self.view_menu.setMenu(view_options);self.view_menu.setToolTip('All display and framing controls, including those hidden when the window is narrow.');file_actions.addWidget(self.view_menu)
        self.export_action=file_actions.addAction('Export STL…',self.export_stl_dialog);self.export_action.setToolTip('Export the active saved tab, not the assembly draft below.')
        self.brep_action=file_actions.addAction('Prepare B-rep job…',self.prepare_brep_dialog);self.brep_action.setToolTip('Prepare separate mesh inputs for optional DualBrep reconstruction. No inference or STEP is produced yet.')
        self.main_action=file_actions.addAction('Set as main',self.set_main);self.main_action.setToolTip('Select the assembly in the current tab as main.');cl.addWidget(file_actions)
        for toolbar in [modes,file_actions]:
            extension=toolbar.findChild(W.QToolButton,'qt_toolbar_ext_button')
            if extension:
                extension.setToolTip('More controls')
        self.tabs=W.QTabWidget();self.tabs.setTabsClosable(True);self.tabs.setMovable(True);self.tabs.tabCloseRequested.connect(self.close_tab);self.tabs.currentChanged.connect(self.tab_changed);cl.addWidget(self.tabs,1)
        addbar=W.QHBoxLayout();self.selection_label=label('Open a version, then select its meshes.','muted');self.selection_label.setWordWrap(True);addbar.addWidget(self.selection_label,1);self.add_button=tip(button('+ Add selected to assembly',self.add_selection,True),'Add selected meshes or a selected subtree from the active USD tab. Original files are never changed.');addbar.addWidget(self.add_button);cl.addLayout(addbar)
        self.notice=label('1  Open a version   →   2  Select geometry   →   3  Add pieces   →   4  Save USD','eyebrow');self.notice.setWordWrap(True);cl.addWidget(self.notice);splitter.addWidget(center)
        right,rl=panel('OBJECTS IN CURRENT FILE');right.setMinimumWidth(220)
        self.scene=W.QTreeWidget();self.scene.setHeaderHidden(True);self.scene.setSelectionMode(W.QAbstractItemView.ExtendedSelection);self.scene.itemSelectionChanged.connect(self.scene_selected);tip(self.scene,'Select a mesh or a whole group. Ctrl/Cmd-click selects multiple objects.');self.inspector_splitter=W.QSplitter(QtCore.Qt.Vertical);self.inspector_splitter.setChildrenCollapsible(False);self.inspector_splitter.addWidget(self.scene);rl.addWidget(self.inspector_splitter,1)
        self.details=W.QTextEdit();self.details.setReadOnly(True);self.details.setMinimumHeight(55);self.inspector_splitter.addWidget(self.details);self.inspector_splitter.setSizes([350,130])
        rl.addWidget(label('MATERIAL FOR ADDED PIECES','eyebrow'));self.material_combo=W.QComboBox();tip(self.material_combo,'Keep source materials, or bind a versioned project material when adding the selection.');rl.addWidget(self.material_combo)
        self.issue_label=label('Full files are versioned. Geometry is selected only when making an assembly.','muted');self.issue_label.setWordWrap(True);rl.addWidget(self.issue_label);splitter.addWidget(right);splitter.setSizes([390,750,280])
        self.preview_notes_button=tip(button('Preview notes…',self.show_preview_notes),'Read all material, texture and geometry preview warnings.');self.preview_notes_button.hide();rl.addWidget(self.preview_notes_button)
        tray,tl=panel('NEW ASSEMBLY');self.table=W.QTableWidget(0,4);self.table.setHorizontalHeaderLabels(['SELECTED GEOMETRY','FROM FILE / VERSION','PLACEMENT (m)','MATERIAL']);self.table.horizontalHeader().setSectionResizeMode(0,W.QHeaderView.Stretch);self.table.setColumnWidth(1,230);self.table.setColumnWidth(2,150);self.table.setColumnWidth(3,180);self.table.setMinimumHeight(55);self.table.setSelectionBehavior(W.QAbstractItemView.SelectRows);self.table.setEditTriggers(W.QAbstractItemView.NoEditTriggers);tl.addWidget(self.table)
        actions=W.QHBoxLayout()
        self.remove_button=tip(button('Remove',self.remove_piece),'Remove the selected draft piece. No history is deleted.');actions.addWidget(self.remove_button)
        self.move_button=tip(button('Move…',self.move_piece),'Set the selected draft piece offset in meters.');actions.addWidget(self.move_button)
        self.preview_button=tip(button('Preview assembly',self.preview_draft),'Inspect this draft in a separate tab.');actions.addWidget(self.preview_button)
        self.clear_button=tip(button('New assembly…',self.new_assembly),'Start an empty draft. Saved assemblies remain in history.');actions.addWidget(self.clear_button)
        actions.addStretch();self.save_button=tip(button('Save assembly as USD…',self.save_assembly,True),'Save the draft pieces below as a new USD assembly.');actions.addWidget(self.save_button)
        self.table.itemSelectionChanged.connect(self.update_actions);tl.addLayout(actions);self.workbench_splitter.addWidget(tray);self.workbench_splitter.setSizes([650,210])
        for divider in [self.workbench_splitter,self.columns_splitter,self.inspector_splitter]:
            divider.setHandleWidth(9)
            for index in range(1,divider.count()):divider.handle(index).setToolTip('Drag to resize panels')
        self.restore_layout()
        from .library_ui import LibraryWidget
        index=layout.indexOf(self.workbench_splitter);layout.removeWidget(self.workbench_splitter)
        self.workspace_tabs=W.QTabWidget();self.geometry_page=W.QWidget();geometry_layout=W.QVBoxLayout(self.geometry_page);geometry_layout.setContentsMargins(0,0,0,0);geometry_layout.addWidget(self.workbench_splitter)
        self.library_browser=LibraryWidget(project);self.library_browser.materialSelected.connect(self.use_library_material);self.library_browser.changed.connect(self.refresh)
        self.workspace_tabs.addTab(self.geometry_page,'Geometry');self.workspace_tabs.addTab(self.library_browser,'Materials && Assets');layout.insertWidget(index,self.workspace_tabs,1);self.workspace_tabs.currentChanged.connect(self.workspace_changed)
        settings=self.layout_settings();library_state=settings.value('library_splitter')
        if library_state is not None:self.library_browser.splitter.restoreState(library_state)
        self.workspace_tabs.setCurrentIndex(1 if os.environ.get('CADGIT_WORKSPACE')=='library' else int(settings.value('workspace',0)))
        self.statusBar().showMessage('Ready • double-click any history version to open it in a tab')
        self.refresh();self.reload_open_menu()
        file=project.root/'.cadgit/drafts/current.json'
        draft_error=None
        if file.exists():
            try:
                data=read_json(file)
                if not isinstance(data,list):raise ValueError('Draft must be a list of assembly selections')
                self.draft=[Selection.model_validate(value).model_dump() for value in data]
            except Exception as exc:
                # Keep the original in place and preserve a separate recovery copy
                # before any later edit can replace current.json.
                backup=file.with_name('unreadable_'+uuid.uuid4().hex+'.json')
                try:backup.write_bytes(file.read_bytes());draft_error='Saved draft could not be loaded. Original preserved at '+str(backup)
                except OSError:draft_error='Saved draft could not be loaded; it has not been overwritten: '+str(file)
                self.draft=[]
        self.update_tray(persist=draft_error is None)
        if draft_error:
            warning=W.QLabel('Draft recovery needed. Original data has been preserved.');warning.setToolTip(draft_error);warning.setWordWrap(True);layout.insertWidget(1,warning);self.statusBar().showMessage(draft_error)
        QtCore.QTimer.singleShot(100,self.open_initial)
        self.timer=QtCore.QTimer(self);self.timer.timeout.connect(self.poll);self.timer.start(1600)
    def workspace_changed(self,index):
        geometry=index==0
        for widget in [self.add_usd_button,self.watch_button,self.open_menu]:widget.setVisible(geometry)
        if not geometry:self.library_browser.refresh()
    def use_library_material(self,revision):
        self.refresh()
        value={'library_material_revision':revision}
        index=self.material_combo.findData(value)
        if index<0:
            from .library import Library
            record=Library(self.project).get(revision);self.material_combo.addItem(record['label']+' • r'+str(record['revision_number']),value);index=self.material_combo.count()-1
        self.material_combo.setCurrentIndex(index);self.workspace_tabs.setCurrentIndex(0);self.statusBar().showMessage('Material selected for new pieces only; existing draft pieces remain pinned.')
    def layout_settings(self):
        settings=QtCore.QSettings('CAD-GIT','Workbench');settings.beginGroup(self.project.config['id']);return settings
    def restore_layout(self):
        settings=self.layout_settings()
        if settings.contains('geometry'):self.restoreGeometry(settings.value('geometry'))
        for name in ['workbench','columns','inspector']:
            state=settings.value(name)
            if state is not None:getattr(self,name+'_splitter').restoreState(state)
    def closeEvent(self,event):
        self._closing=True
        self.library_browser.shutdown()
        for cancelled in getattr(self,'_brep_preparations',[]):cancelled.set()
        for index in range(self.tabs.count()):self.tabs.widget(index).cancel_load()
        if hasattr(self,'timer'):self.timer.stop()
        settings=self.layout_settings();settings.setValue('geometry',self.saveGeometry())
        for name in ['workbench','columns','inspector']:settings.setValue(name,getattr(self,name+'_splitter').saveState())
        settings.setValue('workspace',self.workspace_tabs.currentIndex());settings.setValue('library_splitter',self.library_browser.splitter.saveState())
        settings.sync();super().closeEvent(event)
    def job(self,fn,done,on_error=None,pool=None):
        if self._closing:return
        j=Job(fn);self.jobs.append(j);self.statusBar().showMessage('Working…')
        def finish():
            if j in self.jobs:self.jobs.remove(j)
        def complete(value):
            finish()
            if self._closing:return
            try:done(value)
            except Exception as exc:failed(str(exc))
        def failed(error):
            finish()
            if self._closing:return
            try:
                if on_error and on_error(error) is False:return
            except Exception as exc:error=str(error)+'\n'+str(exc)
            self.update_actions();self.fail(error)
        j.signals.done.connect(complete);j.signals.error.connect(failed);(pool or QtCore.QThreadPool.globalInstance()).start(j)
    def fail(self,message):
        if not self._closing:self.statusBar().showMessage(str(message));W.QMessageBox.warning(self,'CAD-GIT',str(message))
    def tab_is_open(self,tab):
        if self._closing or getattr(tab,'closed',False):return False
        try:return self.tabs.indexOf(tab)>=0
        except RuntimeError:return False
    def update_actions(self):
        if self._closing or not hasattr(self,'tabs') or not hasattr(self,'save_button'):return
        tab=self.current();ready=tab is not None and tab.load_state=='ready';saved=ready and tab.record is not None
        self.open_menu.setEnabled(bool(saved));self.export_action.setEnabled(bool(saved));self.main_action.setEnabled(bool(saved and tab.record['id'].startswith('assembly_')))
        self.brep_action.setEnabled(bool(saved))
        self.add_button.setEnabled(bool(saved and tab.selected));self.material_combo.setEnabled(bool(saved))
        self.save_button.setEnabled(bool(self.draft) and not self._saving_assembly);self.preview_button.setEnabled(bool(self.draft));self.clear_button.setEnabled(bool(self.draft));self.remove_button.setEnabled(self.table.currentRow()>=0);self.move_button.setEnabled(self.table.currentRow()>=0)
    def current(self):return self.tabs.currentWidget()
    def open_initial(self):
        if self._closing:return
        ref=os.environ.pop('CADGIT_INITIAL_REF',None)
        if not ref:
            try:ref=self.project.resolve('main')['id']
            except Exception:
                records=self.project.records();ref=records[-1]['id'] if records else None
        if ref:self.open_record(ref)
    def native_name(self,r):
        path=r.get('metadata',{}).get('native_path') or r.get('metadata',{}).get('import_path')
        return Path(path).name if path else r.get('label') or 'USD snapshot'
    def refresh(self):
        records=self.project.records(strict=False);assemblies=self.project.records('assemblies',strict=False);self._count=len(records)+len(assemblies)
        config=read_json(self.project.root/'cadgit.json')
        main=self.project.root/'main/current.json';main_id=read_json(main).get('assembly_id') if main.exists() else None
        graph=build_graph(records,assemblies,config,main_id)
        materials=self.project.records('materials',strict=False)
        issues=[issue for group in self.project.record_issues.copy().values() for issue in group]
        if issues:graph['warnings'].append(str(len(issues))+' unreadable records preserved; other history remains available')
        self.history.set_graph(graph)
        self.history.setToolTip('Click a commit to open it. Up/Down navigate; Enter opens. Right-click for branch and version actions.'+('\nHistory warning: '+'; '.join(graph['warnings']) if graph.get('warnings') else ''))
        self.graph_warning.setText('History needs attention: '+'; '.join(graph.get('warnings',[])));self.graph_warning.setVisible(bool(graph.get('warnings')))
        self._history_signature=self.history_signature()
        material=self.material_combo.currentData();self.material_combo.clear();self.material_combo.addItem('Keep source materials',None)
        for m in materials:self.material_combo.addItem('Captured shader: '+m['label']+' · '+m['id'][-6:],m['id'])
        from .library import Library
        for m in Library(self.project).records():
            if m['kind']=='material':self.material_combo.addItem(m['label']+' • r'+str(m['revision_number']),{'library_material_revision':m['id']})
        index=self.material_combo.findData(material)
        if index>=0:self.material_combo.setCurrentIndex(index)
        self.filter_history()
        if hasattr(self,'library_browser') and self.workspace_tabs.currentIndex()==1:self.library_browser.refresh()
    def history_signature(self):
        files=[self.project.root/'cadgit.json',self.project.root/'main/current.json',self.project.root/'library/revisions',self.project.root/'materials']
        return (len(self.project.records(strict=False)),len(self.project.records('assemblies',strict=False)),*(p.stat().st_mtime_ns if p.exists() else 0 for p in files))
    def poll(self):
        if self._closing:return
        try:
            if self.history_signature()!=self._history_signature:self.refresh()
        except Exception as exc:self.statusBar().showMessage('History refresh failed: '+str(exc))
    def search_matches(self,count):
        self.search_summary.setVisible(bool(self.search.text().strip()));self.search_summary.setText(str(count)+' matching versions • Enter to open, F3 for next')
    def filter_history(self):self.history.set_query(self.search.text())
    def selected_record(self):
        ref=self.history.selected_ref
        tab=self.current()
        return self.project.resolve(ref) if ref else tab.record if tab else None
    def branch_selected(self):
        r=self.selected_record()
        if not r or 'source' not in r:return self.fail('Select a source save in the graph to branch from.')
        self.create_branch(r)
    def name_selected(self):
        r=self.selected_record()
        if r:self.name_version(r)
        else:self.fail('Select a saved version in the graph first.')
    def name_version(self,r):
        name,ok=W.QInputDialog.getText(self,'Name version','Version name:',text=r['label'])
        if ok and name.strip():
            try:self.project.name_version(r['id'],name.strip());self.refresh()
            except Exception as exc:self.fail(str(exc))
    def history_menu(self,ref,pos):
        r=self.project.resolve(ref);menu=W.QMenu(self)
        menu.addAction('Open version in tab',lambda:self.open_record(ref))
        menu.addAction('Name version…',lambda:self.name_version(r))
        if 'source' in r:
            menu.addAction('Create branch from this version…',lambda:self.create_branch(r))
            heads=next((n['refs'] for n in self.history.graph['nodes'] if n['id']==ref),[])
            branches={(h['source'],h['branch']) for h in heads if h['kind']=='head'} or {(r['source'],r.get('branch','main'))}
            for source,branch in sorted(branches):menu.addAction('Use '+source+'/'+branch+' for new saves',lambda _=False,s=source,b=branch:self.activate_branch(s,b))
        if r['id'].startswith('assembly_'):menu.addAction('Set as main',lambda:(self.project.set_main(ref),self.refresh()))
        menu.addAction('View lineage…',lambda:self.show_lineage(r))
        menu.addAction('Copy version ID',lambda:W.QApplication.clipboard().setText(ref));menu.exec(pos)
    def show_lineage(self,r):
        dialog=W.QDialog(self);dialog.setWindowTitle('Lineage • '+r['label']);dialog.resize(750,440);layout=W.QVBoxLayout(dialog)
        layout.addWidget(label(r['label'],'title'));layout.addWidget(label(r['id'],'muted'))
        layout.addWidget(label('Double-click a source to open its whole file version.','muted'))
        entries=W.QListWidget();layout.addWidget(entries)
        links=[]
        if r.get('parent'):links.append(('Previous save',r['parent'],''))
        origin=r.get('metadata',{}).get('imported_from')
        if origin:links.append(('Imported from',origin,''))
        for selection in r.get('selections',[]):links.append(('Assembly piece',selection['snapshot_id'],selection['prim_path']))
        for role,ref,prim in links:
            try:source=self.project.resolve(ref);title=source['label']
            except Exception:title='Unavailable source'
            item=W.QListWidgetItem(role+' • '+title+'\n'+ref+('\n'+prim if prim else ''));item.setData(QtCore.Qt.UserRole,ref);entries.addItem(item)
        if not links:entries.addItem('Initial imported snapshot: no recorded upstream version.')
        def follow(item):
            ref=item.data(QtCore.Qt.UserRole)
            if ref:dialog.accept();self.open_record(ref)
        entries.itemDoubleClicked.connect(follow)
        close=W.QDialogButtonBox(W.QDialogButtonBox.Close);close.rejected.connect(dialog.reject);layout.addWidget(close);dialog.exec()
    def activate_branch(self,source,name):
        try:self.project.branch(source,name,activate=True);self.refresh();self.statusBar().showMessage('New '+source+' saves use '+name+'. Open an old version with Open with to resume its contents.')
        except Exception as exc:self.fail(str(exc))
    def create_branch(self,r):
        name,ok=W.QInputDialog.getText(self,'New source branch','Branch name:',text='exploration')
        if ok and name:
            try:self.project.branch(r['source'],name,r['id'],activate=True);self.refresh();self.statusBar().showMessage('Capture branch: '+r['source']+'/'+name+'. To resume this historical geometry, use Open with to create a new working file.')
            except Exception as e:self.fail(str(e))
    def open_record(self,ref):
        if self._closing:return
        try:r=self.project.resolve(ref)
        except Exception as exc:return self.fail(str(exc))
        self.history.select_ref(r['id'])
        tab=self.tabs_by_id.get(r['id'])
        if tab is not None:
            self.tabs.setCurrentWidget(tab)
            if tab.load_state!='error':return
            tab.cancelled.clear();tab.load_state='loading';tab.load_notice.setText('Retrying version load…');tab.load_notice.show()
        else:
            tab=SnapshotTab(r);tab.picked.connect(self.pick_path);self.tabs_by_id[r['id']]=tab
            name=(r['label'] if r['id'].startswith('assembly_') else self.native_name(r))+' · '+r['id'][-5:]
            idx=self.tabs.addTab(tab,name);self.tabs.setTabToolTip(idx,r['label']+'\n'+r['created_at']);self.tabs.setCurrentWidget(tab)
        self.update_actions();path=self.project.stage_path(r)
        def done(data):
            if not self.tab_is_open(tab):return
            self.present_tab(tab,data[0],data[1],data[2])
        def failed(error):
            if not self.tab_is_open(tab):return False
            tab.load_error(error)
        def work():
            if tab.cancelled.is_set():return None
            verification=self.project.verify(r['id'])
            if not verification['ok']:raise CadgitError('Snapshot integrity check failed: '+'; '.join(verification['errors']))
            if tab.cancelled.is_set():return None
            parts=meshes(path,include_textures=True)
            return parts,stage_info(path),prepare_parts(parts,tab.cancelled)
        self.job(work,done,failed,pool=VIEWPORT_POOL)
    def present_tab(self,tab,parts,info,prepared):
        # Track GUI upload as work too, so actions/tests cannot race a half scene.
        self.jobs.append(tab)
        def finished():
            tab.display_finished.disconnect(finished)
            if tab in self.jobs:self.jobs.remove(tab)
            if not self.tab_is_open(tab):return
            if not tab.record:self.mark_preview_state(tab)
            self.tab_changed()
            self.statusBar().showMessage('Select meshes to add to an assembly.' if tab.load_state=='ready' else 'Viewport load failed; retry this version.')
            if self.screenshot and tab.load_state=='ready':QtCore.QTimer.singleShot(600,self.save_screenshot)
        tab.display_finished.connect(finished)
        try:tab.display(parts,info,prepared)
        except Exception:
            finished();raise
    def prepare_brep_dialog(self):
        tab=self.current()
        if not tab or not tab.record or tab.load_state!='ready':return
        # Freeze identity and selection before opening a dialog or starting work.
        ref=tab.record['id'];selected=sorted(tab.selected)
        count=sum(not selected or any(p['path']==x or p['path'].startswith(x+'/') for x in selected) for p in tab.parts)
        dialog=W.QDialog(self);dialog.setWindowTitle('Prepare B-rep reconstruction inputs');dialog.resize(650,560)
        layout=W.QVBoxLayout(dialog)
        text=W.QLabel('Saved version: '+ref+'\n'+str(count)+' mesh objects selected')
        text.setTextFormat(QtCore.Qt.PlainText);text.setWordWrap(True);layout.addWidget(text)
        paths=W.QPlainTextEdit();paths.setReadOnly(True);paths.setPlainText('\n'.join(selected) if selected else 'Whole saved scene');paths.setMaximumHeight(120);layout.addWidget(paths)
        note=W.QLabel('Preparation only: saves per-part PLY inputs, units, placement and lineage. No STEP is created. Optional inference requires a compatible CUDA runtime and model checkpoints; execution is not enabled in this release.\n\nReconstruction fits new surfaces. It does not recover original NURBS control points or modeling history.')
        note.setWordWrap(True);note.setSizePolicy(W.QSizePolicy.Preferred,W.QSizePolicy.Minimum);layout.addWidget(note)
        split=W.QCheckBox('Split disconnected components into separate reconstruction parts');layout.addWidget(split)
        warning=W.QLabel('Leave unchecked to reject disconnected meshes. Splitting nested shells can change the meaning of cavities or hollow bodies.');warning.setWordWrap(True);layout.addWidget(warning)
        base=W.QCheckBox('Allow authored base polygons when USD requests subdivision');layout.addWidget(base)
        runtime=button('Check optional CUDA runtime…',lambda:None);layout.addWidget(runtime)
        def check_runtime():
            from .brep import runtime_status
            runtime.setEnabled(False)
            def show(value):
                runtime.setEnabled(True)
                if dialog.isVisible():W.QMessageBox.information(dialog,'Optional runtime',json.dumps(value,indent=2))
            self.job(runtime_status,show,lambda error:runtime.setEnabled(True))
        runtime.clicked.connect(check_runtime)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Ok|W.QDialogButtonBox.Cancel);buttons.button(W.QDialogButtonBox.Ok).setText('Prepare inputs');layout.addWidget(buttons)
        buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject)
        if dialog.exec()!=W.QDialog.Accepted:return
        split_components=split.isChecked();allow_base_mesh=base.isChecked()
        from .brep import prepare_job
        cancel=Event();self._brep_preparations=getattr(self,'_brep_preparations',[]);self._brep_preparations.append(cancel)
        progress=W.QProgressDialog('Preparing B-rep inputs. No model inference is running.','Cancel',0,0,self)
        progress.setWindowTitle('Preparing job');progress.setMinimumDuration(0);progress.setAutoClose(False);progress.canceled.connect(cancel.set);progress.show()
        def finish():
            progress.canceled.disconnect(cancel.set)
            progress.close()
            if cancel in self._brep_preparations:self._brep_preparations.remove(cancel)
        def done(result):
            finish();path=result['_directory']
            self.statusBar().showMessage('B-rep job prepared; no STEP generated. '+path)
            message=W.QMessageBox(self);message.setWindowTitle('B-rep job prepared');message.setTextFormat(QtCore.Qt.PlainText)
            message.setText('Inputs and lineage saved. No inference has run and no STEP exists yet.\n\n'+path)
            reveal=message.addButton('Reveal job folder',W.QMessageBox.ActionRole);message.addButton(W.QMessageBox.Close);message.exec()
            if message.clickedButton() is reveal:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        def failed(error):
            finish()
            if cancel.is_set():self.statusBar().showMessage('B-rep input preparation cancelled.');return False
        self.job(lambda:prepare_job(self.project,ref,selected,split_components,allow_base_mesh,cancel),done,failed)
    def close_tab(self,index):
        tab=self.tabs.widget(index)
        if tab is None:return
        tab.closed=True;tab.cancel_load()
        if tab.record:self.tabs_by_id.pop(tab.record['id'],None)
        self.tabs.removeTab(index);tab.plotter.close();tab.deleteLater();self.update_actions()
    def tab_changed(self,*_):
        tab=self.current();self.scene.blockSignals(True);self.scene.clear()
        if not tab:self.scene.blockSignals(False);self.details.clear();self.selection_label.setText('Open a version to select geometry.');self.issue_label.setText('Open a version to inspect geometry and materials.');self.preview_notes_button.hide();self.update_actions();return
        nodes={}
        for prim in tab.info.get('prims',[]):
            parent='/'.join(prim['path'].split('/')[:-1]);item=W.QTreeWidgetItem(nodes.get(parent,self.scene),[prim['name']]);item.setData(0,QtCore.Qt.UserRole,prim['path']);item.setToolTip(0,prim['path']+'\n'+prim['type']);nodes[prim['path']]=item
            if prim['path'] in tab.selected:item.setSelected(True)
        self.scene.expandToDepth(2);self.scene.blockSignals(False)
        for name,b in self.mode_buttons.items():b.setChecked(name==tab.mode)
        self.edge_check.blockSignals(True);self.edge_check.setChecked(tab.edges);self.edge_check.blockSignals(False)
        if tab.record:
            self.history.select_ref(tab.record['id'])
            r=tab.record;self.details.setPlainText(self.native_name(r)+'\n'+r['label']+'\nVersion '+r['id']+'\n'+r['created_at']+'\n\n'+str(len(tab.parts))+' mesh objects in this file'+('\nImported from '+r['metadata']['imported_from'] if r.get('metadata',{}).get('imported_from') else '')+'\nRight-click history → View lineage')
        else:self.details.setPlainText(('Outdated assembly preview — preview again to see current draft.' if getattr(tab,'preview_stale',False) else 'Unsaved assembly preview')+'\n'+str(len(tab.parts))+' mesh objects\nSave assembly as USD saves the current draft below.'+('\n'+'\n'.join(getattr(tab,'preview_notes',[])) if getattr(tab,'preview_notes',[]) else ''))
        warnings=self.preview_notes(tab)
        self.issue_label.setText('Rendered preview supports image maps. Native shaders use their application.')
        self.preview_notes_button.setText('Preview notes ('+str(len(warnings))+')…');self.preview_notes_button.setVisible(bool(warnings));self.preview_notes_button.setToolTip('\n'.join(warnings))
        if warnings:self.details.setPlainText(self.details.toPlainText()+'\n\n'+'\n'.join(warnings))
        self.selection_label.setText(('Draft preview. Edit pieces below, then preview again.' if not tab.record else str(len(tab.selected))+' selection(s) in this file' if tab.selected else 'Select an object in this file. Ctrl/Cmd-click in the tree for multiple.'))
        self.update_actions()
    def preview_notes(self,tab):
        notes=[*getattr(tab,'preview_notes',[]),*(message for part in tab.parts for message in part.get('warnings',[]))]
        unsupported=tab.info.get('unsupported_types',[])
        if unsupported:notes.append('Unsupported display: '+', '.join(unsupported))
        return list(dict.fromkeys(notes))
    def show_preview_notes(self):
        tab=self.current()
        if not tab:return
        dialog=W.QDialog(self);dialog.setWindowTitle('Preview notes');dialog.resize(650,400);layout=W.QVBoxLayout(dialog)
        layout.addWidget(label(self.native_name(tab.record) if tab.record else 'Assembly draft','title'))
        notes=W.QPlainTextEdit();notes.setReadOnly(True);notes.setPlainText('\n\n'.join(self.preview_notes(tab)));layout.addWidget(notes)
        close=W.QDialogButtonBox(W.QDialogButtonBox.Close);close.rejected.connect(dialog.reject);layout.addWidget(close);dialog.exec()
    def mode_changed(self,mode):
        tab=self.current()
        if tab:tab.mode=mode;tab.apply_mode()
    def edges_changed(self,on):
        tab=self.current()
        if tab:tab.edges=on;tab.apply_mode()
    def frame(self,selected):
        tab=self.current()
        if tab:tab.fit(selected)
    def pick_path(self,path):
        tab=self.current()
        if not tab:return
        if not path:
            tab.selected.clear();self.scene.clearSelection();self.scene.setCurrentItem(None)
            tab.apply_mode();self.tab_changed();return
        it=W.QTreeWidgetItemIterator(self.scene)
        while it.value():
            item=it.value()
            if item.data(0,QtCore.Qt.UserRole)==path:self.scene.setCurrentItem(item);self.scene_selected();return
            it+=1
        if any(part['path']==path for part in tab.parts):
            tab.selected={path};tab.apply_mode();self.selection_label.setText('1 selection in this file');self.update_actions()
    def scene_selected(self):
        tab=self.current()
        if not tab:return
        tab.selected={i.data(0,QtCore.Qt.UserRole) for i in self.scene.selectedItems()};tab.apply_mode()
        self.selection_label.setText(str(len(tab.selected))+' selection(s) in this file')
        self.update_actions()
        if tab.selected:self.details.setPlainText('\n'.join(sorted(tab.selected))+'\n\n'+('From '+self.native_name(tab.record)+'\n'+tab.record['id'] if tab.record else 'Assembly draft'))
    def add_selection(self):
        tab=self.current()
        if not tab or not tab.record:return
        if not tab.selected:return self.fail('Select a mesh in the viewport or object tree first.')
        paths=sorted(tab.selected,key=len);paths=[p for i,p in enumerate(paths) if not any(p.startswith(parent+'/') for parent in paths[:i])]
        for path in paths:
            if not any(p['path']==path or p['path'].startswith(path+'/') for p in tab.parts):continue
            choice=self.material_combo.currentData();logical=choice.get('library_material_revision') if isinstance(choice,dict) else None
            self.draft.append(Selection(snapshot_id=tab.record['id'],prim_path=path,label=path.split('/')[-1],material_revision=choice if isinstance(choice,str) else None,library_material_revision=logical).model_dump())
        self.update_tray();self.statusBar().showMessage('Added to assembly. Open another version tab to add more geometry.')
    def draft_signature(self):return json.dumps(self.draft,sort_keys=True)
    def mark_preview_state(self,tab):
        if not hasattr(tab,'draft_signature'):return
        tab.preview_stale=tab.draft_signature!=self.draft_signature()
        index=self.tabs.indexOf(tab)
        if index>=0:
            self.tabs.setTabText(index,'Assembly • outdated preview' if tab.preview_stale else 'Assembly • draft')
            self.tabs.setTabToolTip(index,'Draft changed. Preview again to update geometry and materials.' if tab.preview_stale else 'Preview of the current assembly draft')
        if tab.load_state=='ready':
            tab.load_notice.setText('Draft changed. Preview again to update this view. Save uses the current draft below.' if tab.preview_stale else '')
            tab.load_notice.setVisible(tab.preview_stale)
    def update_tray(self,persist=True):
        for index in range(self.tabs.count()):self.mark_preview_state(self.tabs.widget(index))
        if self.current() and getattr(self.current(),'preview_stale',False):self.tab_changed()
        self.table.setRowCount(len(self.draft))
        for row,s in enumerate(self.draft):
            try:r=self.project.resolve(s['snapshot_id']);source=self.native_name(r)+' · '+r['id'][-6:]
            except Exception:source=s['snapshot_id']
            material=s.get('material_revision') or 'Source'
            if s.get('library_material_revision'):
                try:
                    from .library import Library
                    record=Library(self.project).get(s['library_material_revision']);material=record['label']+' • r'+str(record['revision_number'])
                except CadgitError:material=s['library_material_revision']
            for col,text in enumerate([s['label'],source,str(s.get('translation',[0,0,0])),material]):
                item=W.QTableWidgetItem(str(text));item.setToolTip(s['prim_path']+'\n'+str(text));self.table.setItem(row,col,item)
        if persist:
            try:atomic_json(self.project.root/'.cadgit/drafts/current.json',self.draft)
            except OSError as exc:self.fail('Draft remains in memory but could not be saved: '+str(exc))
        self.update_actions()
    def new_assembly(self):
        if self.draft and W.QMessageBox.question(self,'New assembly','Start an empty draft? Current draft pieces will be cleared. Saved assemblies remain in history.')!=W.QMessageBox.Yes:return
        self.draft=[];self.update_tray()
    def remove_piece(self):
        row=self.table.currentRow()
        if row>=0:self.draft.pop(row);self.update_tray()
    def move_piece(self):
        row=self.table.currentRow()
        if row<0:return self.fail('Select a row in the assembly list first.')
        text,ok=W.QInputDialog.getText(self,'Move assembly piece','Offset X, Y, Z (meters):',text=', '.join(map(str,self.draft[row].get('translation',[0,0,0]))))
        if ok:
            try:
                v=[float(x.strip()) for x in text.split(',')]
                if len(v)!=3 or not np.isfinite(v).all():raise ValueError('Enter three finite values')
                self.draft[row]['translation']=v;self.update_tray()
            except ValueError as e:self.fail(str(e))
    def preview_draft(self):
        if not self.draft:return self.fail('Add selected geometry from a snapshot tab first.')
        selections=json.loads(json.dumps(self.draft));tab=SnapshotTab();tab.draft_signature=self.draft_signature();tab.preview_notes=[];tab.picked.connect(self.pick_path);self.tabs.addTab(tab,'Assembly • draft');self.tabs.setCurrentWidget(tab)
        def work():
            from .library import Library
            library=Library(self.project);notes=[]
            result=[];prims=[{'path':'/Draft','name':'Draft assembly','type':'Xform'}];known={'/Draft'}
            for index,s in enumerate(selections):
                if tab.cancelled.is_set():return None
                r=self.project.resolve(s['snapshot_id'])
                verification=self.project.verify(r['id'])
                if not verification['ok']:raise CadgitError('Snapshot integrity check failed: '+'; '.join(verification['errors']))
                appearance=None
                if s.get('library_material_revision'):
                    material=library.get(s['library_material_revision']);checked=library.verify(material['id'])
                    if not checked['ok']:raise CadgitError('Material integrity check failed: '+'; '.join(checked['errors']))
                    appearance=material['definition'].get('appearance',{})
                    if appearance.get('native_graph'):notes.append('Native shader graphs are saved for their application; this viewport shows USD textures and surface values.')
                if s.get('material_revision'):notes.append('Captured shader overrides are saved for their native application. This viewport shows source surface values.')
                prefix='/Draft/Piece_'+str(index+1)
                prims.append({'path':prefix,'name':s.get('label','Piece')+' · '+r['id'][-6:],'type':'Xform'});known.add(prefix)
                override=(material,library) if s.get('library_material_revision') else None
                for part in meshes(self.project.stage_path(r),s['prim_path'],include_textures=True,material_override=override):
                    if appearance:
                        preview=appearance.get('preview',{});part['color']=tuple(preview.get('base_color',[.65,.65,.65]));part['roughness']=preview.get('roughness',.4);part['metallic']=preview.get('metallic',0.)
                    source_path=part['path'];part['path']=prefix+source_path
                    part['points']=part['points']+np.array(s.get('translation',[0,0,0]));result.append(part)
                    ancestors=part['path'].split('/')
                    for depth in range(2,len(ancestors)):
                        ancestor='/'.join(ancestors[:depth])
                        if ancestor and ancestor not in known:
                            prims.append({'path':ancestor,'name':ancestor.rsplit('/',1)[-1],'type':'Xform'});known.add(ancestor)
                    prims.append({'path':part['path'],'name':part['name'],'type':'Mesh'})
            return result,{'prims':prims},list(dict.fromkeys(notes)),prepare_parts(result,tab.cancelled)
        def done(data):
            if self.tab_is_open(tab):
                tab.preview_notes=data[2];self.present_tab(tab,data[0],data[1],data[3])
        def failed(error):
            if not self.tab_is_open(tab):return False
            tab.load_error(error)
        self.job(work,done,failed,pool=VIEWPORT_POOL)
    def save_assembly(self):
        if self._saving_assembly:return
        if not self.draft:return self.fail('Add geometry to the assembly list first.')
        path,_=W.QFileDialog.getSaveFileName(self,'Save new assembly as USD',str(self.project.root/'exports/assembly.usdz'),'USD package (*.usdz);;USD scene (*.usd *.usda *.usdc)')
        if not path:return
        output=Path(path)
        sidecar=Path(str(output)+'.cadgit.json')
        if output.exists() or output.is_symlink() or sidecar.exists() or sidecar.is_symlink():return self.fail('Choose a new filename. Existing assembly files and lineage sidecars are not overwritten.')
        selections=json.loads(json.dumps(self.draft));name=output.stem
        self._saving_assembly=True;self.update_actions()
        def work():
            from .usd import export_usd
            r=assemble(self.project,selections,name)
            try:
                export_usd(self.project,r['id'],output)
                import tempfile
                from .store import publish_file
                with tempfile.TemporaryDirectory(prefix='lineage-',dir=self.project.root/'.cadgit/staging') as temporary:
                    metadata=Path(temporary)/'lineage.json';atomic_json(metadata,{'schema_version':1,'project_id':self.project.config['id'],'source_id':r['id'],'project':str(self.project.root)})
                    publish_file(metadata,sidecar)
            except Exception as exc:raise CadgitError('Assembly was saved to history as '+r['id']+', but file/lineage export did not complete: '+str(exc)) from exc
            try:self.project.event('assembly_exported',{'id':r['id'],'output':str(output)})
            except OSError as exc:r['publication_warning']='Assembly and export saved; event log failed: '+str(exc)
            return r
        def done(r):
            self._saving_assembly=False;self.latest_assembly=r;self.refresh();self.open_record(r['id']);self.update_actions();self.statusBar().showMessage('Saved '+str(output)+' • '+r['publication_warning'] if r.get('publication_warning') else 'Saved '+str(output)+' • open it in your modeling application to continue.')
        def failed(error):self._saving_assembly=False;self.refresh();self.update_actions()
        self.job(work,done,failed)
    def set_main(self):
        tab=self.current()
        if not tab or not tab.record or not tab.record['id'].startswith('assembly_'):return self.fail('Open a saved assembly tab first.')
        try:
            result=self.project.set_main(tab.record['id']);self.refresh();self.statusBar().showMessage(result.get('publication_warning') or 'Main points to '+tab.record['label']+'; native app files are unchanged.')
        except Exception as exc:self.fail(str(exc))
    def export_stl_dialog(self):
        tab=self.current()
        if not tab or not tab.record:return self.fail('Open a saved snapshot or assembly tab first.')
        selected=sorted(tab.selected)
        record=tab.record;reference=record['id']
        if len(selected)>1:return self.fail('Choose one subtree for this export, or save the multi-part assembly first.')
        path,_=W.QFileDialog.getSaveFileName(self,'Export selected geometry as STL',str(self.project.root/'exports/part.stl'),'STL (*.stl)')
        if not path:return
        if W.QMessageBox.question(self,'STL settings','Export from '+record['label']+' ('+reference[-7:]+')\n'+(selected[0] if selected else 'Entire current file')+'\nUnits: millimeters. Open/nonmanifold meshes are rejected. Shader displacement is not evaluated.')!=W.QMessageBox.Yes:return
        self.job(lambda:export_stl(self.project,reference,path,selected[0] if selected else None,allow_base_mesh=True),lambda r:self.statusBar().showMessage('STL saved: '+path+' • dimensions '+str(r['report']['dimensions'])+' mm'))
    def ingest_dialog(self):
        path,_=W.QFileDialog.getOpenFileName(self,'Add a whole USD file to history','','USD (*.usd *.usda *.usdc *.usdz)')
        if not path:return
        source,ok=W.QInputDialog.getText(self,'Source application','Source name:',text='manual')
        if ok and source:self.job(lambda:self.project.ingest(path,source,Path(path).name,metadata={'import_path':str(Path(path).resolve())}),lambda r:(self.refresh(),self.open_record(r['id'])))
    def connect_apps(self):
        from .connectors import attach
        from .service import start
        def work():
            r={}
            for app in ['rhino','blender']:
                try:attach(self.project,app);r[app]='watching normal saves'
                except Exception as e:r[app]=str(e)
            r['service']=start(self.project);return r
        self.job(work,lambda r:W.QMessageBox.information(self,'Native save adapters',json.dumps(r,indent=2)))
    def reload_open_menu(self):
        menu=W.QMenu(self)
        menu.addAction('Reveal current USD',self.reveal_current)
        menu.addAction('Copy USD path',self.copy_current)
        menu.addSeparator()
        from .handoff import targets
        try:configured=targets(self.project)
        except CadgitError as exc:
            configured=[];self.statusBar().showMessage('Application targets need attention: '+str(exc)+' • open Settings to repair.')
        for target in configured:menu.addAction(target['label']+'…',lambda _=False,t=target:self.open_target(t))
        menu.addSeparator();menu.addAction('Configure application targets…',self.settings);self.open_menu.setMenu(menu)
    def reveal_current(self):
        tab=self.current()
        if tab and tab.record:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.project.stage_path(tab.record).parent)))
    def copy_current(self):
        tab=self.current()
        if tab and tab.record:W.QApplication.clipboard().setText(str(self.project.stage_path(tab.record)))
    def open_target(self,target):
        tab=self.current()
        if not tab or not tab.record:return self.fail('Open a saved USD snapshot or assembly first.')
        suffix=target.get('extension','.usd');path,_=W.QFileDialog.getSaveFileName(self,'Create new '+target['label']+' file',str(self.project.root/'source'/('derived_'+tab.record['id'][-6:]+suffix)),'Native file (*'+suffix+')')
        if not path:return
        from .handoff import create_native
        self.job(lambda:create_native(self.project,tab.record['id'],target,Path(path)),lambda r:self.statusBar().showMessage(('Created new file with lineage: '+r['file'] if r.get('launched',True) else 'File created, but launch failed: '+r.get('launch_error','Unknown application error')+' • '+r['file'])))
    def settings(self):
        dialog=W.QDialog(self);dialog.setWindowTitle('Project settings');dialog.resize(650,430);layout=W.QVBoxLayout(dialog)
        layout.addWidget(label('Application targets','title'));layout.addWidget(label('Built-in adapters create new native files. External commands can use {usd}.','muted'))
        from .handoff import targets
        try:configured=targets(self.project)
        except CadgitError:configured=read_json(self.project.root/'cadgit.json').get('open_targets',[])
        editor=W.QPlainTextEdit(json.dumps(configured,indent=2));layout.addWidget(editor)
        theme_button=button('Toggle light / dark',self.toggle_theme);layout.addWidget(theme_button)
        buttons=W.QDialogButtonBox(W.QDialogButtonBox.Save|W.QDialogButtonBox.Cancel);layout.addWidget(buttons)
        def save():
            try:
                from .handoff import validate_targets
                value=validate_targets(json.loads(editor.toPlainText()))
                config=read_json(self.project.root/'cadgit.json');config['open_targets']=value;atomic_json(self.project.root/'cadgit.json',config);self.reload_open_menu();dialog.accept()
            except Exception as e:W.QMessageBox.warning(dialog,'Invalid targets',str(e))
        buttons.accepted.connect(save);buttons.rejected.connect(dialog.reject);dialog.exec()
    def toggle_theme(self):
        self.light=not self.light;colors=theme(W.QApplication.instance(),self.light)
        self.history.light=self.light;self.history.redraw()
        for i in range(self.tabs.count()):self.tabs.widget(i).plotter.set_background(colors['Layer_01'])
    def save_screenshot(self):
        if self.screenshot and not self._closing:
            self.grab().save(self.screenshot);self.screenshot=None


def launch(root,screenshot=None):
    from .app_identity import configure_application_identity,configure_application_icon
    configure_application_identity()
    app=W.QApplication.instance() or W.QApplication([])
    configure_application_icon(app)
    window=Window(Project(root),screenshot);window.show();return app.exec()
