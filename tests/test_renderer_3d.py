import os
import subprocess
import sys

import numpy as np
import pytest

os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget


def _pyvista_qt_available() -> bool:
    """Check if pyvistaqt.QtInteractor can be created.

    QtInteractor init can trigger a C-level X error when the display
    is unavailable, which Python try/except cannot catch.  Use a
    subprocess probe to avoid crashing the test process.
    """
    code = (
        "import os; os.environ.setdefault('PYVISTA_OFF_SCREEN','true'); "
        "from PySide6.QtWidgets import QApplication; "
        "app=QApplication([]); "
        "from pyvistaqt import QtInteractor; "
        "w=QtInteractor(); "
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


requires_pyvista_qt = pytest.mark.skipif(
    not _pyvista_qt_available(),
    reason="pyvistaqt.QtInteractor not available in this environment",
)


@requires_pyvista_qt
def test_renderer_3d_init(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    assert widget._plotter is not None


@requires_pyvista_qt
def test_renderer_3d_load_volume(qtbot):
    from geoviz_seismic.renderer_3d import Renderer3D

    widget = Renderer3D()
    qtbot.addWidget(widget)
    data = np.random.randn(10, 10, 10).astype(np.float32)
    widget.load_volume(data)
    assert widget._loaded


def test_renderer_3d_signals():
    """Verify Renderer3D class exposes the expected signal."""
    from geoviz_seismic.renderer_3d import Renderer3D

    assert hasattr(Renderer3D, "slice_changed")
    assert isinstance(Renderer3D.slice_changed, Signal)
