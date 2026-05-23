import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.models import IntervalItem


def test_canvas_renders_group_headers(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.setFixedSize(300, 600)

    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100, width=60))
    canvas.add_track(IntervalTrack(
        intervals=[IntervalItem(top=0, bottom=50, name="C")],
        label="系", width=50, group_name="地层系统"
    ))
    canvas.add_track(IntervalTrack(
        intervals=[IntervalItem(top=0, bottom=50, name="C1")],
        label="统", width=50, group_name="地层系统"
    ))

    pm = QPixmap(canvas.total_width, 600)
    pm.fill()
    painter = QPainter(pm)
    canvas.paint_all(painter)
    painter.end()

    img = pm.toImage()
    has_header = False
    for x in range(60, 160):
        for y in range(0, 32):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.blue() > 200:
                has_header = True
                break
    assert has_header
