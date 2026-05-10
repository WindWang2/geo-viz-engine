import os
import subprocess
import sys

import numpy as np
import pytest

os.environ.setdefault("PYVISTA_OFF_SCREEN", "true")


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
def test_seismic_view_init(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)
    assert view.is_ready()
    # Auto-demo loads synthetic data on empty init
    assert view.is_loaded()


@requires_pyvista_qt
def test_seismic_view_load_demo(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)
    data = np.random.randn(10, 15, 20).astype(np.float32)
    view.load_demo(data)
    assert view.is_loaded()


@requires_pyvista_qt
def test_seismic_view_set_mode(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)
    view.set_display_mode("wiggle")
    assert view.display_mode() == "wiggle"
    view.set_display_mode("vd")
    assert view.display_mode() == "vd"
