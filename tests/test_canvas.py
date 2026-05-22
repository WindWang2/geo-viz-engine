from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData


def _make_gr_curve(n=100):
    return CurveData(name="GR", unit="API",
                     depth=list(range(n)), values=[50.0] * n,
                     display_range=(0, 150), color="#00ff00")


def test_canvas_creation(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    assert len(canvas.tracks) == 0


def test_canvas_add_tracks(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    depth = DepthTrack(top_depth=0, bottom_depth=100)
    curve = CurveTrack(curves=[_make_gr_curve()], label="GR", width=150)
    canvas.add_track(depth)
    canvas.add_track(curve)
    assert len(canvas.tracks) == 2
    assert canvas.total_width == 60 + 150


def test_canvas_set_depth_range(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    depth = DepthTrack(top_depth=0, bottom_depth=100)
    curve = CurveTrack(curves=[_make_gr_curve()], label="GR", width=150)
    canvas.add_track(depth)
    canvas.add_track(curve)
    canvas.set_depth_range(10, 90)
    assert depth.depth_top == 10
    assert curve.depth_top == 10


def test_canvas_paint_all(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100))
    canvas.add_track(CurveTrack(curves=[_make_gr_curve()], label="GR", width=150))
    canvas.set_depth_range(0, 100)
    pm = QPixmap(canvas.total_width, 500)
    painter = QPainter(pm)
    canvas.paint_all(painter)
    painter.end()


def test_canvas_remove_track(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    t1 = DepthTrack(top_depth=0, bottom_depth=100)
    t2 = CurveTrack(curves=[_make_gr_curve()], label="GR", width=150)
    canvas.add_track(t1)
    canvas.add_track(t2)
    canvas.remove_track(t1)
    assert len(canvas.tracks) == 1
    assert canvas.tracks[0] is t2
