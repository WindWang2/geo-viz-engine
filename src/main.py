import sys
from PySide6.QtWidgets import QApplication
from src.app import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("GeoViz Engine")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
