import pytest
from PySide6.QtCore import QPointF

from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_paleo_map.zoom_pan import ZoomPanHandler


def test_drag_pan_increases_center_lng_when_dragging_left():
    vp = PaleoMapViewport(115.0, 30.0, zoom=4.0, width=1200, height=800)
    h = ZoomPanHandler(vp)
    h.start_drag(QPointF(600, 400))
    h.update_drag(QPointF(500, 400))
    new_lng = h.viewport.screen_to_lnglat(QPointF(600, 400))[0]
    assert new_lng > 115.0


def test_wheel_zoom_keeps_cursor_anchor_invariant():
    vp = PaleoMapViewport(115.0, 30.0, zoom=2.0, width=1200, height=800)
    h = ZoomPanHandler(vp)
    cursor = QPointF(900, 300)
    before = vp.screen_to_lnglat(cursor)
    h.wheel_zoom(cursor, delta_steps=1.0)
    after = h.viewport.screen_to_lnglat(cursor)
    assert after[0] == pytest.approx(before[0], abs=1e-6)
    assert after[1] == pytest.approx(before[1], abs=1e-6)
    assert h.viewport.zoom == pytest.approx(3.0)


def test_zoom_clamped_to_range():
    vp = PaleoMapViewport(0.0, 0.0, zoom=2.0, width=1200, height=800)
    h = ZoomPanHandler(vp, min_zoom=1.0, max_zoom=5.0)
    h.wheel_zoom(QPointF(600, 400), delta_steps=-20.0)
    assert h.viewport.zoom == 1.0
    h.wheel_zoom(QPointF(600, 400), delta_steps=20.0)
    assert h.viewport.zoom == 5.0
