"""Project-wide image/spec browser and material revision editor."""
from __future__ import annotations
import copy,json,os
from pathlib import Path
from PySide6 import QtCore,QtGui,QtWidgets as W
from .library import Library,reference,web_url,infer_kind
from .ui import Job
from .store import CadgitError


def button(text,slot,tooltip=''):
    widget=W.QPushButton(text);widget.clicked.connect(slot);widget.setToolTip(tooltip or text);return widget


def choices(combo,records,selected=None,empty=True):
    if empty:combo.addItem('None',None)
    for record in records:
        combo.addItem(record['label']+' • r'+str(record['revision_number'])+' • '+record['id'][-6:],record['id'])
    index=combo.findData(selected)
    if selected is not None and index<0:
        combo.addItem('Retained reference • '+str(selected)[-8:],selected);index=combo.count()-1
    if index>=0:combo.setCurrentIndex(index)


def display_value(value):
    if value is None:return ''
    return json.dumps(value,ensure_ascii=False) if isinstance(value,(dict,list)) else str(value)


class ProvenanceForm(W.QWidget):
    def __init__(self,data=None):
        super().__init__();self.base=copy.deepcopy(data or {});layout=W.QFormLayout(self);self.fields={}
        license=self.base.get('license',{})
        for key,label,value in [('provider','Provider',self.base.get('provider','')),('source_url','Source URL',self.base.get('source_url','')),('creator','Creator',self.base.get('creator','')),('license_name','License name',license.get('name','unknown')),('license_url','License URL',license.get('url','')),('license_notes','License notes',license.get('notes',''))]:
            field=W.QLineEdit(str(value));layout.addRow(label,field);self.fields[key]=field
    def value(self):
        result=copy.deepcopy(self.base);license=copy.deepcopy(result.get('license',{}))
        for key,field in self.fields.items():
            if key.startswith('license_'):license[{'license_name':'name','license_url':'url','license_notes':'notes'}[key]]=field.text().strip()
            else:result[key]=field.text().strip()
        result['license']=license;return result


