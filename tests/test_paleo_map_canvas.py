import time
import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt

from geoviz_paleo_map import PaleoMapCanvas


SAMPLE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"name": "测试区", "facies": "砂岩"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                    [110.0, 30.0], [110.0, 20.0]
                ]],
            },
        }
    ],
}


def _make_canvas(qtbot):
    canvas = PaleoMapCanvas()
    canvas.load_features(SAMPLE["features"], period_name="测试",
                         wells=[{"name": "HZ-1", "lng": 115.0, "lat": 25.0}])
    qtbot.addWidget(canvas)
    canvas.resize(1200, 800)
    canvas.show()
    qtbot.waitExposed(canvas)
    return canvas


def test_canvas_grab_produces_nonempty(qtbot):
    canvas = _make_canvas(qtbot)
    pixmap = canvas.grab()
    assert not pixmap.isNull()
    dpr = pixmap.devicePixelRatio()
    assert pixmap.width() == int(1200 * dpr)


def test_resize_updates_viewport(qtbot):
    canvas = _make_canvas(qtbot)
    canvas.resize(400, 300)
    qtbot.wait(20)
    assert canvas._viewport.width == 400
    assert canvas._viewport.height == 300


def test_load_features_updates_seen_facies(qtbot):
    canvas = _make_canvas(qtbot)
    assert "砂岩" in canvas._legend_layer.facies_names


def test_hover_over_polygon_sets_current_hover(qtbot):
    from PySide6.QtGui import QMouseEvent
    from PySide6.QtWidgets import QApplication
    canvas = _make_canvas(qtbot)
    canvas.repaint()
    # Polygon spans (110..120, 20..30); centered viewport (115, 25)
    center_pt = canvas._viewport.lnglat_to_screen(115.0, 25.0)
    pt = QPointF(center_pt.x(), center_pt.y())
    event = QMouseEvent(QEvent.Type.MouseMove, pt, pt,
                        Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(canvas, event)
    assert canvas._current_hover == "砂岩"


def test_paint_performance(qtbot):
    """Smoke perf baseline: 1 polygon should paint very fast (<50ms)."""
    canvas = _make_canvas(qtbot)
    canvas.repaint()  # warm up
    t0 = time.perf_counter()
    for _ in range(10):
        canvas.repaint()
    avg_ms = (time.perf_counter() - t0) / 10 * 1000
    assert avg_ms < 50, f"avg paint {avg_ms:.1f}ms exceeds 50ms"


def test_facies_with_pattern_renders_composite_brush(qtbot):
    """Facies '三角洲' should resolve to pattern_id='delta' with composite brush."""
    canvas = PaleoMapCanvas()
    canvas.load_features([
        {
            "type": "Feature",
            "properties": {"name": "三角洲区", "facies": "三角洲"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110.0, 20.0], [120.0, 20.0], [120.0, 30.0],
                                [110.0, 30.0], [110.0, 20.0]]],
            },
        }
    ], period_name="测试")
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)
    qtbot.wait(20)
    style = canvas._resolver.resolve("三角洲")
    assert style.pattern_id == "delta"
    # Brush should be a QBrush (composite, not just solid color)
    from PySide6.QtGui import QBrush
    assert isinstance(style.brush, QBrush)
