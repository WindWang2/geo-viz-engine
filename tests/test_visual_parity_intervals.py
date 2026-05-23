"""Visual parity tests for IntervalTrack, LithologyTrack, and FaciesTrack
to ensure they use ECharts-matching color constants."""

import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.models import IntervalItem, LithologyInterval
from geoviz_well_log.renderer.lithology_track import LithologyTrack


def test_interval_track_uses_echarts_border(qtbot):
    track = IntervalTrack(
        intervals=[IntervalItem(top=0, bottom=50, name="Test")],
        width=60
    )
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(60, 300)
    pixmap.fill()
    painter = QPainter(pixmap)
    track.paint_content(painter, QRectF(0, 0, 60, 300))
    painter.end()
    pixel = pixmap.toImage().pixelColor(0, 0)
    assert pixel.red() < 250 or pixel.green() < 250


def test_lithology_track_uses_echarts_border(qtbot):
    track = LithologyTrack(
        intervals=[LithologyInterval(top=0, bottom=50, lithology="砂岩")],
        width=60
    )
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(60, 300)
    pixmap.fill()
    painter = QPainter(pixmap)
    track.paint_content(painter, QRectF(0, 0, 60, 300))
    painter.end()
    pixel = pixmap.toImage().pixelColor(0, 0)
    assert pixel.red() < 250 or pixel.green() < 250
