"""Общие настройки и модель данных ROSA CAD."""
from pathlib import Path
import json, math, os, sys

APP_NAME = "ROSA CAD"
ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
CONFIG_DIR = Path.home() / ".rosa_cad"
LAST_FILE = CONFIG_DIR / "last_project.json"

BG = "#fdeef5"
PANEL = "#ffffff"
PINK = "#ea86bb"
DARK = "#952961"
LIGHT = "#fbe1ee"
TEXT = "#5a1a3d"
BTN_TEXT = "#4a0f33"
RED = "#d94b65"
GREEN = "#478b70"
BLUE = "#2f6db5"
WHITE = "#ffffff"
MUTED = "#8a6a7c"

ROD_KEYS = ("L", "A", "E", "sigma", "q")
POSITIVE_KEYS = ("L", "A", "E", "sigma")
ROD_TITLES = {
    "L": "Длина L, м",
    "A": "Площадь сечения A, м²",
    "E": "Модуль упругости E, Па",
    "sigma": "Допускаемое напряжение [σ], Па",
    "q": "Погонная нагрузка q, Н/м",
}
FONT_FILES = {"main":"Main.ttf", "bold":"Bold.ttf", "title":"Title.ttf"}
FONTS = {"main":"Caveat", "bold":"Caveat", "title":"Nautilus Pompilius"}

def fmt(value):
    return format(float(value), ".10g")

def parse_number(value, key):
    try:
        number = float(str(value).strip().replace(",", "."))
    except (ValueError, TypeError):
        raise ValueError(f"Поле «{key}»: введено не число.")
    if not math.isfinite(number):
        raise ValueError(f"Поле «{key}»: значение должно быть конечным.")
    if key in POSITIVE_KEYS and number <= 0:
        raise ValueError(f"Поле «{key}»: значение должно быть больше нуля.")
    return number

def default_rod(length=1.0):
    return {"L":float(length), "A":0.01, "E":2.1e11, "sigma":2.4e8, "q":0.0}

def empty_project():
    return {"name":"Новый проект", "rods":[default_rod(1.0)],
            "nodes":[{"F":0.0,"support":True},{"F":0.0,"support":False}]}

def validate_project(project):
    if not isinstance(project, dict) or not isinstance(project.get("rods"), list) or not isinstance(project.get("nodes"), list):
        raise ValueError("Неверный формат проекта.")
    if not project["rods"]:
        raise ValueError("В модели должен остаться хотя бы один стержень.")
    if len(project["nodes"]) != len(project["rods"]) + 1:
        raise ValueError("Количество узлов должно быть на один больше количества стержней.")
    for i, rod in enumerate(project["rods"]):
        for key in ROD_KEYS:
            if key not in rod:
                raise ValueError(f"Стержень {i+1}: отсутствует параметр {key}.")
            parse_number(rod[key], key)
    for i, node in enumerate(project["nodes"]):
        if "F" not in node or "support" not in node:
            raise ValueError(f"Узел {i+1}: неполные данные.")
        parse_number(node["F"], "F")
    if not any(bool(n["support"]) for n in project["nodes"]):
        raise ValueError("Не задано ни одного закрепления: конструкция кинематически изменяема.")
    return True

def load_fonts(app):
    """Подключает все шрифты из assets/fonts; применяет их ко всему Qt-интерфейсу."""
    from PySide6.QtGui import QFontDatabase, QFont
    loaded = {}
    for role, filename in FONT_FILES.items():
        path = ASSETS / "fonts" / filename
        if path.exists():
            font_id = QFontDatabase.addApplicationFont(str(path))
            families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
            if families:
                loaded[role] = families[0]
    FONTS.update({**FONTS, **loaded})
    app.setFont(QFont(FONTS["main"], 11))
    return FONTS

def stylesheet():
    return f"""
    QWidget {{ background:{BG}; color:{TEXT}; font-family:'{FONTS['main']}'; font-size:12pt; }}
    QMainWindow, QDialog {{ background:{BG}; }}
    QFrame#card, QGroupBox, QTabWidget::pane {{ background:{PANEL}; border:1px solid {DARK}; border-radius:12px; }}
    QPushButton {{
      background:{PANEL}; color:{TEXT}; border:1px solid {DARK}; border-radius:10px;
      padding:7px 14px; font-family:'{FONTS['bold']}'; font-size:13pt;
    }}
    QPushButton:hover {{ background:{LIGHT}; }}
    QPushButton:pressed {{ background:{PINK}; }}
    QPushButton#primary {{ background:{PINK}; color:{BTN_TEXT}; border:2px solid {DARK}; }}
    QPushButton#primary:hover {{ background:#f2a4ca; }}
    QCheckBox {{ spacing:8px; }}
    QCheckBox::indicator {{
      width:17px; height:17px; background:#ffffff;
      border:1px solid {DARK}; border-radius:3px;
    }}
    QCheckBox::indicator:checked {{
      background:#ffffff; border:2px solid {DARK};
      image: url('{(ASSETS / "checkmark.png").as_posix()}');
    }}
    QCheckBox::indicator:unchecked {{ background:#ffffff; }}
    QCheckBox::indicator:checked:hover, QCheckBox::indicator:unchecked:hover {{
      border:2px solid {PINK};
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QListWidget, QTreeWidget {{
      background:{WHITE}; border:1px solid #e6b5ce; border-radius:6px; padding:5px;
      selection-background-color:{PINK}; selection-color:{TEXT};
    }}
    QTabBar::tab {{ background:{LIGHT}; padding:7px 14px; border:1px solid #e6b5ce; }}
    QTabBar::tab:selected {{ background:{PANEL}; color:{DARK}; }}
    QStatusBar {{ background:{LIGHT}; }}
    QToolTip {{ background:{PANEL}; color:{TEXT}; border:1px solid {DARK}; }}
    """
