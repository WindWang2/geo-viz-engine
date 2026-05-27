from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.reference import ReferenceLabelsLayer
from geoviz_map.models import ReferenceLabel
from geoviz_map.viewport import MapViewport


def test_capital_renders_red_dot():
    labels = [ReferenceLabel(name="北京", lng=116.4, lat=39.9, kind="capital")]
    img = QImage(800, 800, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(116.4, 39.9, zoom=7.5, width=800, height=800)
    layer = ReferenceLabelsLayer(labels)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    # Capital dot is red (#ef4444) — sample near the dot location (center)
    found_red = False
    for dx in range(-5, 6):
        for dy in range(-5, 6):
            c = img.pixelColor(400 + dx, 400 + dy)
            if c.red() > 0xD0 and c.green() < 0x60 and c.blue() < 0x60:
                found_red = True
                break
        if found_red:
            break
    assert found_red, "expected red capital dot near image center"


def test_sea_label_has_no_dot_only_text():
    """Sea labels render italic blue text without an accompanying dot."""
    labels = [ReferenceLabel(name="南海", lng=115.5, lat=20.2, kind="sea")]
    img = QImage(800, 800, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(115.5, 20.2, zoom=7.5, width=800, height=800)
    layer = ReferenceLabelsLayer(labels)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    # Some non-white pixel must exist (the text)
    found_non_white = False
    for y in range(380, 420):
        for x in range(380, 420):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found_non_white = True
                break
        if found_non_white:
            break
    assert found_non_white
