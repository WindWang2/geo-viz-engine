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


@requires_pyvista_qt
def test_seismic_view_toolbar_split_into_two_rows(qtbot):
    """11.6-H regression: toolbar must render as two stacked QToolBars.

    Single-row toolbar overflowed 1280px windows; row 2 carries view/attribute
    controls and IL/XL/T sliders so row 1 stays compact for primary actions.
    """
    from PySide6.QtWidgets import QToolBar
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)

    # Both rows must exist and be QToolBars
    assert isinstance(view._toolbar_row1, QToolBar)
    assert isinstance(view._toolbar_row2, QToolBar)

    # Row 1: primary actions including pick & well-tie
    row1_actions = [a for a in view._toolbar_row1.actions()]
    assert any(view._toolbar_row1.widgetForAction(a) is view._pick_btn
               for a in row1_actions)
    assert any(view._toolbar_row1.widgetForAction(a) is view._well_tie_btn
               for a in row1_actions)

    # Row 2: view + attribute controls
    row2_actions = [a for a in view._toolbar_row2.actions()]
    row2_widgets = {view._toolbar_row2.widgetForAction(a) for a in row2_actions}
    assert view._3d_mode_combo in row2_widgets
    assert view._attr_combo in row2_widgets
    assert view._tb_il_slider in row2_widgets
    assert view._tb_xl_slider in row2_widgets
    assert view._tb_t_slider in row2_widgets
    assert view._clip_spin in row2_widgets
