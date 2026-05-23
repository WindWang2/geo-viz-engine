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
