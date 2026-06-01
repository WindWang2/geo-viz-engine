"""BackgroundLayer — solid color fill (e.g. ocean blue)."""
from PySide6.QtGui import QColor, QPainter

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


class BackgroundLayer(MapLayer):
    def __init__(self, color: str = "#faf9f5"):
        self.color = QColor(color)

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        painter.fillRect(0, 0, viewport.width, viewport.height, self.color)
