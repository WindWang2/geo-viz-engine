from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.wells import WellsLayer
from geoviz_map.models import WellMarker
from geoviz_map.viewport import MapViewport


def _setup(width: int = 800, height: int = 800):
    img = QImage(width, height, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.0, zoom=8.0, width=width, height=height)
    return img, vp


def test_well_dot_renders_at_center_with_specified_color():
    well = WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                      has_data=True)
    layer = WellsLayer([well])
    img, vp = _setup()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    # Center should be near red
    found_red = False
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            c = img.pixelColor(400 + dx, 400 + dy)
            if c.red() > 0xD0 and c.green() < 0x60 and c.blue() < 0x60:
                found_red = True
                break
        if found_red:
            break
    assert found_red


def test_hit_test_returns_well_name_at_dot_position():
    well = WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                      has_data=True)
    layer = WellsLayer([well])
    img, vp = _setup()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    assert layer.hit_test(QPointF(400, 400), vp) == "HZ-1"


def test_hit_test_miss_returns_none():
    well = WellMarker(name="HZ-1", lng=114.5, lat=22.0, color="#ef4444",
                      has_data=True)
    layer = WellsLayer([well])
    img, vp = _setup()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    # 50 px away from any well
    assert layer.hit_test(QPointF(50, 50), vp) is None


def test_set_hovered_increases_hover_dot_size():
    well_a = WellMarker(name="A", lng=114.5, lat=22.0, color="#ef4444",
                        has_data=True)
    well_b = WellMarker(name="B", lng=115.5, lat=22.0, color="#ef4444",
                        has_data=True)
    layer = WellsLayer([well_a, well_b])
    layer.set_hovered("A")
    assert layer.hovered_name == "A"
    layer.set_hovered(None)
    assert layer.hovered_name is None
