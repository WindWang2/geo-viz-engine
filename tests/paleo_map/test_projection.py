import pytest

from geoviz_paleo_map.projection import lnglat_to_world, world_to_lnglat


def test_origin_maps_to_origin():
    assert lnglat_to_world(0.0, 0.0) == (0.0, 0.0)


def test_unit_degrees_pass_through():
    assert lnglat_to_world(1.0, 2.0) == (1.0, 2.0)


def test_negative_coordinates_pass_through():
    assert lnglat_to_world(-117.5, -33.86) == (-117.5, -33.86)


def test_round_trip():
    lng, lat = 114.4158, 23.1109
    x, y = lnglat_to_world(lng, lat)
    lng2, lat2 = world_to_lnglat(x, y)
    assert lng2 == pytest.approx(lng)
    assert lat2 == pytest.approx(lat)
