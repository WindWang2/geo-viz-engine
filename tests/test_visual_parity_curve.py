import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData


def test_curve_header_shows_legend(qtbot):
    curves = [CurveData(name="GR", depth=list(range(100)), values=[50.0]*100,
                        display_range=(0, 150), color="#15803d")]
    track = CurveTrack(curves=curves, label="GR (API)", width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(150, 100)
    pixmap.fill()
    painter = QPainter(pixmap)
    track.paint_header(painter, QRectF(0, 0, 150, 56))
    painter.end()
    img = pixmap.toImage()
    has_content = False
    for x in range(0, 150, 5):
        for y in range(0, 56, 5):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.green() > 200:
                has_content = True
                break
    assert has_content


def test_curve_track_uses_echarts_border(qtbot):
    curves = [CurveData(name="GR", depth=list(range(100)), values=[50.0]*100, display_range=(0, 150))]
    track = CurveTrack(curves=curves, width=150)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(150, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    track.paint_content(painter, QRectF(0, 56, 150, 544))
    painter.end()
    pixel = pixmap.toImage().pixelColor(0, 56)
    assert pixel.red() < 250 or pixel.green() < 250
