from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


SAND_FEATURE = {
    "type": "Feature",
    "properties": {"name": "西部滨岸相", "facies": "砂岩"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [110.0, 20.0], [120.0, 20.0], [120.0, 30.0], [110.0, 30.0], [110.0, 20.0]
        ]],
    },
}

FAULTED_FEATURE = {
    "type": "Feature",
    "properties": {"name": "断裂带", "facies": "灰岩", "boundary_type": "fault"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [114.0, 22.0], [116.0, 22.0], [116.0, 24.0], [114.0, 24.0], [114.0, 22.0]
        ]],
    },
}


def _setup():
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)
    return img, vp, resolver


def test_polygon_renders_visible_pixels_in_viewport():
    img, vp, resolver = _setup()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Center pixel must be non-white (polygon covers full viewport)
    c = img.pixelColor(200, 200)
    assert not (c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF)


def test_polygon_outside_viewport_culled():
    img, vp, resolver = _setup()
    far_feature = {
        "type": "Feature",
        "properties": {"name": "远方", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0], [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0]
            ]],
        },
    }
    layer = FaciesPolygonsLayer([far_feature], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # All pixels still white
    for y in range(0, 400, 20):
        for x in range(0, 400, 20):
            c = img.pixelColor(x, y)
            assert c.red() == 0xFF and c.green() == 0xFF and c.blue() == 0xFF


def test_hit_test_returns_facies_name_inside_polygon():
    img, vp, resolver = _setup()
    layer = FaciesPolygonsLayer([SAND_FEATURE], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    # Center of viewport falls inside the polygon (110..120, 20..30)
    hit = layer.hit_test_polygon(QPointF(200, 200), vp)
    assert hit == "砂岩"


def test_hit_test_miss_returns_none():
    img, vp, resolver = _setup()
    far_feature = {
        "type": "Feature",
        "properties": {"name": "远方", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0], [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0]
            ]],
        },
    }
    layer = FaciesPolygonsLayer([far_feature], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()
    assert layer.hit_test_polygon(QPointF(200, 200), vp) is None


def test_skips_non_polygon_geometries():
    img, vp, resolver = _setup()
    point_feature = {
        "type": "Feature",
        "properties": {"name": "p", "facies": "砂岩"},
        "geometry": {"type": "Point", "coordinates": [115.0, 25.0]},
    }
    layer = FaciesPolygonsLayer([point_feature], resolver)
    # Should construct without error and paint as no-op
    p = QPainter(img); layer.paint(p, vp); p.end()
    assert layer.hit_test_polygon(QPointF(200, 200), vp) is None
