from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.background import BackgroundLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_background_fills_with_default_color():
    img = QImage(100, 80, QImage.Format.Format_RGB32)
    img.fill(0)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=100, height=80)
    layer = BackgroundLayer()
    p = QPainter(img); layer.paint(p, vp); p.end()
    c = img.pixelColor(50, 40)
    assert c.red() == 0xF7 and c.green() == 0xFA and c.blue() == 0xFC
