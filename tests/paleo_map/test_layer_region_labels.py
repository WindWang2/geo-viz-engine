from PySide6.QtGui import QColor, QImage, QPainter

from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer, contrast_color
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_contrast_color_dark_text_on_light_bg():
    assert contrast_color(QColor("#ffffff")) == QColor("#2d3748")


def test_contrast_color_light_text_on_dark_bg():
    assert contrast_color(QColor("#1a1a1a")) == QColor("#f7fafc")


def test_paints_label_text_for_each_feature():
    feat = {
        "type": "Feature",
        "properties": {"name": "测试区", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 20.0], [120.0, 20.0], [120.0, 30.0], [110.0, 30.0], [110.0, 20.0]
            ]],
        },
    }
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = RegionLabelsLayer([feat], resolver)
    p = QPainter(img); layer.paint(p, vp); p.end()

    # At least one non-white pixel near center (the text)
    found = False
    for dy in range(-20, 21, 5):
        for dx in range(-30, 31, 5):
            c = img.pixelColor(200 + dx, 200 + dy)
            if c.red() < 250 or c.green() < 250 or c.blue() < 250:
                found = True; break
        if found: break
    assert found, "expected label text near polygon center"


def test_nan_vertex_does_not_abort_paint():
    """#682: a NaN ring must be skipped instead of crashing CollisionDetector."""
    nan_feat = {
        "type": "Feature",
        "properties": {"name": "坏区", "facies": "砂岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [float("nan"), 30.0], [120.0, 20.0], [120.0, 30.0],
                [110.0, 30.0], [float("nan"), 30.0],
            ]],
        },
    }
    good_feat = {
        "type": "Feature",
        "properties": {"name": "好区", "facies": "泥岩"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [110.0, 20.0], [120.0, 20.0], [120.0, 30.0], [110.0, 30.0], [110.0, 20.0]
            ]],
        },
    }
    img = QImage(400, 400, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFFFF)
    vp = PaleoMapViewport(115.0, 25.0, zoom=4.0, width=400, height=400)
    resolver = FaciesStyleResolver(PatternEngine())
    layer = RegionLabelsLayer([nan_feat, good_feat], resolver)
    p = QPainter(img)
    try:
        layer.paint(p, vp)
    finally:
        p.end()
    assert "好区" in layer.visible_labels
    assert "坏区" not in layer.visible_labels


def test_collision_detector_rejects_nan_rect():
    """#682: int(NaN) must not escape CollisionDetector.try_add."""
    from PySide6.QtCore import QRectF
    from geoviz_paleo_map.collision import CollisionDetector

    cd = CollisionDetector()
    assert cd.try_add(QRectF(float("nan"), 0.0, 10.0, 10.0)) is False
    assert cd.try_add(QRectF(0.0, 0.0, 10.0, 10.0)) is True
