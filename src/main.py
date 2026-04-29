import sys
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from src.app import MainWindow


def main():
    app = QApplication(sys.argv)

    font = QFont("SimHei", 10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    app.setFont(font)

    app.setStyleSheet("""
        QWidget { background: #1a202c; color: #e2e8f0; }
        QGroupBox { border: 1px solid #4a5568; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QPushButton { background: #2d3748; border: 1px solid #4a5568; border-radius: 4px; padding: 6px 16px; color: #e2e8f0; }
        QPushButton:hover { background: #4a5568; }
        QPushButton:pressed { background: #1a202c; }
        QTableWidget { background: #2d3748; gridline-color: #4a5568; border: 1px solid #4a5568; }
        QHeaderView::section { background: #1a202c; border: 1px solid #4a5568; padding: 4px; }
        QScrollBar:vertical { background: #1a202c; width: 10px; }
        QScrollBar::handle:vertical { background: #4a5568; border-radius: 5px; }
        QScrollArea { border: none; }
    """)
    app.setApplicationName("GeoViz Engine")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
