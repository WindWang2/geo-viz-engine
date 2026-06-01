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


def test_seismic_view_init(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)
    # Wait for async synthetic worker to complete
    qtbot.waitUntil(view.is_ready, timeout=5000)
    assert view.is_ready()


def test_seismic_view_load_demo(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)
    data = np.random.randn(10, 15, 20).astype(np.float32)
    view.load_demo(data)
    assert view.is_ready()


def test_seismic_view_set_mode(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)
    view.set_display_mode("wiggle")
    assert view.display_mode() == "wiggle"
    view.set_display_mode("vd")
    assert view.display_mode() == "vd"


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


def test_seismic_view_dual_volume_overlay(qtbot):
    """Verify that SeismicView adds UI controls for dual-volume overlays, connects them, and propagates changes."""
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView()
    qtbot.addWidget(view)

    # 1. Assert overlay UI controls exist and are placed on toolbar row 2
    assert hasattr(view, "_overlay_btn")
    assert hasattr(view, "_overlay_cmap_combo")
    assert hasattr(view, "_overlay_opacity_slider")

    row2_actions = [a for a in view._toolbar_row2.actions()]
    row2_widgets = {view._toolbar_row2.widgetForAction(a) for a in row2_actions}
    assert view._overlay_btn in row2_widgets
    assert view._overlay_cmap_combo in row2_widgets
    assert view._overlay_opacity_slider in row2_widgets

    # Ensure 3D render mode is set to "volume"
    view._3d_mode_combo.setCurrentIndex(1)  # 0: planes, 1: volume
    assert view._renderer_3d._mode == "volume"

    # 2. Load overlay/attribute volume via SeismicView API
    overlay_data = np.random.randn(10, 10, 10).astype(np.float32)
    view.load_overlay_volume(overlay_data, colormap="jet", opacity=0.6)

    # Assert underlying renderer is updated
    assert view._renderer_3d._overlay_volume_visual is not None
    assert view._renderer_3d._overlay_cmap_name == "jet"
    assert view._renderer_3d._overlay_opacity == 0.6

    # Assert UI controls sync their state
    assert view._overlay_btn.isChecked() is True
    assert view._overlay_opacity_slider.value() == 60

    # 3. Test interactive control signals
    # Opacity slider change
    view._overlay_opacity_slider.setValue(80)
    assert view._renderer_3d._overlay_opacity == 0.8

    # Colormap selection change
    view._overlay_cmap_combo.setCurrentText("seismic")
    assert view._renderer_3d._overlay_cmap_name == "seismic"

    # Toggle overlay visibility
    view._overlay_btn.setChecked(False)
    assert view._renderer_3d._overlay_volume_visual.visible() is False

    view._overlay_btn.setChecked(True)
    assert view._renderer_3d._overlay_volume_visual.visible() is True

