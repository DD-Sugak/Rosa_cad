"""Главное окно ROSA CAD (PySide6)."""
import json, os, math, sys, subprocess, shutil
from pathlib import Path
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap, QFont, QKeySequence, QShortcut
from PySide6.QtWidgets import (QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QLabel,
    QPushButton,QFrame,QSplitter,QListWidget,QListWidgetItem,QTabWidget,QLineEdit,
    QCheckBox,QScrollArea,QMessageBox,QFileDialog,QStatusBar,QMenu,QToolBar,
    QSizePolicy,QGroupBox,QFormLayout,QAbstractItemView)
from config import *
from graphics import ModelScene, ModelView

class RosaCAD(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1440,900)
        self.setMinimumSize(1050,680)
        self.project=None; self.project_path=None
        self.sel_rods=set(); self.sel_nodes=set()
        self.selected_type=None; self.selected_index=None
        self.entries={}; self.name_entry=None
        self.sound_on=True; self.show_dims=True; self.q_on_rod=True
        self.rod_bounds=[]; self.node_points=[]
        self._intro_done=False
        self._sounds={}
        self._last_selected_rods=set()
        self._init_sounds()
        self.setStatusBar(QStatusBar())
        self.show_home()

    def make_button(self,text,callback,primary=False):
        b=QPushButton(text)
        if primary: b.setObjectName("primary")
        b.clicked.connect(lambda: (self.play("click"),callback()))
        b.setMinimumHeight(38)
        return b

    def _init_sounds(self):
        """Загружает WAV один раз; постоянные QSoundEffect устраняют гонки winsound."""
        try:
            from PySide6.QtMultimedia import QSoundEffect
            for path in (ASSETS / "sounds").glob("*.wav"):
                effect = QSoundEffect(self)
                effect.setSource(QUrl.fromLocalFile(str(path.resolve())))
                effect.setVolume(0.35)
                self._sounds[path.stem] = effect
        except Exception:
            # Если в системе нет аудиобэкенда Qt, play() использует системный fallback.
            self._sounds = {}

    def play(self,name):
        if not self.sound_on:
            return
        effect = self._sounds.get(name)
        if effect is not None:
            try:
                if effect.isPlaying():
                    effect.stop()
                effect.play()
                return
            except Exception:
                pass
        path=ASSETS/"sounds"/f"{name}.wav"
        if not path.exists():
            return
        try:
            if sys.platform.startswith("win"):
                import winsound
                winsound.PlaySound(str(path),winsound.SND_FILENAME|winsound.SND_ASYNC)
            elif sys.platform=="darwin":
                subprocess.Popen(["afplay",str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            else:
                player=shutil.which("paplay") or shutil.which("aplay")
                if player:
                    subprocess.Popen([player,str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def status(self,text,color=GREEN):
        self.statusBar().showMessage(text,8000)
        self.statusBar().setStyleSheet(f"color:{color};")

    def ask_save_current(self):
        if self.project is None: return True
        answer=QMessageBox.question(self,"Текущий проект",
            "Сохранить текущий проект перед продолжением?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No|QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes)
        if answer==QMessageBox.StandardButton.Cancel: return False
        if answer==QMessageBox.StandardButton.Yes: return self.save_project()
        return True

    def show_home(self):
        self._clear()
        root=QWidget(); root.setObjectName("home")
        layout=QVBoxLayout(root); layout.setContentsMargins(30,30,30,30)
        layout.addStretch()
        card=QFrame(); card.setObjectName("card"); card.setMaximumWidth(540)
        card.setStyleSheet("QFrame#card {background:rgba(255,255,255,235); border:2px solid #952961; border-radius:22px;}")
        card_layout=QVBoxLayout(card); card_layout.setContentsMargins(45,35,45,35); card_layout.setSpacing(14)
        title=QLabel("ROSA CAD"); title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(f"font-family:'{FONTS['title']}';font-size:38pt;color:{DARK};")
        subtitle=QLabel("Система автоматизации прочностных расчётов")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(title); card_layout.addWidget(subtitle); card_layout.addSpacing(16)
        card_layout.addWidget(self.make_button("Создать новый проект",self.new_project,True))
        card_layout.addWidget(self.make_button("Открыть последний проект",self.open_last_project))
        card_layout.addWidget(self.make_button("Открыть проект",self.open_project))
        if self.project is not None:
            card_layout.addWidget(self.make_button("Вернуться к редактору",self.show_editor))
        card_layout.addWidget(self.make_button("Выход",self.close))
        holder=QHBoxLayout(); holder.addStretch(); holder.addWidget(card); holder.addStretch()
        layout.addLayout(holder); layout.addStretch()
        bg=ASSETS/"bg.png"
        if bg.exists():
            pix=QPixmap(str(bg))
            root.setStyleSheet(f"QWidget#home {{border-image:url('{bg.as_posix()}') 0 0 0 0 stretch stretch;}}")
        self.setCentralWidget(root)
        self.statusBar().showMessage("ROSA CAD — препроцессор стержневых систем")
        if not self._intro_done:
            self._intro_done=True; QTimer.singleShot(350,lambda:self.play("meow"))

    def _clear(self):
        self.setCentralWidget(QWidget())

    def show_editor(self):
        if self.project is None: self.project=empty_project()
        self._clear()
        central=QWidget(); outer=QVBoxLayout(central); outer.setContentsMargins(10,10,10,8); outer.setSpacing(8)
        bar=QHBoxLayout()
        logo=QLabel("ROSA CAD"); logo.setStyleSheet(f"font-family:'{FONTS['title']}';font-size:23pt;color:{DARK};")
        bar.addWidget(logo)
        self.title_label=QLabel(self.project.get("name","Новый проект"))
        self.title_label.setStyleSheet(f"font-family:'{FONTS['bold']}';font-size:15pt;color:{DARK};")
        bar.addWidget(self.title_label); bar.addStretch()
        for text,fn in [("На главную",self.back_home),("Новый",self.new_project),("Открыть",self.open_project),("Сохранить",self.save_project),("Сохранить как",self.save_project_as),("Диагностика",self.run_diagnostics)]:
            bar.addWidget(self.make_button(text,fn,text=="Сохранить"))
        outer.addLayout(bar)
        tools=QHBoxLayout()
        for text,fn in [("＋ Добавить стержень",self.add_rod),("− Удалить выбранные",self.delete_selected),("Дублировать",self.duplicate_selected),("Показать всё",self.zoom_fit),("Сброс масштаба",self.zoom_reset)]:
            tools.addWidget(self.make_button(text,fn))
        self.dims_check=QCheckBox("Размеры"); self.dims_check.setChecked(self.show_dims); self.dims_check.toggled.connect(self.toggle_dims)
        self.sound_check=QCheckBox("Звуки"); self.sound_check.setChecked(self.sound_on); self.sound_check.toggled.connect(lambda v:setattr(self,"sound_on",v))
        self.q_position_check=QCheckBox("q на стержне"); self.q_position_check.setChecked(self.q_on_rod)
        self.q_position_check.toggled.connect(self.toggle_q_position)
        tools.addWidget(self.dims_check); tools.addWidget(self.sound_check); tools.addWidget(self.q_position_check); tools.addStretch()
        self.zoom_label=QLabel("Масштаб: ×1.00"); tools.addWidget(self.zoom_label)
        outer.addLayout(tools)
        splitter=QSplitter(Qt.Orientation.Horizontal)
        left=QWidget(); ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0)
        self.scene=ModelScene(self); self.view=ModelView(self.scene,self)
        ll.addWidget(self.view,1)
        lists=QTabWidget()
        self.rod_list=QListWidget(); self.node_list=QListWidget()
        self.rod_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.node_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.rod_list.itemSelectionChanged.connect(lambda:self.list_multi_select("rod"))
        self.node_list.itemSelectionChanged.connect(lambda:self.list_multi_select("node"))
        lists.addTab(self.rod_list,"Стержни"); lists.addTab(self.node_list,"Узлы")
        lists.setMaximumHeight(170); ll.addWidget(lists)
        splitter.addWidget(left)
        right=QFrame(); right.setObjectName("card"); right.setMinimumWidth(300); right.setMaximumWidth(390)
        rl=QVBoxLayout(right); self.panel_title=QLabel("Свойства модели")
        self.panel_title.setStyleSheet(f"font-family:'{FONTS['bold']}';font-size:16pt;color:{DARK};")
        rl.addWidget(self.panel_title)
        self.panel_scroll=QScrollArea(); self.panel_scroll.setWidgetResizable(True)
        self.panel_body=QWidget(); self.panel_layout=QVBoxLayout(self.panel_body); self.panel_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.panel_scroll.setWidget(self.panel_body); rl.addWidget(self.panel_scroll)
        splitter.addWidget(right); splitter.setSizes([1050,340]); outer.addWidget(splitter,1)
        self.setCentralWidget(central)
        self.refresh_lists(); self.refresh_panel(); self.scene.rebuild()
        self.scene.selection_changed.connect(self.scene_selection_changed)
        self._install_shortcuts()
        self.status("Редактор готов. Колесо — масштаб, средняя кнопка — перемещение.",TEXT)
        # Дожидаемся расчёта геометрии виджетов и вписываем всю модель в рабочую область.
        QTimer.singleShot(0, self.zoom_fit)

    def refresh_lists(self):
        self.rod_list.blockSignals(True); self.node_list.blockSignals(True)
        self.rod_list.clear(); self.node_list.clear()
        for i,r in enumerate(self.project["rods"]):
            self.rod_list.addItem(f"{i+1}. L={r['L']:g} м | A={r['A']:g} м² | q={r['q']:g}")
        for i,n in enumerate(self.project["nodes"]):
            self.node_list.addItem(f"{i+1}. F={n['F']:g} Н | {'Опора' if n['support'] else 'Свободный'}")
        self.rod_list.blockSignals(False); self.node_list.blockSignals(False)

    def refresh_scene(self):
        self.scene.rebuild()
        self.refresh_lists()
        self.title_label.setText(self.project.get("name","Новый проект"))

    def scene_selection_changed(self):
        rods=set(); nodes=set()
        for item in self.scene.selectedItems():
            data=item.data(0)
            if data:
                (rods if data[0]=="rod" else nodes).add(data[1])
        newly_selected = rods - self._last_selected_rods
        if newly_selected:
            self.play("select")
        self._last_selected_rods = set(rods)
        self.sel_rods,self.sel_nodes=rods,nodes
        self._derive_selection()
        self.refresh_panel()
        # Не пересоздаём сотни графических объектов при каждом клике:
        # обновляем только оформление уже существующих элементов.
        self.scene.update_selection_appearance(self.sel_rods, self.sel_nodes)

    def _derive_selection(self):
        if len(self.sel_rods)==1 and not self.sel_nodes:
            self.selected_type="rod"; self.selected_index=next(iter(self.sel_rods))
        elif len(self.sel_nodes)==1 and not self.sel_rods:
            self.selected_type="node"; self.selected_index=next(iter(self.sel_nodes))
        elif not self.sel_rods and not self.sel_nodes:
            self.selected_type=None; self.selected_index=None
        else:
            self.selected_type="multi"; self.selected_index=None

    def list_multi_select(self,kind):
        widget = self.rod_list if kind == "rod" else self.node_list
        indexes = {self.rod_list.row(item) if kind == "rod" else self.node_list.row(item)
                   for item in widget.selectedItems()}
        if kind == "rod":
            self.sel_rods, self.sel_nodes = indexes, set()
        else:
            self.sel_nodes, self.sel_rods = indexes, set()
        self._derive_selection()
        if kind == "rod" and indexes - self._last_selected_rods:
            self.play("select")
        self._last_selected_rods = set(self.sel_rods)
        self.refresh_panel()
        self.scene.apply_selection(self.sel_rods, self.sel_nodes)

    def list_select(self,kind,index):
        # Совместимость со старыми вызовами.
        if index >= 0:
            widget = self.rod_list if kind == "rod" else self.node_list
            widget.clearSelection(); widget.item(index).setSelected(True)

    def _install_shortcuts(self):
        shortcuts = {
            "Delete": self.delete_selected,
            "Ctrl+D": self.duplicate_selected,
            "Ctrl+S": self.save_project,
            "Ctrl+Shift+S": self.save_project_as,
            "Ctrl+N": self.new_project,
            "Ctrl+O": self.open_project,
            "Ctrl+0": self.zoom_reset,
            "F": self.zoom_fit,
            "Escape": self.clear_selection,
        }
        self._shortcuts=[]
        for sequence, callback in shortcuts.items():
            shortcut=QShortcut(QKeySequence(sequence),self)
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
            shortcut.activated.connect(callback)
            self._shortcuts.append(shortcut)

    def clear_selection(self):
        self.sel_rods=set(); self.sel_nodes=set(); self._derive_selection()
        self.scene.clearSelection()
        self.refresh_panel()

    def clear_panel(self):
        while self.panel_layout.count():
            item=self.panel_layout.takeAt(0); w=item.widget()
            if w:w.deleteLater()
        self.entries={}; self.name_entry=None

    def section(self,text):
        label=QLabel(text); label.setStyleSheet(f"font-family:'{FONTS['bold']}';font-size:14pt;color:{DARK};margin-top:7px;")
        self.panel_layout.addWidget(label)

    def add_field(self,key,title,value):
        label=QLabel(title); self.panel_layout.addWidget(label)
        edit=QLineEdit("" if value is None else fmt(value))
        edit.setPlaceholderText("Не изменять" if value is None else "")
        edit.editingFinished.connect(lambda e=edit,k=key:self.field_changed(e,k))
        self.panel_layout.addWidget(edit); self.entries[key]=edit

    def refresh_panel(self):
        if not hasattr(self,"panel_layout"):return
        self.clear_panel()
        if self.selected_type=="rod":
            i=self.selected_index; rod=self.project["rods"][i]
            self.panel_title.setText(f"Стержень {i+1}")
            self.section("Геометрия и материал")
            for k in ("L","A","E","sigma"):self.add_field(k,ROD_TITLES[k],rod[k])
            self.section("Распределённая нагрузка"); self.add_field("q",ROD_TITLES["q"],rod["q"])
            self.panel_layout.addWidget(self.make_button("Применить изменения",self.apply_fields,True))
        elif self.selected_type=="node":
            i=self.selected_index; node=self.project["nodes"][i]
            self.panel_title.setText(f"Узел {i+1}")
            self.add_field("F","Продольная сила F, Н (+ вправо)",node["F"])
            check=QCheckBox("Жёсткая опора (u = 0)"); check.setChecked(bool(node["support"]))
            check.toggled.connect(lambda v,idx=i:self.set_support(idx,v)); self.panel_layout.addWidget(check)
            self.panel_layout.addWidget(self.make_button("Применить изменения",self.apply_fields,True))
        elif self.selected_type=="multi":
            self.panel_title.setText("Групповое выделение")
            self.section(f"Выбрано стержней: {len(self.sel_rods)}, узлов: {len(self.sel_nodes)}")
            if self.sel_rods:
                self.section("Параметры стержней (пустые поля не изменяются)")
                for k in ROD_KEYS:self.add_field(k,ROD_TITLES[k],None)
            if self.sel_nodes:
                self.section("Параметры узлов")
                self.add_field("F","Продольная сила F, Н (+ вправо)",None)
                check=QCheckBox("Установить жёсткую опору для всех выбранных узлов")
                check.setTristate(True); check.setCheckState(Qt.CheckState.PartiallyChecked)
                check.stateChanged.connect(lambda state: self.batch_support(state))
                self.panel_layout.addWidget(check)
            self.panel_layout.addWidget(self.make_button("Применить ко всем выбранным",self.apply_batch,True))
            self.panel_layout.addWidget(self.make_button("Удалить выбранные стержни",self.delete_selected))
        else:
            self.panel_title.setText("Свойства модели"); self.section("Модель")
            self.panel_layout.addWidget(QLabel(f"Стержней: {len(self.project['rods'])}    Узлов: {len(self.project['nodes'])}"))
            self.panel_layout.addWidget(QLabel("Название проекта"))
            self.name_entry=QLineEdit(self.project.get("name",""))
            self.name_entry.editingFinished.connect(self.collect_name)
            self.panel_layout.addWidget(self.name_entry)
            hint=QLabel("Выберите стержень или узел на схеме либо в списке, чтобы изменить его параметры.")
            hint.setWordWrap(True); hint.setStyleSheet(f"color:{MUTED};")
            self.panel_layout.addWidget(hint)
        self.panel_layout.addStretch()

    def field_changed(self,edit,key):
        if self.selected_type=="multi" and not edit.text().strip():return
        try:
            value=parse_number(edit.text(),key)
            edit.setStyleSheet(f"border:1px solid {GREEN};")
            if self.selected_type!="multi": self.apply_fields()
        except ValueError as e:
            edit.setStyleSheet(f"border:1px solid {RED};"); self.status(str(e),RED)

    def apply_fields(self):
        try:
            if self.selected_type=="rod":
                values={k:parse_number(e.text(),k) for k,e in self.entries.items()}
                self.project["rods"][self.selected_index].update(values)
            elif self.selected_type=="node":
                values={k:parse_number(e.text(),k) for k,e in self.entries.items()}
                self.project["nodes"][self.selected_index].update(values)
            self.refresh_scene(); self.status("Изменения применены."); self.play("success")
            return True
        except ValueError as e:
            QMessageBox.warning(self,"Ошибка ввода",str(e)); self.status(str(e),RED); return False

    def apply_batch(self):
        try:
            values={k:parse_number(e.text(),k) for k,e in self.entries.items() if e.text().strip()}
            if not values: raise ValueError("Заполните хотя бы одно поле.")
            for i in self.sel_rods:self.project["rods"][i].update({k:v for k,v in values.items() if k in ROD_KEYS})
            if "F" in values:
                for i in self.sel_nodes:self.project["nodes"][i]["F"]=values["F"]
            self.refresh_scene(); self.refresh_panel(); self.status("Параметры применены к выбранным объектам.")
            self.play("success")
        except ValueError as e:QMessageBox.warning(self,"Ошибка ввода",str(e))

    def batch_support(self,state):
        if state == int(Qt.CheckState.PartiallyChecked): return
        value = state == int(Qt.CheckState.Checked)
        for i in self.sel_nodes:
            self.project["nodes"][i]["support"] = value
        self.refresh_scene(); self.refresh_panel()

    def collect_name(self):
        if self.name_entry and self.name_entry.text().strip():
            self.project["name"]=self.name_entry.text().strip()
            self.title_label.setText(self.project["name"])

    def add_rod(self):
        self.project["rods"].append(default_rod())
        self.project["nodes"].append({"F":0.0,"support":False})
        self.sel_rods={len(self.project["rods"])-1}; self.sel_nodes=set(); self._derive_selection()
        self.refresh_scene(); self.refresh_panel(); self.play("add")

    def duplicate_rod(self,index=None):
        if index is None:index=next(iter(self.sel_rods),None)
        if index is None:return
        self.project["rods"].insert(index+1,dict(self.project["rods"][index]))
        self.project["nodes"].insert(index+1,{"F":0.0,"support":False})
        self.sel_rods={index+1}; self.sel_nodes=set(); self._derive_selection()
        self.refresh_scene(); self.refresh_panel(); self.play("add")

    def duplicate_selected(self):
        indexes=sorted(self.sel_rods)
        if not indexes: return
        inserted=[]
        offset=0
        for original in indexes:
            pos=original+offset+1
            self.project["rods"].insert(pos,dict(self.project["rods"][original+offset]))
            self.project["nodes"].insert(pos,{"F":0.0,"support":False})
            inserted.append(pos); offset+=1
        self.sel_rods=set(inserted); self.sel_nodes=set(); self._derive_selection()
        self.refresh_scene(); self.refresh_panel(); self.play("add")

    def delete_selected(self):
        self.delete_rods(set(self.sel_rods))

    def delete_rods(self,indexes):
        if not indexes:return
        if len(indexes)>=len(self.project["rods"]):
            QMessageBox.information(self,"Удаление","Нельзя удалить все стержни — в модели должен остаться хотя бы один.");return
        names=", ".join(str(i+1) for i in sorted(indexes))
        if QMessageBox.question(self,"Удаление",f"Удалить стержни: {names}?")!=QMessageBox.StandardButton.Yes:return
        for i in sorted(indexes,reverse=True):
            left,right=self.project["nodes"][i],self.project["nodes"][i+1]
            left["F"]=float(left["F"])+float(right["F"])
            left["support"]=bool(left["support"] or right["support"])
            self.project["rods"].pop(i); self.project["nodes"].pop(i+1)
        self.sel_rods=set();self.sel_nodes=set();self._derive_selection()
        self.refresh_scene();self.refresh_panel();self.play("delete")

    def toggle_support(self,index):
        node=self.project["nodes"][index];node["support"]=not bool(node["support"])
        self.refresh_scene();self.refresh_panel()

    def set_support(self,index,value):
        self.project["nodes"][index]["support"]=bool(value)
        self.refresh_scene()

    def toggle_dims(self,value):
        self.show_dims=bool(value)
        if hasattr(self,"scene"):self.scene.rebuild()

    def toggle_q_position(self,value):
        self.q_on_rod=bool(value)
        if hasattr(self,"scene"): self.scene.rebuild()

    def zoom_fit(self):
        self.view.resetTransform()
        rect=self.scene.itemsBoundingRect().adjusted(-55,-55,55,55)
        self.view.fitInView(rect,Qt.AspectRatioMode.KeepAspectRatio)
        self.zoom_label.setText(f"Масштаб: ×{self.view.transform().m11():.2f}")

    def zoom_reset(self):
        self.view.resetTransform()
        self.zoom_label.setText("Масштаб: ×1.00")

    def validate_model(self):
        validate_project(self.project)

    def run_diagnostics(self):
        try:self.validate_model()
        except ValueError as e:QMessageBox.critical(self,"Диагностика данных",str(e));self.status(str(e),RED);return
        warnings=[]
        loaded=any(float(n["F"])!=0 for n in self.project["nodes"]) or any(float(r["q"])!=0 for r in self.project["rods"])
        if not loaded:warnings.append("Нагрузки не заданы — перемещения будут нулевыми.")
        for i,node in enumerate(self.project["nodes"]):
            if node["support"] and float(node["F"])!=0:warnings.append(f"Узел {i+1}: сила приложена в закреплённый узел (она уйдёт в реакцию опоры).")
        if warnings:QMessageBox.warning(self,"Диагностика данных","\n".join(warnings))
        else:QMessageBox.information(self,"Диагностика данных","Ошибок не найдено. Модель корректна.")
        self.status("Диагностика завершена.")

    def new_project(self):
        if not self.ask_save_current():return
        self.project=empty_project();self.project_path=None
        self.sel_rods=set();self.sel_nodes=set();self.show_editor()

    def open_project(self):
        path,_=QFileDialog.getOpenFileName(self,"Открыть проект","", "Проекты ROSA CAD (*.json);;Все файлы (*.*)")
        if path:self.load_project(path)

    def open_last_project(self):
        try:
            data=json.loads(LAST_FILE.read_text(encoding="utf-8"));path=data["path"]
            if not os.path.exists(path):raise FileNotFoundError
            self.load_project(path)
        except Exception:QMessageBox.information(self,"ROSA CAD","Последний сохранённый проект не найден.")

    def load_project(self,path):
        try:
            data=json.loads(Path(path).read_text(encoding="utf-8"))
            validate_project(data)
            for rod in data["rods"]:
                for key in ROD_KEYS:rod[key]=float(rod[key])
            for node in data["nodes"]:
                node["F"]=float(node["F"]);node["support"]=bool(node["support"])
            data.setdefault("name",Path(path).stem)
        except Exception as e:QMessageBox.critical(self,"Ошибка открытия проекта",str(e));return
        self.project=data;self.project_path=path;self.sel_rods=set();self.sel_nodes=set()
        self.remember_last_project();self.show_editor()

    def remember_last_project(self):
        if not self.project_path:return
        try:
            CONFIG_DIR.mkdir(parents=True,exist_ok=True)
            LAST_FILE.write_text(json.dumps({"path":self.project_path},ensure_ascii=False,indent=2),encoding="utf-8")
        except OSError:pass

    def save_project(self,save_as=False):
        try:
            if self.selected_type=="rod":self.apply_fields()
            elif self.selected_type=="node":self.apply_fields()
            self.validate_model()
            if save_as or not self.project_path:
                path,_=QFileDialog.getSaveFileName(self,"Сохранить проект",self.project.get("name","project")+".json","Проекты ROSA CAD (*.json)")
                if not path:return False
                if not path.lower().endswith(".json"):path+=".json"
                self.project_path=path
            Path(self.project_path).write_text(json.dumps(self.project,ensure_ascii=False,indent=4),encoding="utf-8")
            self.remember_last_project();self.status(f"Проект сохранён: {self.project_path}");self.play("success");return True
        except Exception as e:QMessageBox.critical(self,"Ошибка сохранения",str(e));return False

    def save_project_as(self):return self.save_project(True)

    def back_home(self):
        self.show_home()
