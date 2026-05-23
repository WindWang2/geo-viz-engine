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
    depth = overlay.depth_at_y(250)
    assert depth == pytest.approx(500.0)


def test_overlay_depth_at_y_clamped(qtbot):
    canvas = _make_canvas(qtbot)
    overlay = CrosshairOverlay(canvas)
    depth = overlay.depth_at_y(-10)
    assert depth == pytest.approx(0.0)
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
