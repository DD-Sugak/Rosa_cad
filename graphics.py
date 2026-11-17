"""Графический редактор схемы на QGraphicsScene/QGraphicsView."""
import math
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPen, QBrush, QColor, QPainter, QFont, QPixmap
from PySide6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsRectItem,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsTextItem, QMenu)
from config import *

def index_is_selected(data, selected_rods, selected_nodes):
    kind, index = data
    return index in (selected_rods if kind == "rod" else selected_nodes)


class ModelScene(QGraphicsScene):
    def __init__(self, owner):
        super().__init__(owner)
        self.owner = owner
        self.setBackgroundBrush(QBrush(QColor("#fff9fc")))

    def rebuild(self):
        self.blockSignals(True)
        selected_rods = set(self.owner.sel_rods)
        selected_nodes = set(self.owner.sel_nodes)
        self.clear()
        rods = self.owner.project["rods"]
        nodes = self.owner.project["nodes"]
        n = len(rods)

        # Базовая ширина модели рассчитывается для масштаба 100%.
        # При увеличении растут именно длины стержней в координатах сцены,
        # а не общий transform QGraphicsView.
        # каждому стержню выделяется минимальная видимая ширина,
        # остаток распределяется по логарифмическим весам длин.
        # Поэтому очень короткие стержни не схлопываются в ноль,
        # а более длинные всё равно визуально отличаются друг от друга.
        # Используем фактический размер viewport. Нельзя подменять его
        # условной минимальной шириной: при первом открытии редактора это
        # смещает модель до следующего resizeEvent (например, движения панели).
        viewport_width = max(1, self.owner.view.viewport().contentsRect().width())
        viewport_height = max(1, self.owner.view.viewport().contentsRect().height())
        scene_height = float(viewport_height)
        # Поля адаптируются к узкой рабочей области и не заставляют сцену
        # становиться шире viewport при масштабе 100%.
        margin = min(70.0, max(12.0, viewport_width * 0.08))
        left_margin = margin
        right_margin = margin
        available = max(float(viewport_width) - left_margin - right_margin, 1.0)
        zoom = float(getattr(self.owner, "zoom_factor", 1.0))

        lengths = [float(r["L"]) for r in rods]
        log_lengths = [math.log10(v) for v in lengths]
        min_log = min(log_lengths)
        weights = [1.0 + (v - min_log) for v in log_lengths]
        min_width = min(45.0, available / max(2 * n, 1))
        remaining = max(available - min_width * n, 0.0)
        weight_sum = sum(weights)
        base_widths = [
            min_width + remaining * weight / weight_sum
            for weight in weights
        ]
        # Важное отличие от обычного масштабирования картинки:
        # меняется длина каждого стержня в самой модели сцены.
        widths = [width * zoom for width in base_widths]
        content_width = sum(widths)
        # На 100% сцена в точности равна рабочей области, а конструкция
        # центрируется внутри неё. При увеличении сцена расширяется вместе
        # с геометрией стержней и получает поля для прокрутки.
        if zoom <= 1.0:
            scene_width = float(viewport_width)
            x = (scene_width - content_width) / 2.0
        else:
            # При увеличении задаём сцене гарантированно большую ширину,
            # чем viewport. Иначе QGraphicsView может показать дорожку
            # полосы прокрутки, но оставить диапазон 0 и скрыть ползунок.
            scene_width = max(
                float(viewport_width) * zoom,
                content_width + left_margin + right_margin
            )
            x = (scene_width - content_width) / 2.0
        cy = scene_height * 0.50
        self.rod_bounds, self.node_points = [], []
        areas = [max(float(r["A"]), 1e-300) for r in rods]
        logs = [math.log10(v) for v in areas]
        lo, hi = min(logs), max(logs)

        for i, rod in enumerate(rods):
            w = widths[i]
            x1, x2 = x, x + w
            xm = (x1 + x2) / 2
            self.rod_bounds.append((x1, x2, cy))
            self.node_points.append((x1, cy))
            selected = i in selected_rods
            thick = 9.0 if hi == lo else 6.0 + (logs[i] - lo) / (hi - lo) * 22.0

            rect = QGraphicsRectItem(x1, cy - thick / 2, w, thick)
            # Выделение обозначаем более светлым оттенком, а не почти чёрной заливкой:
            # синие стрелки и подписи нагрузки остаются контрастными.
            rect.setBrush(QBrush(QColor("#f4b2d0" if selected else PINK)))
            rect.setPen(QPen(QColor(DARK), 2.2 if selected else 1.5))
            rect.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable, True)
            rect.setData(0, ("rod", i))
            rect.setZValue(2)
            self.addItem(rect)

            # Номер стержня и размерные подписи остаются векторными объектами:
            # при масштабировании увеличивается сама геометрия, а не картинка.
            badge = QGraphicsEllipseItem(xm - 13, cy + 43, 26, 26)
            badge.setBrush(QBrush(QColor(WHITE)))
            badge.setPen(QPen(QColor(DARK), 1.5))
            badge.setZValue(3)
            self.addItem(badge)
            label = self.add_text(xm, cy + 56, str(i + 1), DARK, 10, True, center_y=True, center_x=True)
            label.setZValue(4)

            if self.owner.show_dims:
                dim = self.add_text(xm, cy + 78, f"L={rod['L']:g} м   A={rod['A']:g}", TEXT, 9)
                dim.setZValue(4)

            q = float(rod["q"])
            if q:
                direction = 1 if q > 0 else -1
                count = max(1, min(14, int(w / 28.0)))

                # По умолчанию q рисуется прямо на стержне.
                # Если включена галочка «q сверху стержня» — над ним.
                if self.owner.q_on_rod:
                    qy = cy
                    label_y = cy - thick / 2 - 22
                else:
                    qy = cy - 43
                    label_y = qy - 27

                for j in range(count):
                    px = x1 + w * (j + 0.5) / count
                    arrow_items = self.add_arrow(
                        px - direction * 9, qy,
                        px + direction * 9, qy, BLUE
                    )
                    for arrow_item in arrow_items:
                        arrow_item.setZValue(6)
                q_label = self.add_text(xm, label_y, f"q={abs(q):g}", BLUE, 10, True)
                q_label.setZValue(7)

            x = x2

        self.node_points.append((x, cy))

        for i, (nx, ny) in enumerate(self.node_points):
            node = nodes[i]
            selected = i in selected_nodes
            if node["support"]:
                self.add_line(nx, ny - 28, nx, ny + 28, DARK, 3)
                side = -1 if i == 0 else (1 if i == len(self.node_points) - 1 else -1)
                for k in range(-24, 25, 9):
                    if side < 0:
                        self.add_line(nx - 13, ny + k + 8, nx, ny + k, DARK, 1.2)
                    else:
                        self.add_line(nx, ny + k + 8, nx + 13, ny + k, DARK, 1.2)

            # Сила геометрически начинается в центре узла. Сначала рисуем
            # стрелку, затем узел поверх её начала: линия выходит из центра,
            # но не перечёркивает круглое обозначение.
            force = float(node["F"])
            if force:
                direction = 1 if force > 0 else -1
                force_items = self.add_arrow(nx, ny, nx + direction * 58, ny, RED)
                for force_item in force_items:
                    force_item.setZValue(6)
                force_label = self.add_text(
                    nx + direction * 31, ny - 35, f"F={abs(force):g}", RED, 10, True,
                    center_y=True, center_x=True
                )
                force_label.setZValue(8)

            dot = QGraphicsEllipseItem(nx - 7, ny - 7, 14, 14)
            dot.setBrush(QBrush(QColor(DARK if selected else WHITE)))
            dot.setPen(QPen(QColor(DARK), 2))
            dot.setFlag(QGraphicsEllipseItem.GraphicsItemFlag.ItemIsSelectable, True)
            dot.setData(0, ("node", i))
            dot.setZValue(7)
            self.addItem(dot)
            node_label = self.add_text(nx, ny + 30, str(i + 1), DARK, 10, True)
            node_label.setZValue(8)

        total = sum(lengths)
        self.add_text(scene_width / 2, scene_height - 72,
            f"Стержней: {n}     Узлов: {len(nodes)}     Общая длина: {total:g} м",
            TEXT, 11, True)
        # Сохраняем выделение при обновлении модели.
        for graphics_item in self.items():
            data = graphics_item.data(0)
            if data:
                graphics_item.setSelected(
                    index_is_selected(data, selected_rods, selected_nodes)
                )
        self.update_selection_appearance(selected_rods, selected_nodes)
        self.setSceneRect(QRectF(0, 0, scene_width, scene_height))
        self.owner.rod_bounds=self.rod_bounds
        self.owner.node_points=self.node_points
        self.owner.zoom_label.setText(f"Масштаб: {zoom * 100:.0f}%")
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
                item.setBrush(QBrush(QColor("#f4b2d0" if selected else PINK)))
                item.setPen(QPen(QColor(DARK), 2.2 if selected else 1.5))
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

    def add_text(self,x,y,text,color,size=10,bold=False,center_y=False,center_x=True):
        item=QGraphicsTextItem(str(text))
        item.setDefaultTextColor(QColor(color))
        item.document().setDocumentMargin(0)
        f=QFont(FONTS["bold"] if bold else FONTS["main"],size)
        f.setBold(bold); item.setFont(f)
        bounds = item.boundingRect()
        item.setPos(x-bounds.width()/2 if center_x else x, y-bounds.height()/2 if center_y else y)
        self.addItem(item); return item

    def add_line(self,x1,y1,x2,y2,color,width=1):
        item=QGraphicsLineItem(x1,y1,x2,y2)
        item.setPen(QPen(QColor(color),width)); self.addItem(item); return item

    def add_arrow(self, x1, y1, x2, y2, color):
        items = [self.add_line(x1, y1, x2, y2, color, 2)]
        angle = 0 if x2 >= x1 else math.pi
        size = 8
        for delta in (-.55, .55):
            items.append(self.add_line(
                x2, y2,
                x2 - size * math.cos(angle + delta),
                y2 - size * math.sin(angle + delta),
                color, 2
            ))
        return items

