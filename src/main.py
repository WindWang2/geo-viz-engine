import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from src.app import MainWindow


def main():
    app = QApplication(sys.argv)

    font = QFont("Noto Sans CJK SC", 10)
    font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging | QFont.StyleStrategy.PreferMatch)
    font.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    app.setFont(font)

    app.setStyleSheet("""
        QWidget { background: #ffffff; color: #1a202c; }
        QGroupBox { border: 1px solid #cbd5e0; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QPushButton { background: #edf2f7; border: 1px solid #cbd5e0; border-radius: 4px; padding: 6px 16px; color: #1a202c; }
        QPushButton:hover { background: #e2e8f0; }
        QPushButton:pressed { background: #cbd5e0; }
        QTableWidget { background: #ffffff; gridline-color: #e2e8f0; border: 1px solid #e2e8f0; }
        QHeaderView::section { background: #f7fafc; border: 1px solid #e2e8f0; padding: 4px; }
        QScrollBar:vertical { background: #f7fafc; width: 10px; }
        QScrollBar::handle:vertical { background: #cbd5e0; border-radius: 5px; }
        QScrollArea { border: none; }
    """)
    app.setApplicationName("GeoViz Engine")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