class MaterialEditor(W.QDialog):
    def __init__(self,library,record=None,parent=None):
        super().__init__(parent);self.library=library;self.record=record;self.base=copy.deepcopy((record or {}).get('definition',{}));self.setWindowTitle('New material' if not record else 'New material revision');self.resize(850,650)
        layout=W.QVBoxLayout(self);form=W.QFormLayout();self.name=W.QLineEdit((record or {}).get('label',''));self.note=W.QLineEdit();form.addRow('Material name',self.name);form.addRow('Change note',self.note);layout.addLayout(form)
        tabs=W.QTabWidget();layout.addWidget(tabs,1)
        physical=W.QWidget();pl=W.QVBoxLayout(physical);pl.addWidget(W.QLabel('Missing values remain unspecified. Enter units and a source; these are stored properties, not certified solver data.'))
        self.properties=W.QTableWidget(0,6);self.properties.setHorizontalHeaderLabels(['Property','Value','Unit','Status','Source','Conditions']);self.properties.horizontalHeader().setSectionResizeMode(W.QHeaderView.Stretch);pl.addWidget(self.properties)
        for key,value in self.base.get('physical',{}).get('properties',{}).items():self.add_property(key,value)
        row=W.QHBoxLayout();row.addWidget(button('Add property',lambda:self.add_property()));row.addWidget(button('Remove property',self.remove_property));row.addStretch();pl.addLayout(row);tabs.addTab(physical,'Physical properties')
        appearance=W.QWidget();al=W.QVBoxLayout(appearance);af=W.QFormLayout();self.use_preview=W.QCheckBox('Provide a portable preview appearance');preview=self.base.get('appearance',{}).get('preview',{});self.use_preview.setChecked(bool(preview));af.addRow(self.use_preview)
        color=preview.get('base_color',[.65,.65,.65]);self.color=W.QLineEdit(QtGui.QColor.fromRgbF(*color).name());self.original_color=self.color.text();af.addRow('Base color (#RRGGBB)',self.color)
        self.roughness=W.QDoubleSpinBox();self.roughness.setRange(0,1);self.roughness.setSingleStep(.05);self.roughness.setDecimals(8);self.roughness.setValue(preview.get('roughness',.4));self.original_roughness=self.roughness.value();af.addRow('Roughness',self.roughness)
        self.metallic=W.QDoubleSpinBox();self.metallic.setRange(0,1);self.metallic.setSingleStep(.05);self.metallic.setDecimals(8);self.metallic.setValue(preview.get('metallic',0));self.original_metallic=self.metallic.value();af.addRow('Metallic',self.metallic)
        all_records=library.records()+library.legacy();images=[r for r in all_records if r['kind']=='image'];self.graph=W.QComboBox();choices(self.graph,[r for r in all_records if r['kind']=='shader' and library.project.stage_path(r).suffix.lower()=='.blend'],reference(self.base['appearance']['native_graph']) if self.base.get('appearance',{}).get('native_graph') else None);af.addRow('Native Blender graph',self.graph)
        self.material_name=W.QLineEdit(self.base.get('appearance',{}).get('material_name',''));af.addRow('Blender material name (if multiple)',self.material_name);al.addLayout(af)
        help=W.QLabel('Maps pin exact image revisions. USD projects base_color / roughness / metallic / opacity; UVs are required. Use graph:ImageName to map a named native graph image.');help.setWordWrap(True);al.addWidget(help)
        self.maps=W.QTableWidget(0,3);self.maps.setHorizontalHeaderLabels(['Role / graph:ImageName','Image revision','Color space']);self.maps.horizontalHeader().setSectionResizeMode(W.QHeaderView.Stretch);al.addWidget(self.maps,1);self.image_records=images
        for role,value in self.base.get('appearance',{}).get('maps',{}).items():self.add_map(role,reference(value),value.get('color_space','raw') if isinstance(value,dict) else 'raw')
        for name,value in self.base.get('appearance',{}).get('graph_images',{}).items():self.add_map('graph:'+name,reference(value),'raw')
        row=W.QHBoxLayout();row.addWidget(button('Add image binding',lambda:self.add_map()));row.addWidget(button('Remove binding',lambda:self.maps.removeRow(self.maps.currentRow()) if self.maps.currentRow()>=0 else None));row.addStretch();al.addLayout(row);tabs.addTab(appearance,'Appearance')
        documents=W.QWidget();dl=W.QVBoxLayout(documents);dl.addWidget(W.QLabel('Attach exact specification/document revisions. Import files in the asset browser first.'));self.documents=W.QListWidget();dl.addWidget(self.documents)
        selected={reference(r) for r in self.base.get('documents',[])}
        for record in all_records:
            if record['kind'] not in {'document','other'} and record['id'] not in selected:continue
            item=W.QListWidgetItem(record['label']+' • r'+str(record['revision_number']));item.setData(QtCore.Qt.UserRole,record['id']);item.setFlags(item.flags()|QtCore.Qt.ItemIsUserCheckable);item.setCheckState(QtCore.Qt.Checked if record['id'] in selected else QtCore.Qt.Unchecked);self.documents.addItem(item)
        tabs.addTab(documents,'Documents');self.provenance=ProvenanceForm(self.record.get('provenance',{}) if self.record else {});tabs.addTab(self.provenance,'Source / license')
        self.error=W.QLabel();self.error.setWordWrap(True);layout.addWidget(self.error);buttons=W.QDialogButtonBox(W.QDialogButtonBox.Save|W.QDialogButtonBox.Cancel);buttons.accepted.connect(self.validate);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def add_property(self,key='',value=None):
        value=value or {};row=self.properties.rowCount();self.properties.insertRow(row)
        columns=[key,json.dumps(value['value']) if value.get('value') is not None else '',display_value(value.get('unit','')),display_value(value.get('status','unverified')),display_value(value.get('source',value.get('source_url',''))),display_value(value.get('conditions',''))]
        for col,text in enumerate(columns):self.properties.setItem(row,col,W.QTableWidgetItem(text))
        self.properties.item(row,0).setData(QtCore.Qt.UserRole,key)
    def remove_property(self):
        if self.properties.currentRow()>=0:self.properties.removeRow(self.properties.currentRow())
    def add_map(self,role='',revision=None,color_space='raw'):
        row=self.maps.rowCount();self.maps.insertRow(row);self.maps.setItem(row,0,W.QTableWidgetItem(role));self.maps.item(row,0).setData(QtCore.Qt.UserRole,role);combo=W.QComboBox();choices(combo,self.image_records,revision);self.maps.setCellWidget(row,1,combo);color=W.QComboBox();color.addItems(['raw','sRGB','auto']);
        if color.findText(color_space)<0:color.addItem(color_space)
        color.setCurrentText(color_space);self.maps.setCellWidget(row,2,color)
    def value(self):
        definition=copy.deepcopy(self.base);physical=copy.deepcopy(definition.get('physical',{}));properties={};old=physical.get('properties',{})
        for row in range(self.properties.rowCount()):
            cells=[self.properties.item(row,col).text().strip() if self.properties.item(row,col) else '' for col in range(6)];key,raw,unit,status,source,conditions=cells
            if not key:continue
            if key in properties:raise CadgitError('Duplicate property: '+key)
            original_key=self.properties.item(row,0).data(QtCore.Qt.UserRole);prop=copy.deepcopy(old.get(original_key,{}))
            original_raw=json.dumps(prop['value']) if prop.get('value') is not None else ''
            if raw!=original_raw or original_key not in old:
                try:prop['value']=json.loads(raw) if raw else None
                except ValueError:prop['value']=raw
            for field,text,original_text in [('unit',unit,display_value(prop.get('unit',''))),('status',status,display_value(prop.get('status','unverified'))),('source',source,display_value(prop.get('source',prop.get('source_url','')))),('conditions',conditions,display_value(prop.get('conditions','')))]:
                if text!=original_text or original_key not in old:
                    if field=='conditions':
                        try:prop[field]=json.loads(text) if text else ''
                        except ValueError:prop[field]=text
                    else:prop[field]=text
            properties[key]=prop
        if properties or 'properties' in physical:physical['properties']=properties
        if physical or 'physical' in definition:definition['physical']=physical
        appearance=copy.deepcopy(definition.get('appearance',{}))
        if self.use_preview.isChecked():
            color=QtGui.QColor(self.color.text())
            if not color.isValid():raise CadgitError('Choose a valid preview color')
            preview=copy.deepcopy(appearance.get('preview',{}))
            if self.color.text()!=self.original_color or 'base_color' not in preview:preview['base_color']=[color.redF(),color.greenF(),color.blueF()]
            if self.roughness.value()!=self.original_roughness or 'roughness' not in preview:preview['roughness']=self.roughness.value()
            if self.metallic.value()!=self.original_metallic or 'metallic' not in preview:preview['metallic']=self.metallic.value()
            appearance['preview']=preview
        else:appearance.pop('preview',None)
        original_graph=appearance.get('native_graph');selected_graph=self.graph.currentData()
        if selected_graph:
            if original_graph is None or reference(original_graph)!=selected_graph:appearance['native_graph']=selected_graph
        else:appearance.pop('native_graph',None)
        if self.material_name.text().strip()!=appearance.get('material_name',''):appearance['material_name']=self.material_name.text().strip()
        maps={};graph_images={};old_maps=appearance.get('maps',{});old_graph_images=appearance.get('graph_images',{})
        for row in range(self.maps.rowCount()):
            role=self.maps.item(row,0).text().strip() if self.maps.item(row,0) else '';ref=self.maps.cellWidget(row,1).currentData()
            if not role or not ref:continue
            if role in maps or role.startswith('graph:') and role[6:] in graph_images:raise CadgitError('Duplicate image binding role: '+role)
            if role=='graph:':raise CadgitError('A native graph image binding needs its image name')
            previous_role=self.maps.item(row,0).data(QtCore.Qt.UserRole) or ''
            original=copy.deepcopy(old_graph_images.get(previous_role[6:])) if previous_role.startswith('graph:') else copy.deepcopy(old_maps.get(previous_role))
            if role.startswith('graph:'):
                if original is not None and reference(original)==ref:graph_images[role[6:]]=original
                else:graph_images[role[6:]]={**original,'revision_id':ref} if isinstance(original,dict) else ref
            else:
                color_space=self.maps.cellWidget(row,2).currentText()
                if isinstance(original,str) and original==ref and color_space=='raw':maps[role]=original
                else:
                    value=original if isinstance(original,dict) else {};value['revision_id']=ref
                    if color_space!=value.get('color_space','raw') or original is None:value['color_space']=color_space
                    maps[role]=value
        if maps or 'maps' in appearance:appearance['maps']=maps
        if graph_images or 'graph_images' in appearance:appearance['graph_images']=graph_images
        if appearance or 'appearance' in definition:definition['appearance']=appearance
        original_docs={reference(value):copy.deepcopy(value) for value in self.base.get('documents',[])}
        documents=[original_docs.get(self.documents.item(i).data(QtCore.Qt.UserRole),self.documents.item(i).data(QtCore.Qt.UserRole)) for i in range(self.documents.count()) if self.documents.item(i).checkState()==QtCore.Qt.Checked]
        if documents or 'documents' in definition:definition['documents']=documents
        return definition
    def validate(self):
        try:
            if not self.name.text().strip():raise CadgitError('Material name is required')
            self.library._material_dependencies(self.value());self.accept()
        except Exception as exc:self.error.setText(str(exc))


