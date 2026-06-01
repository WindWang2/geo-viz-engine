"""TitleLayer — top-center map title with semi-transparent white pad."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


TITLE_COLOR = QColor("#1a202c")
TITLE_BG = QColor(255, 255, 255, 217)  # rgba(255,255,255,0.85)


class TitleLayer(PaleoLayer):
    is_chrome = True

    def __init__(self, text: str):
        self.text = text

    def set_text(self, text: str) -> None:
        self.text = text

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if not self.text:
            return
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 12)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(self.text)
        h = metrics.height()
        
        cx = viewport.width / 2
        rect = QRectF(cx - w / 2 - 12, 4, w + 24, h + 8)
            
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(TITLE_BG)
        painter.drawRoundedRect(rect, 4, 4)
        painter.setPen(QPen(TITLE_COLOR, 0))
        painter.drawText(QPointF(cx - w / 2, rect.y() + metrics.ascent() + 4),
                         self.text)
