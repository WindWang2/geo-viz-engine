import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData


def test_depth_track_draws_horizontal_grid_lines(qtbot):
    track = DepthTrack(top_depth=0, bottom_depth=100, width=60)
    qtbot.addWidget(track)
    pixmap = QPixmap(60, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 60, 544)
    track.paint_content(painter, rect)
    painter.end()
    mid_y = int(rect.top() + rect.height() * 0.5)
    pixel = pixmap.toImage().pixelColor(30, mid_y)
    assert pixel.red() < 250 or pixel.green() < 250


def test_curve_track_draws_horizontal_grid_lines(qtbot):
    curves = [CurveData(name="GR", depth=list(range(100)), values=[50.0]*100, display_range=(0, 150))]
    track = CurveTrack(curves=curves, width=150)
    qtbot.addWidget(track)
    pixmap = QPixmap(150, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 150, 544)
    track.paint_content(painter, rect)
    painter.end()
    mid_y = int(rect.top() + rect.height() * 0.5)
    pixel = pixmap.toImage().pixelColor(75, mid_y)
    assert pixel.red() < 250 or pixel.green() < 250
