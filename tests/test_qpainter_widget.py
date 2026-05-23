import pytest
from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt

from geoviz_well_log import (
    WellLogCanvas, DepthTrack, CurveTrack, CurveData,
)
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