class LibraryWidget(W.QWidget):
    materialSelected=QtCore.Signal(str)
    changed=QtCore.Signal()
    def __init__(self,project):
        super().__init__();self.project=project;self.library=Library(project);self.record=None;self._refreshing=False;self._closed=False;self.jobs=[];self._catalog=[];self._index={};self._thumbnails={};self._valid_selection=False
        layout=W.QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        tools=W.QToolBar();self.tools=tools;tools.setMovable(False);tools.addAction('New material…',self.new_material);tools.addAction('Import files…',self.import_files);tools.addAction('Import folder…',self.import_folder);tools.addAction('Browse Poliigon…',lambda:QtGui.QDesktopServices.openUrl(QtCore.QUrl('https://www.poliigon.com/textures/free')));tools.addAction('Refresh',self.refresh);layout.addWidget(tools)
        splitter=W.QSplitter();self.splitter=splitter;splitter.setChildrenCollapsible(False);splitter.setHandleWidth(9);layout.addWidget(splitter,1)
        filters=W.QWidget();fl=W.QVBoxLayout(filters);self.search=W.QLineEdit();self.search.setPlaceholderText('Search names, tags, sources…');self.search_timer=QtCore.QTimer(self);self.search_timer.setSingleShot(True);self.search_timer.timeout.connect(lambda:self.refresh(reload=False));self.search.textChanged.connect(self.search_changed);fl.addWidget(self.search)
        self.kinds=W.QListWidget()
        for label,kind in [('All assets',None),('Materials','material'),('Images','image'),('Native graphs','shader'),('Documents','document'),('Other assets','other'),('Captured shaders','legacy')]:
            item=W.QListWidgetItem(label);item.setData(QtCore.Qt.UserRole,kind);self.kinds.addItem(item)
        self.kinds.setCurrentRow(0);self.kinds.currentRowChanged.connect(lambda:self.refresh(reload=False));fl.addWidget(self.kinds)
        hint=W.QLabel('Images and documents have their own histories. Materials pin exact revisions.');hint.setWordWrap(True);fl.addWidget(hint);filters.setMinimumWidth(160);splitter.addWidget(filters)
        center=W.QWidget();cl=W.QVBoxLayout(center);self.count=W.QLabel();cl.addWidget(self.count);self.grid=W.QListWidget();self.grid.setViewMode(W.QListView.IconMode);self.grid.setResizeMode(W.QListView.Adjust);self.grid.setMovement(W.QListView.Static);self.grid.setIconSize(QtCore.QSize(112,96));self.grid.setGridSize(QtCore.QSize(205,160));self.grid.setWordWrap(True);self.grid.currentItemChanged.connect(self.selected);cl.addWidget(self.grid,1);splitter.addWidget(center)
        right=W.QWidget();rl=W.QVBoxLayout(right);self.title=W.QLabel('Select a material or asset');self.title.setWordWrap(True);self.title.setTextFormat(QtCore.Qt.PlainText);rl.addWidget(self.title);self.revisions=W.QComboBox();self.revisions.currentIndexChanged.connect(self.revision_selected);rl.addWidget(self.revisions)
        self.preview=W.QLabel('Import images, graphs and specifications, or create a material.');self.preview.setTextFormat(QtCore.Qt.PlainText);self.preview.setAlignment(QtCore.Qt.AlignCenter);self.preview.setWordWrap(True);self.preview.setMinimumHeight(130);rl.addWidget(self.preview)
        self.inspector=W.QTabWidget();self.details=W.QTextBrowser();self.history=W.QTreeWidget();self.history.setHeaderLabels(['Revision / relationship','ID']);self.history.itemDoubleClicked.connect(self.follow_link);self.source=W.QTextBrowser();self.inspector.addTab(self.details,'Properties / assets');self.inspector.addTab(self.history,'History / lineage');self.inspector.addTab(self.source,'Source / license');rl.addWidget(self.inspector,1)
        row=W.QHBoxLayout();self.revise_button=button('New revision…',self.new_revision);row.addWidget(self.revise_button);self.derive_button=button('Derive…',self.derive);row.addWidget(self.derive_button);rl.addLayout(row)
        row=W.QHBoxLayout();self.recombine_button=button('Recombine…',self.recombine);row.addWidget(self.recombine_button);self.use_button=button('Use for new pieces',self.use_material);row.addWidget(self.use_button);rl.addLayout(row)
        row=W.QHBoxLayout();self.verify_button=button('Verify',self.verify);row.addWidget(self.verify_button);self.reveal_button=button('Reveal file',self.reveal);row.addWidget(self.reveal_button);self.open_button=button('Open file',self.open_file);row.addWidget(self.open_button);self.source_button=button('Open source',self.open_source);row.addWidget(self.source_button);rl.addLayout(row)
        right.setMinimumWidth(310);splitter.addWidget(right);splitter.setSizes([190,600,430]);self.status=W.QLabel();self.status.setWordWrap(True);self.status.setTextFormat(QtCore.Qt.PlainText);layout.addWidget(self.status);self.refresh()
    def fail(self,error):self.status.setText(str(error))
    def shutdown(self):self._closed=True;self.search_timer.stop()
    def run(self,operation,done):
        job=Job(operation);self.jobs.append(job);self.tools.setEnabled(False);self.status.setText('Saving assets…');self.actions()
        def complete(value):
            self.jobs.remove(job)
            if self._closed:return
            self.tools.setEnabled(not self.jobs)
            try:done(value)
            except Exception as exc:self.fail(exc)
            self.actions()
        def failed(error):
            self.jobs.remove(job)
            if not self._closed:self.tools.setEnabled(not self.jobs);self.fail(error);self.actions()
        job.signals.done.connect(complete);job.signals.error.connect(failed);QtCore.QThreadPool.globalInstance().start(job)
    def clear_selection(self):
        self.record=None;self._valid_selection=False;self.revisions.blockSignals(True);self.revisions.clear();self.revisions.blockSignals(False);self.title.setText('Select a material or asset');self.preview.clear();self.preview.setStyleSheet('');self.preview.setText('No asset selected');self.details.clear();self.history.clear();self.source.clear();self.actions()
    def search_changed(self,*_):
        self.clear_selection();self.search_timer.start(180)
    def indexed(self,revision):return self._index.get(revision) or self.library.get(revision)
    def thumbnail(self,record,size=QtCore.QSize(112,96)):
        if record['kind']!='image':return None
        try:
            path=self.project.stage_path(record);stat=path.stat();key=(record['id'],tuple((f['path'],f['sha256']) for f in record['files']),stat.st_mtime_ns,stat.st_size,size.width(),size.height())
            if key in self._thumbnails:return self._thumbnails[key]
            QtGui.QImageReader.setAllocationLimit(64)
            reader=QtGui.QImageReader(str(path));dimensions=reader.size()
            if dimensions.width()<=0 or dimensions.height()<=0 or dimensions.width()*dimensions.height()>40_000_000:return None
            if not self.project.verify(record)['ok']:return None
            reader.setScaledSize(dimensions.scaled(size,QtCore.Qt.KeepAspectRatio));image=reader.read();result=QtGui.QPixmap.fromImage(image) if not image.isNull() else None;self._thumbnails[key]=result
            return result
        except (OSError,CadgitError):return None
    def refresh(self,*_,reload=True):
        if self._refreshing:return
        self.search_timer.stop();self._refreshing=True;selected=self.record['id'] if self.record else None
        try:
            kind=self.kinds.currentItem().data(QtCore.Qt.UserRole) if self.kinds.currentItem() else None
            if reload or not self._catalog:
                self._catalog=self.library.records()+self.library.legacy();self._index={r['id']:r for r in self._catalog}
            items=self.library.summaries(None if kind=='legacy' else kind,self.search.text(),self._catalog)
            if kind=='legacy':items=[item for item in items if item['legacy']]
            self.grid.blockSignals(True);self.grid.clear()
            for summary in items:
                record=self.indexed(summary['head']);item=W.QListWidgetItem(summary['label']+'\n'+summary['kind'].title()+' • r'+str(record['revision_number'])+' • '+str(summary['revision_count'])+' version(s)'+(' • captured' if summary['legacy'] else ''));item.setData(QtCore.Qt.UserRole,record['asset_id']);item.setToolTip(record['id']+'\n'+str(len(summary['heads']))+' head(s)');image=self.thumbnail(record)
                if image:item.setIcon(QtGui.QIcon(image))
                else:item.setIcon(self.style().standardIcon(W.QStyle.SP_DirIcon if record['kind']=='material' else W.QStyle.SP_FileIcon))
                self.grid.addItem(item)
            self.grid.blockSignals(False);self.count.setText(str(len(items))+' project assets');self.status.setText('\n'.join(self.library.issues))
            available={item['asset_id'] for item in items}
            if selected and self._index.get(selected,{}).get('asset_id') in available:self.select_revision(selected,reset_filter=False)
            else:self.clear_selection()
            self.actions()
        except Exception as exc:self.fail(exc)
        finally:self._refreshing=False
    def selected(self,item,previous=None):
        if not item:return
        records=[r for r in self._catalog if r['asset_id']==item.data(QtCore.Qt.UserRole)]
        self.revisions.blockSignals(True);self.revisions.clear()
        for record in reversed(records):self.revisions.addItem('r'+str(record['revision_number'])+' • '+record['created_at'][:19]+' • '+record['id'][-7:],record['id'])
        self.revisions.blockSignals(False);self.revision_selected()
    def select_revision(self,revision,reset_filter=True):
        record=self.library.get(revision)
        if reset_filter:
            self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False);self.kinds.blockSignals(True);self.kinds.setCurrentRow(0);self.kinds.blockSignals(False);self.refresh()
        for index in range(self.grid.count()):
            item=self.grid.item(index)
            if item.data(QtCore.Qt.UserRole)==record['asset_id']:
                self.grid.setCurrentItem(item);self.selected(item);self.revisions.setCurrentIndex(self.revisions.findData(revision));self.revision_selected();return
    def revision_selected(self,*_):
        ref=self.revisions.currentData()
        if not ref:return
        try:
            self.record=self.indexed(ref);r=self.record;self._valid_selection=False;
            checked=self.library.verify(ref)
            if not checked['ok']:
                self.preview.clear();self.details.setPlainText('Integrity error: '+'; '.join(checked['errors']));self.actions();return
            self._valid_selection=True;self.title.setText(r['label']+' • r'+str(r['revision_number'])+'\n'+r['id']);self.preview.clear();self.preview.setStyleSheet('')
            image=self.thumbnail(r,QtCore.QSize(380,220))
            if image:self.preview.setPixmap(image)
            elif r['kind']=='material':
                appearance=r['definition'].get('appearance',{});color=appearance.get('preview',{}).get('base_color')
                if color:
                    qcolor=QtGui.QColor.fromRgbF(*color);text='#17202A' if qcolor.lightnessF()>.55 else '#FFFFFF';self.preview.setStyleSheet('background:'+qcolor.name()+';color:'+text+';padding:12px;')
                self.preview.setText('Portable color preview\nNative graphs render in their application' if color else 'Native graph attached • preview in its compatible application' if appearance.get('native_graph') else 'Physical-only / no portable preview\nNo engineering properties are inferred')
            else:self.preview.setText(r['kind'].title()+' asset\n'+('Captured native shader' if r.get('legacy') else Path(r['entry_layer']).name)+'\nPreview unavailable or not supported')
            import html
            definition=r.get('definition',{});body=[]
            if r['kind']=='material':
                body.append('<h3>Physical properties</h3>')
                props=definition.get('physical',{}).get('properties',{})
                if not props:body.append('<p>Unspecified. Add sourced values in a new revision.</p>')
                for key,value in props.items():body.append('<p><b>'+html.escape(key)+'</b>: '+html.escape(str(value.get('value') if value.get('value') is not None else 'unspecified'))+' '+html.escape(value.get('unit',''))+'<br>'+html.escape(value.get('status','unverified'))+' • '+html.escape(str(value.get('source',value.get('source_url',''))))+'</p>')
                body.append('<h3>Appearance / supporting assets</h3>')
            for dependency in r.get('dependencies',[]):
                target=self.indexed(dependency['revision_id']);body.append('<p>'+html.escape(dependency['role'])+': <b>'+html.escape(target['label'])+'</b> r'+str(target['revision_number'])+'<br>'+html.escape(target['id'])+'</p>')
            body.append('<h3>Used by</h3>')
            for used in self.library.used_by(ref):body.append('<p>'+html.escape(used['label'])+' • '+html.escape(used['role'])+'</p>')
            if r['kind']!='material':body.append('<p>Archived file: '+html.escape(r['entry_layer'])+'</p>')
            self.details.setHtml(''.join(body));self.history.clear()
            versions=W.QTreeWidgetItem(self.history,['Revision history','']);parents=W.QTreeWidgetItem(self.history,['Derived from / recombined donors','']);inputs=W.QTreeWidgetItem(self.history,['Pinned assets',''])
            for revision in reversed([value for value in self._catalog if value['asset_id']==r['asset_id']]):
                item=W.QTreeWidgetItem(versions,['r'+str(revision['revision_number'])+' • '+revision.get('change_note',''),revision['id']]);item.setData(0,QtCore.Qt.UserRole,revision['id'])
            for link in [*r.get('parents',[]),*r.get('dependencies',[])]:
                target=self.indexed(link['revision_id']);item=W.QTreeWidgetItem(inputs if link in r.get('dependencies',[]) else parents,[link['role']+' • '+target['label']+' r'+str(target['revision_number']),link['revision_id']]);item.setData(0,QtCore.Qt.UserRole,link['revision_id'])
            self.history.expandToDepth(0)
            self.source.setPlainText(json.dumps(r.get('provenance',{}),indent=2));self.actions()
        except Exception as exc:self.fail(exc)
    def actions(self):
        r=self.record;material=bool(r and self._valid_selection and r['kind']=='material');busy=bool(self.jobs)
        self.use_button.setEnabled(material and not busy);self.recombine_button.setEnabled(material and not busy);self.revise_button.setEnabled(bool(r and self._valid_selection and not r.get('legacy')) and not busy);self.derive_button.setEnabled(bool(r and self._valid_selection) and not busy);self.verify_button.setEnabled(bool(r));self.reveal_button.setEnabled(bool(r));self.open_button.setEnabled(bool(r));self.source_button.setEnabled(bool(r and web_url(r.get('provenance',{}).get('source_url',''))))
    def follow_link(self,item,column=0):
        ref=item.data(0,QtCore.Qt.UserRole)
        if ref:self.select_revision(ref)
    def changed_record(self,record):self.refresh();self.select_revision(record['id']);self.changed.emit();self.status.setText('Saved immutable revision '+record['id'])
    def save_material_editor(self,editor,asset_id=None,expected_revision=None,parents=None):
        try:name=editor.name.text().strip();definition=editor.value();provenance=editor.provenance.value();note=editor.note.text()
        except Exception as exc:return self.fail(exc)
        self.run(lambda:self.library.create_material(name,definition,asset_id,expected_revision,parents,provenance=provenance,note=note),self.changed_record)
    def new_material(self):
        editor=MaterialEditor(self.library,parent=self)
        if editor.exec()==W.QDialog.Accepted:self.save_material_editor(editor)
    def new_revision(self):
        if not self.record:return
        if self.record['kind']=='material':
            record=self.record;editor=MaterialEditor(self.library,record,self)
            if editor.exec()==W.QDialog.Accepted:self.save_material_editor(editor,record['asset_id'],record['id'])
        else:self.import_files(revise=True)
    def import_files(self,revise=False,derive=False):
        paths,_=W.QFileDialog.getOpenFileNames(self,'Import new revision' if revise else 'Import local assets')
        if not paths:return
        if revise and len(paths)!=1:return self.fail('Choose one file for a new revision')
        self.import_paths(paths,revise,derive)
    def import_paths(self,paths,revise=False,derive=False):
        base=self.record if revise or derive else None
        dialog=W.QDialog(self);dialog.setWindowTitle('Asset import provenance');layout=W.QVBoxLayout(dialog);layout.addWidget(W.QLabel(str(len(paths))+' file(s), archived independently; originals remain in place.'));provenance=ProvenanceForm((base or {}).get('provenance',{}));layout.addWidget(provenance);note=W.QLineEdit();note.setPlaceholderText('Change / derivation note');layout.addWidget(note);buttons=W.QDialogButtonBox(W.QDialogButtonBox.Save|W.QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()!=W.QDialog.Accepted:return
        source=provenance.value();change=note.text()
        def operation():
            imported=[];failure=None
            for path in paths:
                try:imported.append(self.library.import_asset(path,label=base['label'] if revise else None,kind=base['kind'] if revise else None,asset_id=base['asset_id'] if revise else None,expected_revision=base['id'] if revise else None,parents=[{'revision_id':base['id'],'role':'derived_from'}] if derive else None,provenance=source,note=change))
                except Exception as exc:failure=str(path)+': '+str(exc);break
            return imported,failure
        def complete(result):
            imported,failure=result
            if imported:self.changed_record(imported[-1])
            if failure:self.fail('Imported '+str(len(imported))+' file(s); import stopped at '+failure+'; successful IDs: '+', '.join(r['id'] for r in imported))
        self.run(operation,complete)
    def import_folder(self):
        directory=W.QFileDialog.getExistingDirectory(self,'Import downloaded local assets (no archive extraction)')
        if directory:
            paths=[]
            for folder,dirs,files in os.walk(directory,followlinks=False):
                here=Path(folder)
                if (here/'library.json').exists() or (here/'COMMITTED').exists():dirs[:]=[];continue
                dirs[:]=[name for name in dirs if name not in {'.git','.cadgit','.venv','node_modules','__pycache__'} and not (here/name).is_symlink()]
                paths.extend(str(here/name) for name in sorted(files) if not (here/name).is_symlink())
                if len(paths)>200:break
            if len(paths)>200:return self.fail('Choose a smaller folder (at most 200 files per import)')
            if paths:self.import_paths(paths)
            else:self.status.setText('No regular source files found; generated archives, runtime folders and symlinks are skipped.')
    def derive(self):
        if not self.record:return
        if self.record['kind']=='material':
            record=self.record;editor=MaterialEditor(self.library,record,self);editor.setWindowTitle('Derive as new material');editor.name.setText(record['label']+' variant')
            if editor.exec()==W.QDialog.Accepted:self.save_material_editor(editor,parents=[{'revision_id':record['id'],'role':'derived_from'}])
        else:self.import_files(derive=True)
    def recombine(self):
        records=[r for r in self.library.records() if r['kind']=='material']
        dialog=W.QDialog(self);dialog.setWindowTitle('Recombine material facets');dialog.resize(700,530);layout=W.QVBoxLayout(dialog);form=W.QFormLayout();name=W.QLineEdit('Recombined material');physical=W.QComboBox();appearance=W.QComboBox();choices(physical,records,self.record['id'],False);choices(appearance,records,self.record['id'],False);form.addRow('New material name',name);form.addRow('Physical data from',physical);form.addRow('Appearance from',appearance);layout.addLayout(form);preview=W.QPlainTextEdit();preview.setReadOnly(True);layout.addWidget(preview)
        def update(*_):
            p=self.library.get(physical.currentData());a=self.library.get(appearance.currentData());preview.setPlainText(json.dumps({'physical':p['definition'].get('physical',{}),'appearance':a['definition'].get('appearance',{}),'note':'These facets are copied; no physical averaging or shader-node merge.'},indent=2))
        physical.currentIndexChanged.connect(update);appearance.currentIndexChanged.connect(update);update();buttons=W.QDialogButtonBox(W.QDialogButtonBox.Save|W.QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec()==W.QDialog.Accepted:
            label=name.text().strip();physical_revision=physical.currentData();appearance_revision=appearance.currentData()
            self.run(lambda:self.library.recombine(label,physical_revision,appearance_revision),self.changed_record)
    def use_material(self):
        if self.record and self.record['kind']=='material':self.materialSelected.emit(self.record['id'])
    def verify(self):
        if self.record:self.status.setText(json.dumps(self.library.verify(self.record['id']),indent=2))
    def reveal(self):
        if self.record:QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.project.stage_path(self.record).parent)))
    def open_file(self):
        if not self.record:return
        checked=self.library.verify(self.record['id'])
        if not checked['ok']:return self.fail('; '.join(checked['errors']))
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(self.project.stage_path(self.record))))
    def open_source(self):
        url=self.record.get('provenance',{}).get('source_url','') if self.record else ''
        if web_url(url):QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))
