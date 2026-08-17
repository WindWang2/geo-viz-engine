import pytest
from PySide6.QtWidgets import QApplication

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.renderer.canvas import WellLogCanvas


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_cross_well_widget_creation(app):
    widget = CrossWellWidget()
    assert widget.canvas_count == 0
    assert widget._canvases == []


def test_cross_well_widget_add_well(app):
    widget = CrossWellWidget()
    canvas = WellLogCanvas()
    widget.add_canvas(canvas, "well1")
    assert widget.canvas_count == 1
    assert widget._canvases[0] is canvas


def test_cross_well_widget_remove_well(app):
    widget = CrossWellWidget()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.remove_canvas(c1)
    assert widget.canvas_count == 1


def test_cross_well_widget_clear_all(app):
    widget = CrossWellWidget()
    widget.add_canvas(WellLogCanvas(), "well1")
    widget.add_canvas(WellLogCanvas(), "well2")
    widget.clear_all()
    assert widget.canvas_count == 0


def test_cross_well_widget_event_coalescing(app, qtbot):
    widget = CrossWellWidget()
    c1 = WellLogCanvas()
    widget.add_canvas(c1, "well1")

    emissions = 0
    def on_changed():
        nonlocal emissions
        emissions += 1

    widget.canvas_depth_changed.connect(on_changed)

    # Rapidly emit depth_range_changed 100 times to simulate fast mouse scroll/pan
    for i in range(100):
        c1.depth_range_changed.emit(0, 100 + i)

    # Give the 16ms timer time to fire
    qtbot.wait(50)

    # Assert that it fired exactly once (coalesced)
    assert emissions == 1


# --- Task 4: auto-link and manual link ---

from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.models import IntervalItem
from src.data.models import CorrelationLink


def _make_well_canvas(well_name: str, intervals: list[IntervalItem]) -> WellLogCanvas:
    canvas = WellLogCanvas()
    canvas.resize(200, 600)
    tracks = [DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度")]
    if intervals:
        tracks.append(IntervalTrack(intervals=intervals, label="组", width=50))
    canvas.set_tracks(tracks)
    return canvas


def test_auto_link_matches_common_intervals(app):
    widget = CrossWellWidget()
    iv1 = [IntervalItem(top=10, bottom=50, name="FormationA")]
    iv2 = [IntervalItem(top=15, bottom=55, name="FormationA")]
    c1 = _make_well_canvas("well1", iv1)
    c2 = _make_well_canvas("well2", iv2)
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    assert len(widget._overlay._links) == 1
    link = widget._overlay._links[0]
    assert link.source_well == "well1"
    assert link.target_well == "well2"


def test_auto_link_no_match(app):
    widget = CrossWellWidget()
    iv1 = [IntervalItem(top=10, bottom=50, name="FormationA")]
    iv2 = [IntervalItem(top=15, bottom=55, name="FormationB")]
    c1 = _make_well_canvas("well1", iv1)
    c2 = _make_well_canvas("well2", iv2)
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    assert len(widget._overlay._links) == 0


def test_manual_link(app):
    widget = CrossWellWidget()
    iv1 = [IntervalItem(top=10, bottom=50, name="FormationA")]
    iv2 = [IntervalItem(top=15, bottom=55, name="FormationA")]
    c1 = _make_well_canvas("well1", iv1)
    c2 = _make_well_canvas("well2", iv2)
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.toggle_manual_link()
    assert widget._manual_link_active is True
    # Simulate picking two intervals
    widget._manual_link_picks = [
        ("well1", IntervalItem(top=10, bottom=50, name="FormationA")),
        ("well2", IntervalItem(top=15, bottom=55, name="FormationA")),
    ]
    widget._finish_manual_link()
    assert len(widget._overlay._links) == 1
    assert widget._overlay._links[0].is_manual is True


# --- Task 5: Depth ruler and crosshair ---


def test_depth_ruler_updates_on_add(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [IntervalItem(top=0, bottom=100, name="A")])
    widget.add_canvas(c1, "well1")
    assert widget._depth_ruler._depth_top == 0
    assert widget._depth_ruler._depth_bottom == 100


def test_crosshair_syncs_across_canvases(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [])
    c2 = _make_well_canvas("well2", [])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    # Each canvas should have its own crosshair overlay
    assert c1.crosshair is not None
    assert c2.crosshair is not None


# --- Task 6: Composite vector export ---

import tempfile
import os


def test_export_composite_svg_no_crash(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [IntervalItem(top=0, bottom=100, name="A")])
    c2 = _make_well_canvas("well2", [IntervalItem(top=0, bottom=100, name="A")])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = f.name
    try:
        widget.export_composite(path, fmt="svg")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_export_composite_pdf_no_crash(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [IntervalItem(top=0, bottom=100, name="A")])
    c2 = _make_well_canvas("well2", [IntervalItem(top=0, bottom=100, name="A")])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = f.name
    try:
        widget.export_composite(path, fmt="pdf")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_export_composite_png_no_crash(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [IntervalItem(top=0, bottom=100, name="A")])
    c2 = _make_well_canvas("well2", [IntervalItem(top=0, bottom=100, name="A")])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        widget.export_composite(path, fmt="png")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)


def test_export_composite_empty_no_crash(app):
    """Export with no canvases should not crash."""
    widget = CrossWellWidget()
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = f.name
    try:
        widget.export_composite(path, fmt="svg")
        # File may or may not exist — no crash is the key assertion
    finally:
        if os.path.exists(path):
            os.unlink(path)


# --- Task 7: Well reordering ---


def test_well_reorder_changes_order(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [])
    c2 = _make_well_canvas("well2", [])
    c3 = _make_well_canvas("well3", [])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.add_canvas(c3, "well3")
    widget.move_well(0, 2)  # Move well1 to position 2
    assert widget._well_names == ["well2", "well3", "well1"]


# --- Task 8: Per-well track control ---


def test_per_well_track_toggle(app):
    widget = CrossWellWidget()
    iv = [IntervalItem(top=0, bottom=100, name="A")]
    c1 = _make_well_canvas("well1", iv)
    initial_track_count = len(c1.tracks)
    widget.add_canvas(c1, "well1")
    # Hide the interval track (index 1 = IntervalTrack)
    widget.set_track_visible(c1, 1, False)
    assert len(c1.tracks) == initial_track_count
    assert c1.tracks[1].visible is False
    widget.set_track_visible(c1, 1, True)
    assert c1.tracks[1].visible is True
