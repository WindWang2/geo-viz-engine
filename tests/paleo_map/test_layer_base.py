import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainter

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_layer_is_abstract():
    with pytest.raises(TypeError):
        PaleoLayer()  # type: ignore[abstract]


def test_default_hit_test_returns_none():
    class Dummy(PaleoLayer):
        def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
            return None

    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=100, height=100)
    assert Dummy().hit_test_polygon(QPointF(0, 0), vp) is None
