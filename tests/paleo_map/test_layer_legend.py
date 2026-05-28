from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.legend import LegendLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_legend_renders_in_bottom_right_corner():
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=600)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = LegendLayer({"砂岩", "灰岩"}, resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Bottom-right corner must have non-white pixels (legend box)
    found = False
    for y in range(400, 590):
        for x in range(600, 790):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found, "expected legend artifacts in bottom-right corner"


def test_legend_empty_facies_still_renders_fixed_section():
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(0.0, 0.0, zoom=1.0, width=800, height=600)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = LegendLayer(set(), resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Even with no facies, the boundary/well section should render
    found = False
    for y in range(400, 590):
        for x in range(600, 790):
            c = img.pixelColor(x, y)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found


def test_set_facies_updates_seen():
    resolver = FaciesStyleResolver(PatternEngine())
    layer = LegendLayer(set(), resolver)
    layer.set_facies({"砂岩"})
    assert layer.facies_names == {"砂岩"}
