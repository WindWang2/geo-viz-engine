import pytest
from PySide6.QtCore import QPointF

from geoviz_map.viewport import MapViewport
from geoviz_map.zoom_pan import ZoomPanHandler


def test_drag_pan_moves_center_opposite_to_drag():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    initial_lng = 118.0
    handler = ZoomPanHandler(vp)
    handler.start_drag(QPointF(600, 400))
    handler.update_drag(QPointF(500, 400))  # drag left 100 px
    # Drag left → map moves left → center longitude increases
    new_lng = handler.viewport.screen_to_lnglat(QPointF(600, 400))[0]
    assert new_lng > initial_lng


def test_wheel_zoom_anchors_at_cursor():
    vp = MapViewport(118.0, 25.0, zoom=7.0, width=1200, height=800)
    handler = ZoomPanHandler(vp)
    cursor = QPointF(900, 300)  # off-center
    before = vp.screen_to_lnglat(cursor)
    handler.wheel_zoom(cursor, delta_steps=1.0)  # zoom in by 1 level
    after = handler.viewport.screen_to_lnglat(cursor)
    assert after[0] == pytest.approx(before[0], abs=1e-6)
    assert after[1] == pytest.approx(before[1], abs=1e-6)
    assert handler.viewport.zoom == pytest.approx(8.0)


def test_zoom_clamps_to_min_max():
    vp = MapViewport(118.0, 25.0, zoom=5.0, width=1200, height=800)
    handler = ZoomPanHandler(vp, min_zoom=4.0, max_zoom=10.0)
    handler.wheel_zoom(QPointF(600, 400), delta_steps=-20.0)
    assert handler.viewport.zoom == 4.0
    handler.wheel_zoom(QPointF(600, 400), delta_steps=20.0)
    assert handler.viewport.zoom == 10.0
