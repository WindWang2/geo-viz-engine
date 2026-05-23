import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.depth_track import DepthTrack


def test_depth_track_draws_centered_labels(qtbot):
    track = DepthTrack(top_depth=0, bottom_depth=100, width=60)
    qtbot.addWidget(track)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(60, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 60, 544)
    track.paint_content(painter, rect)
    painter.end()
    img = pixmap.toImage()
    center_has_text = False
    for y in range(int(rect.top()), int(rect.bottom()), 10):
        c = img.pixelColor(30, y)
        if c.lightness() < 200:
            center_has_text = True
            break
    assert center_has_text
