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

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    data = np.random.randn(10, 15, 20).astype(np.float32)
    view.load_demo(data)
    assert view.is_ready()
    assert view._3d_mode_combo.currentText() == "三维体"
    assert view._renderer_3d._mode == "volume"


def test_seismic_view_set_mode(qtbot):
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    view.set_display_mode("wiggle")
    assert view.display_mode() == "wiggle"
    view.set_display_mode("vd")
    assert view.display_mode() == "vd"


def test_seismic_view_toolbar_single_row(qtbot):
    """Toolbar must render as a compact single row with dropdown menus."""
    from PySide6.QtWidgets import QToolBar
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)

    # Toolbars exist
    assert isinstance(view._toolbar_row1, QToolBar)
    assert isinstance(view._toolbar_row2, QToolBar)

    # Primary single row actions
    row1_actions = [a for a in view._toolbar_row1.actions()]
    row1_widgets = {view._toolbar_row1.widgetForAction(a) for a in row1_actions if view._toolbar_row1.widgetForAction(a) is not None}
    assert view._3d_mode_combo in row1_widgets
    assert view._attr_combo in row1_widgets
    assert view._horizon_menu_btn in row1_widgets
    assert view._render_menu_btn in row1_widgets
    assert view._overlay_menu_btn in row1_widgets

    # Sub-row toolbars are hidden
    assert view._toolbar_row2.isHidden()
    assert view._toolbar_row3.isHidden()


def test_seismic_view_dual_volume_overlay(qtbot):
    """Verify that SeismicView adds UI controls for dual-volume overlays, connects them, and propagates changes."""
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)

    # 1. Assert overlay UI controls exist and are placed on toolbar row 3
    assert hasattr(view, "_overlay_btn")
    assert hasattr(view, "_overlay_cmap_combo")
    assert hasattr(view, "_overlay_opacity_slider")

    row_actions = [a for a in view._toolbar_row2.actions()] + [a for a in view._toolbar_row3.actions()]
    row_widgets = {w for w in (view._toolbar_row2.widgetForAction(a) for a in row_actions) if w is not None} | {w for w in (view._toolbar_row3.widgetForAction(a) for a in row_actions) if w is not None}
    assert view._overlay_btn in row_widgets
    assert view._overlay_cmap_combo in row_widgets
    assert view._overlay_opacity_slider in row_widgets

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


def test_seismic_view_syncs_survey_meta_and_geo_coord_mode(qtbot):
    """#116: SeismicView must push its survey meta into Renderer3D.

    ``Renderer3D._meta`` was never wired, so the toolbar's geo toggle only
    changed 2D readouts while the 3D geo branch (world grid/bbox,
    Easting/Northing labels) stayed dead code.
    """
    from geoviz_seismic.models import BinGridGeometry, SeismicVolumeMeta
    from geoviz_seismic.seismic_view import SeismicView

    view = SeismicView(auto_load=False)
    qtbot.addWidget(view)
    view.load_demo(np.random.randn(6, 7, 8).astype(np.float32))
    # load_demo's meta has no bin grid: renderer got it but stays in grid.
    assert view._renderer_3d._meta is view._meta
    assert view._renderer_3d._meta.bin_grid is None

    # Simulate a calibrated SEGY arriving (same path as _on_segy_ready).
    view._meta = SeismicVolumeMeta(
        filename="t.sgy",
        n_inlines=6,
        n_crosslines=7,
        n_samples=8,
        sample_interval=4.0,
        iline_start=1,
        iline_step=1,
        xline_start=1,
        xline_step=1,
        dt_ms=4.0,
        bin_grid=BinGridGeometry(
            x_origin=500000.0, y_origin=4400000.0,
            il_spacing_m=25.0, xl_spacing_m=50.0,
        ),
    )
    view._sync_renderer_survey_mapping()
    assert view._renderer_3d._meta is view._meta

    # Toggle geo via the toolbar button path.
    view.btn_coord.setChecked(True)
    view._toggle_coord_mode()

    assert view._renderer_3d._coord_mode == "geo"
    texts = [getattr(item, "text", "") for item in view._renderer_3d._axis_labels]
    assert any("Easting" in t for t in texts)
    assert any("Northing" in t for t in texts)

    # Uncalibrated survey: the toggle reverts and the renderer stays grid.
    view._meta = SeismicVolumeMeta(
        filename="demo",
        n_inlines=6,
        n_crosslines=7,
        n_samples=8,
        sample_interval=4.0,
        iline_start=1,
        iline_step=1,
        xline_start=1,
        xline_step=1,
        dt_ms=4.0,
    )
    view._sync_renderer_survey_mapping()
    # set_survey_meta re-applies geo → explicit grid fallback in the renderer.
    assert view._renderer_3d._coord_mode == "grid"
    assert not any("Easting" in t for t in
                   [getattr(i, "text", "") for i in view._renderer_3d._axis_labels])

    view.btn_coord.setChecked(True)
    view._toggle_coord_mode()
    assert view.btn_coord.isChecked() is False  # reverted
    assert view._renderer_3d._coord_mode == "grid"
