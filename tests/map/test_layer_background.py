from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.background import BackgroundLayer
from geoviz_map.viewport import MapViewport


def test_background_fills_with_specified_color():
    img = QImage(100, 80, QImage.Format.Format_RGB32)
    img.fill(0)
    vp = MapViewport(118.0, 25.0, zoom=7.5, width=100, height=80)
    layer = BackgroundLayer(color="#cbebfb")
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    center = img.pixelColor(50, 40)
    assert center.red() == 0xCB
    assert center.green() == 0xEB
    assert center.blue() == 0xFB
