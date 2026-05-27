import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


def test_layer_is_abstract_paint_required():
    with pytest.raises(TypeError):
        MapLayer()  # type: ignore[abstract]


def test_default_hit_test_returns_none():
    class Dummy(MapLayer):
        def paint(self, painter: QPainter, viewport: MapViewport) -> None:
            return None

    vp = MapViewport(118.0, 25.0, zoom=7.5, width=1200, height=800)
    assert Dummy().hit_test(QPointF(0, 0), vp) is None
