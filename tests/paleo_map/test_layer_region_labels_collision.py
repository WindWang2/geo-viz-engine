import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter
from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_well_log.renderer.pattern_engine import PatternEngine

def test_region_labels_layer_collision():
    feat1 = {
        "properties": {"name": "Delta1", "facies": "D", "id": "1"},
        "geometry": {"type": "Polygon", "coordinates": [[[10.0, 10.0], [10.0, 11.0], [11.0, 11.0], [10.0, 10.0]]]}
    }
    feat2 = {
        "properties": {"name": "Delta2", "facies": "D", "id": "2"},
        "geometry": {"type": "Polygon", "coordinates": [[[10.00001, 10.00001], [10.00001, 11.00001], [11.00001, 11.00001], [10.00001, 10.00001]]]}
    }
    
    resolver = FaciesStyleResolver(PatternEngine())
    layer = RegionLabelsLayer([feat1, feat2], resolver)
    
    vp = PaleoMapViewport(center_lng=10.5, center_lat=10.5, zoom=20.0, width=800, height=600)
    
    img = QImage(800, 600, QImage.Format_ARGB32)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    
    assert hasattr(layer, "visible_labels")
    assert len(layer.visible_labels) == 1
    assert "Delta1" in layer.visible_labels
