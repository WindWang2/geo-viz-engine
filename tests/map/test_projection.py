import math

import pytest

from geoviz_map.projection import (
    MAX_LAT,
    R_EARTH,
    lnglat_to_world,
    world_to_lnglat,
)


def test_zero_lng_lat_maps_to_origin():
    x, y = lnglat_to_world(0.0, 0.0)
    assert x == pytest.approx(0.0, abs=1e-6)
    assert y == pytest.approx(0.0, abs=1e-6)


def test_round_trip_known_point_huizhou():
    # Huizhou ~114.4°E, 23.1°N
    lng, lat = 114.4158, 23.1109
    x, y = lnglat_to_world(lng, lat)
    lng2, lat2 = world_to_lnglat(x, y)
    assert lng2 == pytest.approx(lng, abs=1e-9)
    assert lat2 == pytest.approx(lat, abs=1e-9)


def test_one_degree_lng_equals_R_times_radian():
    x, _ = lnglat_to_world(1.0, 0.0)
    assert x == pytest.approx(math.radians(1.0) * R_EARTH, rel=1e-12)


def test_polar_latitude_raises():
    with pytest.raises(ValueError):
        lnglat_to_world(0.0, MAX_LAT + 0.01)
    with pytest.raises(ValueError):
        lnglat_to_world(0.0, -MAX_LAT - 0.01)
