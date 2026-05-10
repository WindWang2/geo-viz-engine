"""Run the seismic demo: ``python -m geoviz_seismic``."""
import sys

from PySide6.QtWidgets import QApplication

from .seismic_view import SeismicView


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("geoviz-seismic demo")
    win = SeismicView()
    win.resize(1200, 800)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
