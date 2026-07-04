import pytest
from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt

from geoviz_well_log import (
    WellLogCanvas, DepthTrack, CurveTrack, CurveData,
)
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.models import IntervalItem
from src.pages.well_log.qpainter_widget import QPainterWidget


def _make_tracks():
    return [
        DepthTrack(top_depth=0, bottom_depth=100),
        CurveTrack(
            curves=[CurveData(name="GR", depth=list(range(100)),
                              values=[50.0] * 100, display_range=(0, 150))],
            label="GR (API)", width=150,
        ),
    ]


def test_widget_creates_scroll_area(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    assert isinstance(widget, QScrollArea)


def test_widget_has_canvas(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    assert isinstance(widget.canvas, WellLogCanvas)


def test_set_tracks(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    tracks = _make_tracks()
    widget.set_tracks(tracks)
    assert len(widget.canvas.tracks) == 2


def test_set_depth_range(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    widget.set_tracks(_make_tracks())
    widget.set_depth_range(10.0, 90.0)
    t = widget.canvas.tracks[0]
    assert t.depth_top == 10.0
    assert t.depth_bottom == 90.0


def test_reset_view(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    widget.set_tracks(_make_tracks())
    widget.set_depth_range(10.0, 90.0)
    widget.reset_view()
    t = widget.canvas.tracks[0]
    assert t.depth_top == 0.0
    assert t.depth_bottom == 100.0


def test_set_tracks_empty(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    widget.set_tracks([])
    assert len(widget.canvas.tracks) == 0
    widget.reset_view()


def test_canvas_preserves_natural_track_width_for_horizontal_scroll(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    widget.resize(360, 600)
    widget.show()
    qtbot.waitExposed(widget)
    tracks = [
        DepthTrack(top_depth=0, bottom_depth=100, width=60),
        *[
            IntervalTrack(
                intervals=[IntervalItem(top=0, bottom=100, name=f"Track {i}")],
                label=f"T{i}",
                width=120,
            )
            for i in range(6)
        ],
    ]

    widget.set_tracks(tracks)

    assert widget.canvas.minimumWidth() == sum(t.width for t in tracks)
    assert widget.canvas.width() >= sum(t.width for t in tracks)
    assert widget.horizontalScrollBar().maximum() > 0
