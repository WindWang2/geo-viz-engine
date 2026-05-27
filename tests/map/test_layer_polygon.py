from PySide6.QtGui import QImage, QPainter

from geoviz_map.layers.geojson_polygon import GeoJsonPolygonLayer
from geoviz_map.viewport import MapViewport


SQUARE_AROUND_HUIZHOU = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {"ISO_A3": "CHN"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [114.0, 22.0], [115.0, 22.0],
                [115.0, 23.5], [114.0, 23.5], [114.0, 22.0],
            ]],
        },
    }],
}

POLYGON_FAR_AWAY = {
    "type": "FeatureCollection",
    "features": [{
        "type": "Feature",
        "properties": {},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-180.0, -10.0], [-170.0, -10.0],
                [-170.0, 0.0], [-180.0, 0.0], [-180.0, -10.0],
            ]],
        },
    }],
}


def test_polygon_in_viewport_fills_center_pixels():
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.75, zoom=8.0, width=400, height=400)
    layer = GeoJsonPolygonLayer(SQUARE_AROUND_HUIZHOU,
                                fill_color="#f3f1ec",
                                border_color="#cbd5e1",
                                border_width=0.8)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    center = img.pixelColor(200, 200)
    assert center.red() == 0xF3
    assert center.green() == 0xF1
    assert center.blue() == 0xEC


def test_polygon_outside_viewport_is_culled():
    """Polygon far away should not produce any visible pixels."""
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.75, zoom=8.0, width=400, height=400)
    layer = GeoJsonPolygonLayer(POLYGON_FAR_AWAY, fill_color="#ff0000",
                                border_color="#000000", border_width=1.0)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()

    # No red pixels anywhere
    for y in range(0, 400, 20):
        for x in range(0, 400, 20):
            c = img.pixelColor(x, y)
            assert not (c.red() > 200 and c.green() < 50 and c.blue() < 50)


def test_feature_filter_excludes_iso_a3():
    """`feature_filter` callable can exclude features by properties."""
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = MapViewport(114.5, 22.75, zoom=8.0, width=400, height=400)
    layer = GeoJsonPolygonLayer(
        SQUARE_AROUND_HUIZHOU,
        fill_color="#f3f1ec", border_color="#cbd5e1", border_width=0.8,
        feature_filter=lambda props: props.get("ISO_A3") != "CHN",
    )
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    center = img.pixelColor(200, 200)
    # Should be unchanged white
    assert center.red() == 0xFF
    assert center.green() == 0xFF
    assert center.blue() == 0xFF
