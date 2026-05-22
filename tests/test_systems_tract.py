import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import IntervalItem
from geoviz_well_log.renderer.systems_tract import SystemsTractTrack


def _make_tracts():
    return [
        IntervalItem(top=0, bottom=100, name="LST"),
        IntervalItem(top=100, bottom=200, name="TST"),
        IntervalItem(top=200, bottom=300, name="HST"),
    ]


def test_systems_tract_creation(qtbot):
    track = SystemsTractTrack(intervals=_make_tracts(), width=60)
    qtbot.addWidget(track)
    assert track.label == "Systems Tract"


def test_systems_tract_paint_no_crash(qtbot):
    track = SystemsTractTrack(intervals=_make_tracts(), width=60)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_systems_tract_export_render(qtbot):
    track = SystemsTractTrack(intervals=_make_tracts(), width=60)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(60, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 60, 832))
    painter.end()


def test_systems_tract_unknown_name(qtbot):
    """Unknown tract name renders as gray rectangle."""
    intervals = [IntervalItem(top=0, bottom=100, name="UNKNOWN")]
    track = SystemsTractTrack(intervals=intervals, width=60)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_systems_tract_chinese_names(qtbot):
    """Chinese tract names should also work."""
    intervals = [
        IntervalItem(top=0, bottom=100, name="海侵体系域"),
        IntervalItem(top=100, bottom=200, name="高位体系域"),
        IntervalItem(top=200, bottom=300, name="低位体系域"),
    ]
    track = SystemsTractTrack(intervals=intervals, width=60)
    qtbot.addWidget(track)
    track.set_depth_range(0, 300)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_systems_tract_empty(qtbot):
    track = SystemsTractTrack(intervals=[], width=60)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()
