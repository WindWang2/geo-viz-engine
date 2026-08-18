# tests/test_cross_well_picking.py
"""Unit and integration tests for cross-well multi-curve overlay and interactive picking snapping."""
from __future__ import annotations

import pytest
import numpy as np
from PySide6.QtCore import Qt, QPoint, QRectF
from PySide6.QtWidgets import QApplication, QScrollArea

from geoviz_well_log.models import WellLogData, CurveData, LineStyle
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_cross_well import CrossWellCanvas
from src.pages.cross_well.page import CrossWellPage

@pytest.fixture
def app():
    instance = QApplication.instance()
    if instance is None:
        instance = QApplication([])
    return instance

def _make_mock_well_data() -> WellLogData:
    # depths 0 to 100
    depths = np.linspace(0, 100, 101).tolist()
    
    # values: base 50.0, peak 150.0 at depth 50.0m, trough 10.0 at depth 60.0m
    gr_values = [50.0] * 101
    gr_values[50] = 150.0
    gr_values[60] = 10.0
    
    # AC values
    ac_values = [80.0] * 101
    
    gr_curve = CurveData(name="GR", unit="API", depth=depths, values=gr_values, display_range=(0, 150), color="green")
    ac_curve = CurveData(name="AC", unit="us/ft", depth=depths, values=ac_values, display_range=(40, 140), color="blue")
    
    return WellLogData(
        well_name="MockWell-1",
        top_depth=0.0,
        bottom_depth=100.0,
        curves=[gr_curve, ac_curve]
    )

def test_snapping_calculation(app, qtbot):
    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    
    well_data = _make_mock_well_data()
    # Add well to canvas
    well_canvas = WellLogCanvas()
    well_canvas.set_tracks([
        CurveTrack(curves=well_data.curves, label="GR/AC", width=150)
    ])
    canvas.widget.add_canvas(well_canvas, "MockWell-1")
    
    # 1. Snap mode "none"
    canvas.snap_type = "none"
    assert canvas._get_snapped_depth(well_canvas, 49.5) == pytest.approx(49.5)
    
    # 2. Snap mode "max"
    canvas.snap_type = "max"
    canvas.active_curve = "GR"
    canvas.snap_window_m = 1.5
    # Click near depth 49.5m -> should snap to peak at 50.0m
    assert canvas._get_snapped_depth(well_canvas, 49.5) == pytest.approx(50.0)
    
    # 3. Snap mode "min"
    canvas.snap_type = "min"
    # Click near depth 59.8m -> should snap to trough at 60.0m
    assert canvas._get_snapped_depth(well_canvas, 59.8) == pytest.approx(60.0)

def test_sidebar_toggle(app, qtbot):
    page = CrossWellPage()
    qtbot.addWidget(page)
    
    # Initial state: expanded
    assert page._sidebar_collapsed is False
    assert page._sidebar.maximumWidth() == 280
    assert page._toggle_sidebar_btn.text() == "▶"
    
    # Toggle sidebar -> collapsed
    page._toggle_sidebar()
    assert page._sidebar_collapsed is True
    assert page._toggle_sidebar_btn.text() == "◀"
    
    # Toggle sidebar again -> expanded
    page._toggle_sidebar()
    assert page._sidebar_collapsed is False
    assert page._toggle_sidebar_btn.text() == "▶"

def test_custom_curve_groupings_rebuild(app, qtbot):
    page = CrossWellPage()
    qtbot.addWidget(page)
    
    well_data = _make_mock_well_data()
    # Cache well data
    page._well_data_cache["MockWell-1"] = well_data
    page._selected_labels = ["GR", "AC", "深度"]
    
    # Add a canvas
    canvas = WellLogCanvas()
    page._cross_well.add_canvas(canvas, "MockWell-1")
    
    # Set grouping: GR merged into AC
    page._canvas.curve_groups = {
        "AC/GR": ["AC", "GR"]
    }
    
    page._rebuild_canvases()
    
    # Verify that the tracks in the canvas contain the merged CurveTrack
    tracks = canvas.tracks
    # Look for CurveTrack with label "AC/GR"
    merged_track = next((t for t in tracks if t.label == "AC/GR"), None)
    assert merged_track is not None
    assert isinstance(merged_track, CurveTrack)
    assert len(merged_track._curves) == 2
    assert {c.name for c in merged_track._curves} == {"GR", "AC"}


