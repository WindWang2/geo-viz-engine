import pytest

from geoviz_paleo_map.viewport import PaleoMapViewport


def test_center_maps_to_screen_center():
    vp = PaleoMapViewport(center_lng=115.0, center_lat=30.0, zoom=1.0,
                          width=1200, height=800)
    pt = vp.lnglat_to_screen(115.0, 30.0)
    assert pt.x() == pytest.approx(600.0)
    assert pt.y() == pytest.approx(400.0)


def test_one_degree_east_at_zoom_1_is_one_pixel():
    """At zoom=1.0 the scale is exactly 1 pixel per degree (baseline)."""
    vp = PaleoMapViewport(center_lng=0.0, center_lat=0.0, zoom=1.0,
                          width=1200, height=800)
    pt = vp.lnglat_to_screen(1.0, 0.0)
    # 1 degree east of center → 1 pixel right of width/2
    assert pt.x() == pytest.approx(600.0 + 1.0)


def test_zoom_plus_one_doubles_pixel_distance():
    vp_a = PaleoMapViewport(115.0, 30.0, zoom=1.0, width=1200, height=800)
    vp_b = PaleoMapViewport(115.0, 30.0, zoom=2.0, width=1200, height=800)
    pa = vp_a.lnglat_to_screen(116.0, 30.0)
    pb = vp_b.lnglat_to_screen(116.0, 30.0)
    dx_a = pa.x() - 600.0
    dx_b = pb.x() - 600.0
    assert dx_b == pytest.approx(dx_a * 2.0)


def test_screen_to_lnglat_inverts():
    vp = PaleoMapViewport(115.0, 30.0, zoom=4.0, width=1200, height=800)
    from PySide6.QtCore import QPointF
    pt = vp.lnglat_to_screen(112.0, 28.0)
    lng2, lat2 = vp.screen_to_lnglat(pt)
    assert lng2 == pytest.approx(112.0)
    assert lat2 == pytest.approx(28.0)


def test_resize_updates_dimensions():
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=100, height=100)
    vp.resize(200, 150)
    assert vp.width == 200
    assert vp.height == 150


def test_world_bbox_contains_center():
    vp = PaleoMapViewport(115.0, 30.0, zoom=2.0, width=1200, height=800)
    bbox = vp.world_bbox()
    cx, cy = vp.center_world
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]
    assert bbox[0] <= cx <= bbox[2]
    assert bbox[1] <= cy <= bbox[3]
