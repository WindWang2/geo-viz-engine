import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF, Qt

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.overlay import CrosshairOverlay


def _make_canvas(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(210, 500)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=1000))
    canvas.set_depth_range(0, 1000)
    return canvas


def test_overlay_creation(qtbot):
    canvas = _make_canvas(qtbot)
    overlay = CrosshairOverlay(canvas)
    assert overlay is not None


def test_overlay_depth_at_y(qtbot):
    canvas = _make_canvas(qtbot)
    overlay = CrosshairOverlay(canvas)
    # Canvas height=500, header_h=56, content area=444px
    # y=250 => content_y=194 => depth=194/444 * 1000 ≈ 436.9
    depth = overlay.depth_at_y(250)
    header_h = 56
    content_h = 500 - header_h
    expected = (250 - header_h) / content_h * 1000
    assert depth == pytest.approx(expected, abs=1.0)


def test_overlay_depth_at_y_clamped(qtbot):
    canvas = _make_canvas(qtbot)
    overlay = CrosshairOverlay(canvas)
    # Below canvas => clamped to bottom
    depth = overlay.depth_at_y(600)
    assert depth == pytest.approx(1000.0)


def test_overlay_paint_no_crash(qtbot):
    canvas = _make_canvas(qtbot)
    overlay = CrosshairOverlay(canvas)
    overlay.set_cursor_y(250)
    pm = QPixmap(210, 500)
    painter = QPainter(pm)
    overlay.paint_overlay(painter, QRectF(0, 0, 210, 500))
    painter.end()


def test_overlay_paint_hidden(qtbot):
    """When cursor_y is None, paint does nothing."""
    canvas = _make_canvas(qtbot)
    overlay = CrosshairOverlay(canvas)
    pm = QPixmap(210, 500)
    painter = QPainter(pm)
    overlay.paint_overlay(painter, QRectF(0, 0, 210, 500))
    painter.end()


def test_overlay_interpolation(qtbot):
    """Curve values should be linearly interpolated between depth points."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    from geoviz_well_log.models import CurveData

    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(210, 500)

    # Create a curve with known values
    curve = CurveData(
        name="GR",
        depth=[0.0, 100.0],
        values=[10.0, 20.0],
    )
    track = CurveTrack(curves=[curve])
    track.set_depth_range(0, 100)
    canvas.add_track(track)
    canvas.set_depth_range(0, 100)

    overlay = CrosshairOverlay(canvas)
    # depth=50 should interpolate to 15.0 (midpoint)
    rows = overlay._collect_values(50.0)
    gr_rows = [(n, v) for n, v in rows if n == "GR"]
    assert len(gr_rows) == 1
    assert float(gr_rows[0][1]) == pytest.approx(15.0, abs=0.1)
