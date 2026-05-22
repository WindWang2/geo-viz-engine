import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import LithologyInterval
from geoviz_well_log.renderer.lithology_track import LithologyTrack


def _make_intervals():
    return [
        LithologyInterval(top=0, bottom=100, lithology="砂岩", description="中砂岩"),
        LithologyInterval(top=100, bottom=200, lithology="泥岩", description="深灰色泥岩"),
        LithologyInterval(top=200, bottom=300, lithology="灰岩", description="生物灰岩"),
    ]


def test_lithology_track_creation(qtbot):
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    qtbot.addWidget(track)
    assert track.label == "Lithology"
    assert track.width == 80


def test_lithology_track_paint_no_crash(qtbot):
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_lithology_track_export_render(qtbot):
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 80, 832))
    painter.end()


def test_lithology_track_unknown_lithology_no_crash(qtbot):
    """Unknown lithology name falls back to color fill — no crash."""
    intervals = [LithologyInterval(top=0, bottom=100, lithology="未知岩石")]
    track = LithologyTrack(intervals=intervals, width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_lithology_track_empty_intervals(qtbot):
    track = LithologyTrack(intervals=[], width=80)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_lithology_track_zoomed_view(qtbot):
    """Only a subset of intervals visible — should not crash."""
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    qtbot.addWidget(track)
    track.set_depth_range(50, 150)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()
