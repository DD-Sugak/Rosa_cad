"""Графический редактор схемы на QGraphicsScene/QGraphicsView."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QFont, QPixmap
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QMenu)
from config import *

def index_is_selected(data, selected_rods, selected_nodes):
    kind, index = data
    return index in (selected_rods if kind == "rod" else selected_nodes)


class ModelScene(QGraphicsScene):
    selection_changed = Signal()
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setBackgroundBrush(QBrush(QColor("#fff9fc")))
        self.selectionChanged.connect(self.selection_changed.emit)

    def rebuild(self):
        self.blockSignals(True)
        selected_rods = set(self.owner.sel_rods)
        selected_nodes = set(self.owner.sel_nodes)
        self.clear()
        rods = self.owner.project["rods"]
        nodes = self.owner.project["nodes"]
        n = len(rods)
        lengths = [max(float(r["L"]), 1e-9) for r in rods]
        # Геометрическая длина напрямую зависит от L: 1 м = 100 условных единиц.
        # fitInView автоматически подбирает масштаб для всей конструкции.
        widths = [max(35.0, min(2000.0, value * 100.0)) for value in lengths]
        x, cy = 70.0, 250.0
        self.rod_bounds, self.node_points = [], []
        areas=[max(float(r["A"]),1e-20) for r in rods]
        logs=[math.log10(v) for v in areas]
        lo,hi=min(logs),max(logs)
        for i, rod in enumerate(rods):
            w=widths[i]; x1,x2=x,x+w; xm=(x1+x2)/2
            self.rod_bounds.append((x1,x2,cy)); self.node_points.append((x1,cy))
            selected=i in selected_rods
            thick=9 if hi==lo else 6+(logs[i]-lo)/(hi-lo)*22
            rect=QGraphicsRectItem(x1,cy-thick/2,w,thick)
            rect.setBrush(QBrush(QColor(DARK if selected else PINK)))
            rect.setPen(QPen(QColor(DARK),3 if selected else 1.5))
            rect.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable,True)
            rect.setData(0,("rod",i)); rect.setZValue(2); self.addItem(rect)
            label=self.add_text(xm,cy+52,str(i+1),DARK,11,True)
            label.setZValue(4)
            if self.owner.show_dims:
                self.add_text(xm,cy+78,f"L={rod['L']:g} м   A={rod['A']:g}",TEXT,9)
            q=float(rod["q"])
            if q:
                direction=1 if q>0 else -1
                count=max(1,min(12,int(w/35)))
                qy = cy-17 if self.owner.q_on_rod else cy-48
                for j in range(count):
                    px=x1+w*(j+.5)/count
                    self.add_arrow(px-direction*9,qy,px+direction*9,qy,BLUE)
                self.add_text(xm,qy-27,f"q={abs(q):g}",BLUE,10,True)
            x=x2
        self.node_points.append((x,cy))
        for i,(nx,ny) in enumerate(self.node_points):
            node=nodes[i]; selected=i in selected_nodes
            if node["support"]:
                self.add_line(nx,ny-28,nx,ny+28,DARK,3)
                # У внутреннего/левого узла штриховка слева, у правого крайнего — справа.
                side = -1 if i == 0 else (1 if i == len(self.node_points)-1 else -1)
                for k in range(-24,25,9):
                    if side < 0:
                        self.add_line(nx-13,ny+k+8,nx,ny+k,DARK,1.2)
                    else:
                        self.add_line(nx,ny+k,nx+13,ny+k+8,DARK,1.2)
            dot=QGraphicsEllipseItem(nx-7,ny-7,14,14)
            dot.setBrush(QBrush(QColor(DARK if selected else WHITE)))
            dot.setPen(QPen(QColor(DARK),2))
            dot.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable,True)
            dot.setData(0,("node",i)); dot.setZValue(5); self.addItem(dot)
            self.add_text(nx,ny+30,str(i+1),DARK,10,True)
            force=float(node["F"])
            if force:
                direction=1 if force>0 else -1
                self.add_arrow(nx,ny-1,nx+direction*55,ny-1,RED)
                self.add_text(nx+direction*28,ny-40,f"F={abs(force):g}",RED,10,True)
        total=sum(lengths)
        self.add_text(max(x/2,500),390,
            f"Стержней: {n}     Узлов: {len(nodes)}     Общая длина: {total:g} м",
            TEXT,11,True)
        self.add_text(max(x/2,500),415,
            "Красная стрелка — сила F, синие стрелки — нагрузка q. Знак «+» направлен вправо.",
            MUTED,9)
        # Сохраняем выделение при обновлении модели.
        for graphics_item in self.items():
            data = graphics_item.data(0)
            if data:
                graphics_item.setSelected(
                    index_is_selected(data, selected_rods, selected_nodes)
                )
        self.update_selection_appearance(selected_rods, selected_nodes)
        self.setSceneRect(QRectF(0,0,max(x+100,1100),470))
        self.owner.rod_bounds=self.rod_bounds
        self.owner.node_points=self.node_points
        self.owner.zoom_label.setText(f"Масштаб: ×{self.owner.view.transform().m11():.2f}")
        self.blockSignals(False)

    def update_selection_appearance(self, selected_rods=None, selected_nodes=None):
        selected_rods = self.owner.sel_rods if selected_rods is None else selected_rods
        selected_nodes = self.owner.sel_nodes if selected_nodes is None else selected_nodes
        for item in self.items():
            data = item.data(0)
            if not data:
                continue
            kind, index = data
            selected = index in (selected_rods if kind == "rod" else selected_nodes)
            if kind == "rod" and isinstance(item, QGraphicsRectItem):
                item.setBrush(QBrush(QColor(DARK if selected else PINK)))
                item.setPen(QPen(QColor(DARK), 3 if selected else 1.5))
            elif kind == "node" and isinstance(item, QGraphicsEllipseItem):
                item.setBrush(QBrush(QColor(DARK if selected else WHITE)))
                item.setPen(QPen(QColor(DARK), 2))

    def apply_selection(self, selected_rods, selected_nodes):
        self.blockSignals(True)
        for item in self.items():
            data = item.data(0)
            if data:
                kind, index = data
                item.setSelected(index in (selected_rods if kind == "rod" else selected_nodes))
        self.update_selection_appearance(selected_rods, selected_nodes)
        self.blockSignals(False)

    def add_text(self,x,y,text,color,size=10,bold=False):
        item=QGraphicsTextItem(str(text))
        item.setDefaultTextColor(QColor(color))
        f=QFont(FONTS["bold"] if bold else FONTS["main"],size)
        f.setBold(bold); item.setFont(f)
        item.setPos(x-item.boundingRect().width()/2,y)
        self.addItem(item); return item

    def add_line(self,x1,y1,x2,y2,color,width=1):
        item=QGraphicsLineItem(x1,y1,x2,y2)
        item.setPen(QPen(QColor(color),width)); self.addItem(item); return item

    def add_arrow(self,x1,y1,x2,y2,color):
        self.add_line(x1,y1,x2,y2,color,2)
        angle=0 if x2>=x1 else math.pi
        size=8
        for delta in (-.55,.55):
            self.add_line(x2,y2,x2-size*math.cos(angle+delta),y2-size*math.sin(angle+delta),color,2)

class ModelView(QGraphicsView):
    def __init__(self, scene, owner):
        super().__init__(scene, owner)
        self.owner=owner
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#fff9fc"))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self._pan=False; self._last=None

    def wheelEvent(self,event):
        factor=1.2 if event.angleDelta().y()>0 else 1/1.2
        current=self.transform().m11()
        if current*factor<0.02 or current*factor>30:
            event.accept()
            return
        self.scale(factor,factor)
        event.accept()
        self.owner.zoom_label.setText(f"Масштаб: ×{self.transform().m11():.2f}")

    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton:
            self._pan=True; self._last=event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor); event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self._pan and self._last is not None:
            delta=event.position().toPoint()-self._last; self._last=event.position().toPoint()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value()-delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value()-delta.y())
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        if event.button()==Qt.MouseButton.MiddleButton and self._pan:
            self._pan=False; self._last=None; self.unsetCursor(); event.accept(); return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self,event):
        item=self.itemAt(event.pos())
        data=item.data(0) if item else None
        if not data:
            return super().contextMenuEvent(event)
        kind,index=data
        menu=QMenu(self)
        if kind=="rod":
            menu.addAction("Дублировать стержень",lambda:self.owner.duplicate_rod(index))
            menu.addAction("Удалить стержень",lambda:self.owner.delete_rods({index}))
        else:
            node=self.owner.project["nodes"][index]
            menu.addAction("Снять опору" if node["support"] else "Поставить опору",
                           lambda:self.owner.toggle_support(index))
        menu.exec(event.globalPos())
