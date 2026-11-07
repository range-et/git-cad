"""Scrollable, connected commit graph for the CAD-GIT workbench."""
from PySide6 import QtCore,QtGui,QtWidgets as W

COLORS=['#D59D48','#4CA6D6','#AD8CD7','#65B99E','#D97989','#A4B862']

def connection_path(start,end,gap,row_height):
    """Straight lanes with short, adjacent-column hops below a fork/merge."""
    path=QtGui.QPainterPath(start)
    columns=round(abs(end.x()-start.x())/gap)
    if not columns:
        path.lineTo(end);return path
    direction=1 if end.x()>start.x() else -1
    down=1 if end.y()>=start.y() else -1
    height=min(row_height*.65,max(0,abs(end.y()-start.y())-12),gap*columns)
    step=height/columns;x=start.x();y=start.y()+down*6
    path.lineTo(x,y)
    for _ in range(columns):
        x+=direction*gap
        path.lineTo(x,y+down*step*.5)
        y+=down*step
        path.lineTo(x,y)
    path.lineTo(end)
    return path

class HistoryGraph(W.QGraphicsView):
    openRequested=QtCore.Signal(str)
    menuRequested=QtCore.Signal(str,object)
    matchesChanged=QtCore.Signal(int)
    ROW=68
    def __init__(self,parent=None):
        super().__init__(parent);self.graph={'nodes':[],'edges':[],'lanes':[]};self.selected_ref=None;self.query='';self.rows={};self.light=False
        self.setScene(W.QGraphicsScene(self));self.setRenderHint(QtGui.QPainter.Antialiasing)
        self.setAlignment(QtCore.Qt.AlignTop|QtCore.Qt.AlignLeft);self.setFrameShape(W.QFrame.NoFrame)
        self.setFocusPolicy(QtCore.Qt.StrongFocus);self.setAccessibleName('Versions and branches graph')
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.setToolTip('Click a commit to open its file. Right-click to branch, name a version, or inspect lineage. Solid lines: save ancestry. Dashed lines: assembly/import ancestry.')
    def set_graph(self,graph):
        scroll=self.verticalScrollBar().value();self.graph=graph;self.redraw();self.verticalScrollBar().setValue(scroll)
    def matched_ids(self):
        def matches(node):
            record=node['record'];haystack=' '.join([node['id'],record.get('label',''),record.get('metadata',{}).get('native_path') or '',*[r['label'] for r in node['refs']]])
            return not self.query or self.query in haystack.lower()
        return [node['id'] for node in self.graph['nodes'] if matches(node)]
    def set_query(self,text):
        self.query=text.strip().lower();matches=self.matched_ids()
        if self.query and matches and self.selected_ref not in matches:self.selected_ref=matches[0]
        self.redraw();self.matchesChanged.emit(len(matches))
        if self.query and self.selected_ref in self.rows:self.ensureVisible(self.rows[self.selected_ref])
    def open_selected(self):
        if self.selected_ref in self.matched_ids():self.openRequested.emit(self.selected_ref)
    def navigate(self,delta):
        matches=self.matched_ids()
        if not matches:return
        index=matches.index(self.selected_ref) if self.selected_ref in matches else (-1 if delta>0 else len(matches))
        self.select_ref(matches[max(0,min(len(matches)-1,index+delta))])
    def keyPressEvent(self,event):
        if event.key() in (QtCore.Qt.Key_Down,QtCore.Qt.Key_Up,QtCore.Qt.Key_F3):
            backward=event.key()==QtCore.Qt.Key_Up or event.key()==QtCore.Qt.Key_F3 and bool(event.modifiers() & QtCore.Qt.ShiftModifier)
            self.navigate(-1 if backward else 1);event.accept();return
        if event.key() in (QtCore.Qt.Key_Return,QtCore.Qt.Key_Enter,QtCore.Qt.Key_Space):self.open_selected();event.accept();return
        if event.key() in (QtCore.Qt.Key_Home,QtCore.Qt.Key_End):
            matches=self.matched_ids()
            if matches:self.select_ref(matches[0] if event.key()==QtCore.Qt.Key_Home else matches[-1])
            event.accept();return
        super().keyPressEvent(event)

    def select_ref(self,ref):
        self.selected_ref=ref;self.redraw()
        if ref in self.rows:self.ensureVisible(self.rows[ref])
        node=next((n for n in self.graph['nodes'] if n['id']==ref),None)
        if node:self.setAccessibleDescription(node['record'].get('label','')+' '+ref)
    def redraw(self):
        scene=self.scene();scene.clear();self.rows={}
        bg='#F0F2F5' if self.light else '#181C21';fg='#232B34' if self.light else '#DFE5EA';muted='#687583' if self.light else '#93A0AD'
        self.setBackgroundBrush(QtGui.QColor(bg))
        lanes=self.graph['lanes'];gap=22;graph_width=26+max(1,self.graph.get('column_count',len(lanes)))*gap;text_x=graph_width+14
        width=max(self.viewport().width()-4,text_x+260)
        positions={n['id']:QtCore.QPointF(20+n.get('column',n['lane'])*gap,34+i*self.ROW) for i,n in enumerate(self.graph['nodes'])}
        self.positions=positions
        lane_by_id={n['id']:n['lane'] for n in self.graph['nodes']}
        for edge in self.graph['edges']:
            a=positions[edge['child']];b=positions[edge['parent']]
            color=COLORS[lane_by_id[edge['child']]%len(COLORS)]
            path=connection_path(a,b,gap,self.ROW)
            pen=QtGui.QPen(QtGui.QColor(color),2)
            if edge['kind']!='save':pen.setStyle(QtCore.Qt.DashLine)
            line=scene.addPath(path,pen);line.setZValue(0);line.setToolTip(edge['kind']+'\n'+edge['child']+' → '+edge['parent'])
        for i,node in enumerate(self.graph['nodes']):
            ref=node['id'];record=node['record'];p=positions[ref];top=i*self.ROW
            color=COLORS[node['lane']%len(COLORS)]
            haystack=' '.join([ref,record.get('label',''),(record.get('metadata',{}).get('native_path') or ''),*[r['label'] for r in node['refs']]]).lower()
            matched=not self.query or self.query in haystack
            rect=scene.addRect(0,top,width,self.ROW,QtGui.QPen(QtCore.Qt.NoPen),QtGui.QBrush(QtGui.QColor('#263C4A' if ref==self.selected_ref else bg)))
            rect.setZValue(-1);rect.setData(0,ref)
            tooltip=record.get('label','')+'\n'+ref+'\n'+record.get('created_at','')+'\n'+(record.get('metadata',{}).get('native_path') or '')
            rect.setToolTip(tooltip);self.rows[ref]=rect
            pen=QtGui.QPen(QtGui.QColor(color),2);brush=QtGui.QBrush(QtGui.QColor(color))
            if record.get('selections'):
                polygon=QtGui.QPolygonF([p+QtCore.QPointF(0,-6),p+QtCore.QPointF(6,0),p+QtCore.QPointF(0,6),p+QtCore.QPointF(-6,0)])
                shape=scene.addPolygon(polygon,pen,QtGui.QBrush(QtGui.QColor(bg)))
            else:shape=scene.addEllipse(p.x()-5,p.y()-5,10,10,pen,brush)
            shape.setZValue(2);shape.setData(0,ref);shape.setToolTip(tooltip)
            refs=node['refs'];badge='   '.join(r['label'] for r in refs)
            tooltip+='\n'+'\n'.join(r['label'] for r in refs)
            badge=QtGui.QFontMetrics(QtGui.QFont('Helvetica Neue',10)).elidedText(badge,QtCore.Qt.ElideRight,int(width-text_x-10))
            title=record.get('label',ref)
            font=QtGui.QFont('Helvetica Neue',11);font.setBold(True)
            title=QtGui.QFontMetrics(font).elidedText(title,QtCore.Qt.ElideRight,int(width-text_x-10))
            for text,y,c,bold,size in [(title,top+6,fg,True,11),(badge or '/'.join(lanes[node['lane']]),top+26,color,False,10),(ref[-7:]+'  ·  '+record.get('created_at','')[:19].replace('T',' '),top+45,muted,False,9)]:
                item=scene.addSimpleText(text,QtGui.QFont('Helvetica Neue',size))
                f=item.font();f.setBold(bold);item.setFont(f);item.setBrush(QtGui.QColor(c));item.setPos(text_x,y);item.setData(0,ref);item.setZValue(3);item.setToolTip(tooltip)
                if not matched:item.setOpacity(.23)
            if not matched:shape.setOpacity(.25)
        if not self.graph['nodes']:
            item=scene.addSimpleText('No versions yet. Add a USD file\nor watch native saves.');item.setBrush(QtGui.QColor(muted));item.setPos(16,20)
        scene.setSceneRect(0,0,width,max(self.ROW,len(positions)*self.ROW))
    def ref_at(self,pos):
        for item in self.items(pos):
            if item.data(0):return item.data(0)
        return None
    def mousePressEvent(self,event):
        if event.button()==QtCore.Qt.LeftButton:
            ref=self.ref_at(event.position().toPoint())
            if ref:self.select_ref(ref);self.openRequested.emit(ref);event.accept();return
        super().mousePressEvent(event)
    def contextMenuEvent(self,event):
        ref=self.ref_at(event.pos())
        if ref:self.menuRequested.emit(ref,event.globalPos())
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'graph'):self.redraw()