class ModelView(QGraphicsView):
    def __init__(self, scene, owner):
        super().__init__(scene, owner)
        self.owner=owner
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.setBackgroundBrush(QColor("#fff9fc"))
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)
        self._pan=False; self._last=None

    def paintEvent(self, event):
        # Закрываем индикатор только после того, как Qt действительно нарисовал
        # сцену. Это убирает паузу с белым экраном после исчезновения загрузки.
        super().paintEvent(event)
        if getattr(self.owner, "_editor_ready_to_paint", False) and getattr(self.owner, "_loading_dialog", None) is not None:
            self.owner._editor_ready_to_paint = False
            QTimer.singleShot(0, self.owner._finish_loading_dialog)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.scene() is not None:
            # Геометрия пересчитывается под новый размер области просмотра,
            # затем центр модели выставляется уже после layout/scrollbar pass.
            QTimer.singleShot(0, self._rebuild_after_resize)

    def _rebuild_after_resize(self):
        if self.scene() is None or not hasattr(self.owner, "zoom_label"):
            return
        self.scene().rebuild()
        self.setSceneRect(self.scene().sceneRect())
        if self.owner.zoom_factor <= 1.0:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            QTimer.singleShot(0, self._center_model)
        else:
            # При масштабе выше 100% полоса должна быть доступна сразу.
            # ScrollBarAsNeeded иногда скрывает её при повторном пересчёте
            # sceneRect/viewport, хотя геометрия модели уже увеличена.
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if not delta:
            event.accept()
            return
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - (80 if delta > 0 else -80))
            event.accept()
            return

        old_zoom = float(self.owner.zoom_factor)
        # Считываем положение курсора ДО перестроения сцены и изменения
        # размеров viewport из-за появления/исчезновения scrollbar.
        cursor_pos = event.position().toPoint()
        old_scene_x = self.mapToScene(cursor_pos).x()
        old_scene_width = max(self.scene().sceneRect().width(), 1.0)
        cursor_fraction = min(1.0, max(0.0, old_scene_x / old_scene_width))

        factor = 1.25 if delta > 0 else 1.0 / 1.25
        new_zoom = min(80.0, max(1.0, old_zoom * factor))
        if math.isclose(new_zoom, old_zoom, rel_tol=0.0, abs_tol=1e-9):
            event.accept()
            return

        # При 100% полоса прокрутки принудительно скрыта. При увеличении
        # включается AsNeeded, поэтому она появляется в тот же момент,
        # когда расширенная геометрия действительно выходит за viewport.
        self.owner.zoom_factor = new_zoom
        if new_zoom <= 1.0:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        else:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.resetTransform()  # меняется геометрия сцены, а не масштаб картинки
        self.scene().rebuild()
        self.setSceneRect(self.scene().sceneRect())
        self.horizontalScrollBar().setSingleStep(40)
        self.horizontalScrollBar().setPageStep(max(1, self.viewport().width()))

        if new_zoom <= 1.0:
            # Сброс: гарантированно убираем остаточное смещение и
            # центрируем базовую конструкцию после перерасчёта viewport.
            self.verticalScrollBar().setValue(0)
            QTimer.singleShot(0, self._center_model)
        else:
            # Сохраняем точку под курсором в координатах модели. Расчёт
            # выполняется после того, как Qt обновит диапазон scrollbar.
            cursor_x = cursor_pos.x()
            new_width = max(self.scene().sceneRect().width(), 1.0)
            target_x = cursor_fraction * new_width
            def restore_scroll(tx=target_x, cx=cursor_x):
                bar = self.horizontalScrollBar()
                bar.setPageStep(max(1, self.viewport().width()))
                bar.setValue(min(bar.maximum(), max(bar.minimum(), int(tx - cx))))
            QTimer.singleShot(0, restore_scroll)

        self.owner.zoom_label.setText(f"Масштаб: {new_zoom * 100:.0f}%")
        event.accept()

    def _center_model(self):
        if self.owner.zoom_factor <= 1.0 and self.scene() is not None:
            self.horizontalScrollBar().setValue(0)
            self.verticalScrollBar().setValue(0)
            # Геометрия модели уже рассчитана относительно фактического
            # viewport и центрирована в ModelScene.rebuild(). Дополнительный
            # centerOn здесь не нужен: он мог сдвигать сцену после resize.
            self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

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
