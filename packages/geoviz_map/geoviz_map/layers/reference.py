"""ReferenceLabelsLayer — city/capital dots and sea italic labels."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.models import ReferenceLabel
from geoviz_map.viewport import MapViewport


CITY_DOT_COLOR = QColor("#94a3b8")
CAPITAL_DOT_COLOR = QColor("#ef4444")
DOT_BORDER = QColor("#ffffff")
LABEL_COLOR = QColor("#475569")
SEA_COLOR = QColor("#0284c7")
LABEL_HALO = QColor("#ffffff")


class ReferenceLabelsLayer(MapLayer):
    def __init__(self, labels: list[ReferenceLabel]):
        self.labels = labels

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        if not self.visible:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        for lbl in self.labels:
            pt = viewport.lnglat_to_screen(lbl.lng, lbl.lat)
            if lbl.kind == "sea":
                self._draw_sea(painter, pt, lbl.name)
            else:
                self._draw_city(painter, pt, lbl.name, lbl.kind == "capital")

    def _draw_city(self, painter: QPainter, pt: QPointF,
                   name: str, is_capital: bool) -> None:
        dot_color = CAPITAL_DOT_COLOR if is_capital else CITY_DOT_COLOR
        # 6 px dot with 1px white border
        painter.setPen(QPen(DOT_BORDER, 1.0))
        painter.setBrush(dot_color)
        painter.drawEllipse(pt, 3.0, 3.0)

        # Label text (11px, with white halo)
        font = QFont("Sans Serif", 8)
        if is_capital:
            font.setBold(True)
        painter.setFont(font)
        text_pt = QPointF(pt.x() + 8.0, pt.y() + 4.0)
        self._draw_text_with_halo(painter, text_pt, name, LABEL_COLOR)

    def _draw_sea(self, painter: QPainter, pt: QPointF, name: str) -> None:
        font = QFont("Sans Serif", 10)
        font.setBold(True)
        font.setItalic(True)
        painter.setFont(font)
        self._draw_text_with_halo(painter, pt, name, SEA_COLOR)

    @staticmethod
    def _draw_text_with_halo(painter: QPainter, pt: QPointF, text: str,
                             color: QColor) -> None:
        # Halo: draw text in white at 4 corner offsets, then draw final color on top
        painter.setPen(QPen(LABEL_HALO, 0))
        for dx, dy in ((-1.5, -1.5), (1.5, -1.5), (-1.5, 1.5), (1.5, 1.5)):
            painter.drawText(QPointF(pt.x() + dx, pt.y() + dy), text)
        painter.setPen(QPen(color, 0))
        painter.drawText(pt, text)
