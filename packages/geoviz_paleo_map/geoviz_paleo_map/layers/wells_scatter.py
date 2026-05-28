"""WellsScatterLayer — red 8px dots + name labels at well positions."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


DOT_COLOR = QColor("#e53e3e")
DOT_BORDER = QColor("#ffffff")
LABEL_COLOR = QColor("#e53e3e")
DOT_RADIUS = 4.0  # 8px diameter


class WellsScatterLayer(PaleoLayer):
    def __init__(self, wells: list[dict]):
        """`wells` is a list of {"name": str, "lng": float, "lat": float}.

        Wells missing lng or lat are silently skipped.
        """
        self.wells = [
            w for w in wells
            if isinstance(w.get("lng"), (int, float))
            and isinstance(w.get("lat"), (int, float))
        ]

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        for w in self.wells:
            pt = viewport.lnglat_to_screen(w["lng"], w["lat"])
            painter.setPen(QPen(DOT_BORDER, 2.0))
            painter.setBrush(DOT_COLOR)
            painter.drawEllipse(pt, DOT_RADIUS, DOT_RADIUS)
            painter.setPen(QPen(LABEL_COLOR, 0))
            painter.drawText(QPointF(pt.x() + DOT_RADIUS + 4.0,
                                     pt.y() + 3.0), w.get("name", ""))
