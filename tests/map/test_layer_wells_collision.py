import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QImage, QPainter
from geoviz_map.layers.wells import WellsLayer
from geoviz_map.models import WellMarker
from geoviz_map.viewport import MapViewport

def test_wells_layer_collision():
    # Two wells very close to each other
    wells = [
        WellMarker(name="W1", lng=10.0, lat=10.0, color="#f00", has_data=True),
        WellMarker(name="W2", lng=10.00001, lat=10.00001, color="#f00", has_data=True)
    ]
    layer = WellsLayer(wells)
    
    vp = MapViewport(center_lng=10.0, center_lat=10.0, zoom=20.0, width=800, height=600)
    
    img = QImage(800, 600, QImage.Format_ARGB32)
    painter = QPainter(img)
    layer.paint(painter, vp)
    painter.end()
    
    assert hasattr(layer, "visible_labels")
    assert len(layer.visible_labels) == 1
    assert "W1" in layer.visible_labels
