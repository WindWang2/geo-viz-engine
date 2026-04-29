import os

# Ensure off-screen rendering before any VTK/PyVista imports
# so headless/CI environments don't segfault on OpenGL init
os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")

import numpy as np
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide6.QtWidgets import QWidget, QVBoxLayout


def _check_pyvista_qt_available() -> bool:
    """Test whether pyvistaqt.QtInteractor can be created in this process.

    Runs a subprocess probe because QtInteractor init can trigger a C-level
    segfault (SIGSEGV) when OpenGL is unavailable — a Python try/except won't
    catch it.  The subprocess either exits 0 (OK) or is killed by a signal
    (unavailable).
    """
    import subprocess
    import sys

    code = (
        "import os; os.environ.setdefault('PYVISTA_OFF_SCREEN','true'); "
        "from PySide6.QtWidgets import QApplication; "
        "app=QApplication([]); "
        "from pyvistaqt import QtInteractor; "
        "from PySide6.QtWidgets import QWidget, QVBoxLayout; "
        "w=QWidget(); l=QVBoxLayout(w); "
        "p=QtInteractor(w); l.addWidget(p.interactor); "
        "print('OK')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            timeout=15,
        )
        return result.returncode == 0 and b"OK" in result.stdout
    except Exception:
        return False


class SeismicRenderer(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plotter = QtInteractor(self)
        layout.addWidget(self.plotter.interactor)

    def load_volume(self, data: np.ndarray, origin=(0, 0, 0), spacing=(1, 1, 1)):
        grid = pv.ImageData(dimensions=data.shape, spacing=spacing, origin=origin)
        grid["amplitude"] = data.flatten(order="F")
        self.plotter.add_volume(grid, cmap="seismic", opacity="sigmoid")
        self.plotter.reset_camera()

    def add_slice(self, data: np.ndarray, axis: str = "inline", index: int = 0, spacing=(1, 1, 1)):
        grid = pv.ImageData(dimensions=data.shape, spacing=spacing)
        grid["amplitude"] = data.flatten(order="F")
        if axis == "inline":
            slice_ = grid.slice_orthogonal(x=index * spacing[0])
        elif axis == "crossline":
            slice_ = grid.slice_orthogonal(y=index * spacing[1])
        else:
            slice_ = grid.slice_orthogonal(z=index * spacing[2])
        self.plotter.add_mesh(slice_, cmap="seismic", opacity=0.8)
        self.plotter.reset_camera()

    def clear(self):
        self.plotter.clear()
