from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_arrow_paints_in_top_right_corner():
    img = QImage(400, 200, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=400, height=200)
    layer = NorthArrowLayer()
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Top-right corner band — anchor at width-46 .. width-16
    found = False
    for y in range(50, 100):
        for x in range(350, 390):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.green() < 200 or c.blue() < 200:
                found = True; break
        if found: break
    assert found, "expected north arrow in top-right corner band"
