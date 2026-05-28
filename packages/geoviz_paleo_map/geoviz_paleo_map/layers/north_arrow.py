"""NorthArrowLayer — triangle + N letter in the top-right corner."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


ARROW_COLOR = QColor("#334155")


class NorthArrowLayer(PaleoLayer):
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # 30x40 SVG offset 16px from right, ~50px from top
        x0 = viewport.width - 46
        y0 = 50
        # Triangle: points (15, 0), (10, 18), (20, 18) within 30x40 box
        polygon = QPolygonF([
            QPointF(x0 + 15, y0),
            QPointF(x0 + 10, y0 + 18),
            QPointF(x0 + 20, y0 + 18),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ARROW_COLOR)
        painter.drawPolygon(polygon)
        # "N" at (15, 30)
        painter.setPen(QPen(ARROW_COLOR, 0))
        font = QFont("Sans Serif", 9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance("N")
        painter.drawText(QPointF(x0 + 15 - w / 2, y0 + 32), "N")
