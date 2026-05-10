"""Quick-start demo for geoviz-seismic.

Run with:
    python examples/demo.py

Requires a display server (X11/Wayland). The demo generates synthetic
seismic data with dipping reflectors, a normal fault, and Gaussian noise.
"""

import sys
from PySide6.QtWidgets import QApplication
from geoviz_seismic import SeismicView


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("geoviz-seismic demo")
    view = SeismicView()
    view.resize(1200, 800)
    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
