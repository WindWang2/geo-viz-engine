from unittest.mock import patch

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPainter, QPixmap

from geoviz_well_log.models import CurveData, IntervalItem, LithologyInterval
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.renderer.lithology_track import LithologyTrack


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


def test_hover_tooltip_shows_curve_value(qtbot):
    """#724: CurveTrack has no public ``curves`` attr; tooltip must still read GR."""
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(210, 500)
    curve = CurveData(
        name="GR",
        unit="API",
        depth=[0.0, 100.0],
        values=[10.0, 20.0],
        display_range=(0, 150),
        color="#00ff00",
    )
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100))
    canvas.add_track(CurveTrack(curves=[curve], label="GR", width=150))
    canvas.set_depth_range(0, 100)

    with patch("geoviz_well_log.renderer.canvas.QToolTip") as tooltip:
        canvas._update_hover_tooltip(QPointF(130.0, 278.0))
    text = tooltip.showText.call_args[0][1]
    assert "GR:" in text
    assert "15.00" in text


def test_hover_tooltip_uses_sorted_depths_for_descending_las(qtbot):
    """#724: interpolate against CurveTrack's sorted arrays, not raw LAS order."""
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(210, 500)
    curve = CurveData(
        name="GR",
        unit="API",
        depth=[100.0, 0.0],
        values=[20.0, 10.0],
        display_range=(0, 150),
        color="#00ff00",
    )
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100))
    canvas.add_track(CurveTrack(curves=[curve], label="GR", width=150))
    canvas.set_depth_range(0, 100)

    with patch("geoviz_well_log.renderer.canvas.QToolTip") as tooltip:
        canvas._update_hover_tooltip(QPointF(130.0, 278.0))
    text = tooltip.showText.call_args[0][1]
    assert "GR:" in text
    assert "15.00" in text


def test_hover_tooltip_shows_interval_and_lithology_names(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(220, 500)
    canvas.add_track(
        IntervalTrack(
            intervals=[IntervalItem(top=40.0, bottom=60.0, name="沙一段")],
            label="分层",
            width=80,
        )
    )
    canvas.add_track(
        LithologyTrack(
            intervals=[LithologyInterval(top=40.0, bottom=60.0, lithology="砂岩")],
            label="岩性",
            width=80,
        )
    )
    canvas.set_depth_range(0, 100)

    with patch("geoviz_well_log.renderer.canvas.QToolTip") as tooltip:
        canvas._update_hover_tooltip(QPointF(40.0, 278.0))
    interval_text = tooltip.showText.call_args[0][1]
    assert "沙一段" in interval_text

    with patch("geoviz_well_log.renderer.canvas.QToolTip") as tooltip:
        canvas._update_hover_tooltip(QPointF(120.0, 278.0))
    lith_text = tooltip.showText.call_args[0][1]
    assert "砂岩" in lith_text