def _well_canvas_with_track(depths, name="GR") -> WellLogCanvas:
    """A WellLogCanvas with one simple CurveTrack over ``depths``."""
    curves = [
        CurveData(name=name, unit="API", depth=list(depths),
                  values=[50.0] * len(depths), display_range=(0, 100),
                  color="green"),
    ]
    well_canvas = WellLogCanvas()
    well_canvas.set_tracks([CurveTrack(curves=curves, label=name, width=150)])
    return well_canvas


def test_paint_twt_axis_uses_leftmost_displayed_well(qtbot):
    """#853-4: _paint_twt_axis took the tie table's first well (CSV order),
    not the leftmost displayed well — with a CSV whose well order differs
    from the display order the axis was labeled with the wrong well's
    calibration."""
    import os
    import tempfile

    from PySide6.QtGui import QImage, QPainter

    from geoviz_cross_well import CrossWellCanvas
    from geoviz_cross_well.seismic_tie import SeismicTie

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.waitExposed(canvas)

    # Display order: W2 leftmost, then W1.
    depths = np.linspace(0, 100, 101)
    canvas.widget.add_canvas(_well_canvas_with_track(depths), "W2")
    canvas.widget.add_canvas(_well_canvas_with_track(depths), "W1")

    # CSV lists W1 first — the opposite of the display order.
    csv_text = (
        "depth_m,twt_ms,well\n"
        "0,10,W1\n50,20,W1\n100,30,W1\n"
        "0,11,W2\n50,21,W2\n100,31,W2\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        path = f.name
    try:
        tie = SeismicTie()
        tie.load_csv(path)
    finally:
        os.unlink(path)
    assert tie.well_names() == ["W1", "W2"], (
        "precondition: CSV-first well is W1"
    )

    queried = []
    orig_table_for_well = tie.table_for_well
    tie.table_for_well = lambda w: (queried.append(w), orig_table_for_well(w))[1]
    canvas._overlay._seismic_tie = tie
    canvas._overlay._depth_domain = "TWT"

    img = QImage(800, 600, QImage.Format.Format_RGB32)
    p = QPainter(img)
    try:
        canvas._overlay._paint_twt_axis(p)
    finally:
        p.end()

    assert queried, "the axis must query a well's calibration table"
    assert queried[0] == "W2", (
        "must use the LEFTMOST displayed well, not the CSV-first well"
    )


def test_paint_twt_axis_survives_missing_calibration(monkeypatch, qtbot):
    """#853-4: the old code called ``calibration.depth_to_twt`` directly,
    bypassing interpolate_twt's None-guard — with the well-tie extra absent
    (WellTieCalibration import fails) the axis crashed. Painting must
    degrade to plain interpolation instead."""
    import os
    import tempfile

    import geoviz_cross_well.seismic_tie as st_mod
    from PySide6.QtGui import QImage, QPainter

    from geoviz_cross_well import CrossWellCanvas
    from geoviz_cross_well.seismic_tie import SeismicTie

    monkeypatch.setattr(st_mod, "WellTieCalibration", None)

    canvas = CrossWellCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.show()
    qtbot.waitExposed(canvas)
    depths = np.linspace(0, 100, 101)
    canvas.widget.add_canvas(_well_canvas_with_track(depths), "W1")

    csv_text = "depth_m,twt_ms,well\n0,10,W1\n50,20,W1\n100,30,W1\n"
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv_text)
        path = f.name
    try:
        tie = SeismicTie()
        tie.load_csv(path)
    finally:
        os.unlink(path)
    assert tie.table_for_well("W1").calibration is None, (
        "precondition: calibration unavailable"
    )

    canvas._overlay._seismic_tie = tie
    canvas._overlay._depth_domain = "TWT"

    img = QImage(800, 600, QImage.Format.Format_RGB32)
    p = QPainter(img)
    try:
        canvas._overlay._paint_twt_axis(p)  # must not raise
    finally:
        p.end()
