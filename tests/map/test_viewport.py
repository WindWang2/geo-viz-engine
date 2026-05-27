import math

import pytest

from geoviz_map.viewport import MapViewport


def test_center_maps_to_screen_center():
    vp = MapViewport(center_lng=118.0, center_lat=25.0, zoom=7.5,
                     width=1200, height=800)
    pt = vp.lnglat_to_screen(118.0, 25.0)
    assert pt.x() == pytest.approx(600.0)
    assert pt.y() == pytest.approx(400.0)


def test_zoom_plus_one_doubles_pixel_distance():
    vp_a = MapViewport(118.0, 25.0, zoom=6.0, width=1200, height=800)
    vp_b = MapViewport(118.0, 25.0, zoom=7.0, width=1200, height=800)
    pa = vp_a.lnglat_to_screen(119.0, 25.0)
    pb = vp_b.lnglat_to_screen(119.0, 25.0)
    dx_a = pa.x() - 600.0
    dx_b = pb.x() - 600.0
    assert dx_b == pytest.approx(dx_a * 2.0, rel=1e-9)


def test_screen_to_lnglat_inverts_lnglat_to_screen():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    src_lng, src_lat = 115.0, 22.0
    pt = vp.lnglat_to_screen(src_lng, src_lat)
    lng2, lat2 = vp.screen_to_lnglat(pt)
    assert lng2 == pytest.approx(src_lng, abs=1e-6)
    assert lat2 == pytest.approx(src_lat, abs=1e-6)


def test_pan_world_shifts_center():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    initial_center_x = vp.center_world[0]
    vp.pan_world(dx=1000.0, dy=0.0)
    assert vp.center_world[0] == pytest.approx(initial_center_x + 1000.0)


def test_world_bbox_is_within_lng_range():
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    bbox = vp.world_bbox()
    assert bbox[0] < bbox[2]
    assert bbox[1] < bbox[3]
    cx, cy = vp.center_world
    assert bbox[0] <= cx <= bbox[2]
    assert bbox[1] <= cy <= bbox[3]
