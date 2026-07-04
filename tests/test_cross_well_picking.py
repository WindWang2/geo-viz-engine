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
