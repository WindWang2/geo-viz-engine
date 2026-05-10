"""Load and display a SEGY file with geoviz-seismic.

Run with:
    python examples/load_segy.py path/to/cube.sgy
"""

import sys
from PySide6.QtWidgets import QApplication
from geoviz_seismic import SeismicView


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <segy_file>")
        sys.exit(1)

    path = sys.argv[1]
    app = QApplication(sys.argv)
    app.setApplicationName("geoviz-seismic")
    view = SeismicView(path=path)
    view.resize(1200, 800)
    view.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
