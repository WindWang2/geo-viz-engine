from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.title import TitleLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_title_paints_text_near_top_center():
    img = QImage(800, 200, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=200)
    layer = TitleLayer("奥陶纪岩相古地理图")
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Sample top-center band for any text pixels
    found = False
    for y in range(0, 30):
        for x in range(300, 500):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found


def test_empty_title_paints_nothing():
    img = QImage(800, 200, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=200)
    layer = TitleLayer("")
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Image is unchanged
    for y in range(0, 30, 2):
        for x in range(0, 800, 10):
            c = img.pixelColor(x, y)
            assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF
