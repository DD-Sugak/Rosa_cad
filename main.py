"""Точка входа ROSA CAD на PySide6."""
import sys
from pathlib import Path
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from config import load_fonts, stylesheet
from app import RosaCAD

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ROSA CAD")
    icon_path = Path(__file__).resolve().parent / "assets" / "rosa_icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    load_fonts(app)
    app.setStyleSheet(stylesheet())
    window = RosaCAD()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
