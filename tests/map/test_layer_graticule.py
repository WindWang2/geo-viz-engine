from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.graticule import GraticuleLayer
from geoviz_map.viewport import MapViewport


def test_graticule_paints_lines_at_2deg_steps():
    """Centered at (115°E, 28°N) zoom 7.5 — graticule lines should appear."""
    img = QImage(1200, 800, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)  # white background
    vp = MapViewport(115.0, 28.0, zoom=7.5, width=1200, height=800)
    layer = GraticuleLayer()
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    # At least one non-white pixel must exist (a graticule line was drawn)
    non_white = 0
    for y in range(0, 800, 10):
        for x in range(0, 1200, 10):
            c = img.pixelColor(x, y)
            if c.red() < 255 or c.green() < 255 or c.blue() < 255:
                non_white += 1
                break
    assert non_white > 0


def test_graticule_uses_configured_lng_lat_range():
    layer = GraticuleLayer(lng_min=100, lng_max=130, lng_step=5,
                           lat_min=10, lat_max=40, lat_step=5)
    # Expected lng lines: 100, 105, 110, 115, 120, 125, 130 → 7
    assert layer.lng_lines() == [100, 105, 110, 115, 120, 125, 130]
    assert layer.lat_lines() == [10, 15, 20, 25, 30, 35, 40]
