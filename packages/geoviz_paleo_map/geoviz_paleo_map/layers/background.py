"""BackgroundLayer — solid color fill."""
from PySide6.QtGui import QColor, QPainter

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


class BackgroundLayer(PaleoLayer):
    def __init__(self, color: str = "#f7fafc"):
        self.color = QColor(color)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.fillRect(0, 0, viewport.width, viewport.height, self.color)
