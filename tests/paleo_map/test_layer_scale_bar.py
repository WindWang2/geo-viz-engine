import pytest

from geoviz_paleo_map.layers.scale_bar import (
    ScaleBarLayer, _smooth_scale_km,
)


@pytest.mark.parametrize("extent_km, expected", [
    (10.0, 3.0),    # 0.3 * 10
    (100.0, 30.0),  # 0.3 * 100
    (1000.0, 300.0), # 0.3 * 1000
    (3.0, 0.9),     # 0.3 * 3
    (5000.0, 1500.0), # 0.3 * 5000
])
def test_smooth_scale_km(extent_km, expected):
    assert _smooth_scale_km(extent_km) == pytest.approx(expected)


def test_layer_constructs():
    layer = ScaleBarLayer()
    assert layer is not None
