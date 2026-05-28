from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


def test_dot_renders_at_well_location():
    wells = [{"name": "HZ-1", "lng": 115.0, "lat": 25.0}]
    img = QImage(400, 400, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    layer = WellsScatterLayer(wells)
    p = QPainter(img); layer.paint(p, vp); p.end()

    # Sample pixels around center for red
    found_red = False
    for dx in range(-4, 5):
        for dy in range(-4, 5):
            c = img.pixelColor(200 + dx, 200 + dy)
            if c.red() > 0xD0 and c.green() < 0x70 and c.blue() < 0x70:
                found_red = True; break
        if found_red: break
    assert found_red, "expected red dot at well location"


def test_missing_lng_lat_well_is_skipped():
    wells = [{"name": "valid", "lng": 115.0, "lat": 25.0},
             {"name": "incomplete"}]
    layer = WellsScatterLayer(wells)
    assert len(layer.wells) == 1
