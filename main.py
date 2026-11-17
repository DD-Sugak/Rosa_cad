"""Точка входа ROSA CAD на PySide6."""
import sys
from PySide6.QtWidgets import QApplication
from config import load_fonts, stylesheet
from app import RosaCAD

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ROSA CAD")
    load_fonts(app)
    app.setStyleSheet(stylesheet())
    window = RosaCAD()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
