import pytest
from PySide6.QtCore import Qt, QEvent, QPointF, QPoint
from PySide6.QtGui import QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QApplication, QWidget

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interaction import ZoomPanHandler


def _make_canvas(qtbot):
    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(210, 500)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=1000))
    canvas.set_depth_range(0, 1000)
    return canvas


def _send_event(widget, event):
    """Send event through Qt event system so event filters are triggered."""
    QApplication.sendEvent(widget, event)


def test_handler_install(qtbot):
    canvas = _make_canvas(qtbot)
    handler = ZoomPanHandler(canvas)
    assert handler is not None


def test_wheel_zoom_in(qtbot):
    canvas = _make_canvas(qtbot)
    handler = ZoomPanHandler(canvas)
    handler.set_full_range(0, 1000)
    event = QWheelEvent(
        QPointF(100, 250), QPointF(100, 250), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollBegin, False,
    )
    _send_event(canvas, event)
    dt = canvas.tracks[0]
    assert dt.depth_span < 1000.0


def test_wheel_zoom_out(qtbot):
    canvas = _make_canvas(qtbot)
    handler = ZoomPanHandler(canvas)
    handler.set_full_range(0, 1000)
    canvas.set_depth_range(400, 600)
    event = QWheelEvent(
        QPointF(100, 250), QPointF(100, 250), QPoint(0, -120), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollBegin, False,
    )
    _send_event(canvas, event)
    dt = canvas.tracks[0]
    assert dt.depth_span > 200.0


def test_double_click_reset(qtbot):
    canvas = _make_canvas(qtbot)
    handler = ZoomPanHandler(canvas)
    handler.set_full_range(0, 1000)
    canvas.set_depth_range(400, 600)
    assert canvas.tracks[0].depth_span == pytest.approx(200.0)
    event = QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(100, 250),
                        QPointF(100, 250), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    _send_event(canvas, event)
    assert canvas.tracks[0].depth_span == pytest.approx(1000.0)
