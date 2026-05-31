"""LegendLayer — bottom-right facies swatches + boundary samples + well dot."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_paleo_map.viewport import PaleoMapViewport


BG_COLOR = QColor(255, 255, 255, 242)  # rgba(255,255,255,0.95)
BORDER_COLOR = QColor("#cbd5e1")
TITLE_COLOR = QColor("#334155")
TEXT_COLOR = QColor("#4a5568")
WELL_COLOR = QColor("#e53e3e")
SWATCH_W = 18
SWATCH_H = 12
ROW_H = 16
PADDING = 10


class LegendLayer(PaleoLayer):
    is_chrome = True

    def __init__(self, facies_names: set[str],
                 style_resolver: FaciesStyleResolver):
        self.facies_names = set(facies_names)
        self._resolver = style_resolver

    def set_facies(self, facies_names: set[str]) -> None:
        self.facies_names = set(facies_names)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        # 1. Compute box height: title row + per-facies rows + separator + 4 fixed rows
        facies_count = len(self.facies_names)
        fixed_rows = 4  # confirmed, inferred, fault, well
        box_w = 140
        box_h = PADDING * 2 + ROW_H * (1 + facies_count) + 6 + ROW_H * fixed_rows
        
        x0 = viewport.width - box_w - 12
        y0 = viewport.height - box_h - 12

        # 2. Background
        painter.setPen(QPen(BORDER_COLOR, 1))
        painter.setBrush(BG_COLOR)
        painter.drawRoundedRect(QRectF(x0, y0, box_w, box_h), 6, 6)

        # 3. Title "图例"
        painter.setPen(QPen(TITLE_COLOR, 0))
        title_font = QFont("Sans Serif", 9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QPointF(x0 + PADDING, y0 + PADDING + 12), "图例")
        painter.setFont(font)

        y = y0 + PADDING + ROW_H + 12

        # 4. Facies swatches
        painter.setPen(QPen(TEXT_COLOR, 0))
        for name in sorted(self.facies_names):
            style = self._resolver.resolve(name)
            sw_x = x0 + PADDING
            sw_y = y - SWATCH_H + 2
            painter.setPen(QPen(QColor("#aaa"), 1))
            painter.setBrush(style.brush)
            painter.drawRect(QRectF(sw_x, sw_y, SWATCH_W, SWATCH_H))
            painter.setPen(QPen(TEXT_COLOR, 0))
            painter.drawText(QPointF(sw_x + SWATCH_W + 6, y), name)
            y += ROW_H

        # 5. Separator
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.drawLine(QPointF(x0 + PADDING, y - 4),
                         QPointF(x0 + box_w - PADDING, y - 4))
        y += 4

        # 6. Boundary samples
        for label, kind in (("实测界线", "confirmed"),
                            ("推测界线", "inferred"),
                            ("断层", "fault")):
            pen = boundary_pen(kind)
            pen.setWidthF(2.0)
            painter.setPen(pen)
            painter.drawLine(QPointF(x0 + PADDING, y - 4),
                             QPointF(x0 + PADDING + SWATCH_W, y - 4))
            painter.setPen(QPen(TEXT_COLOR, 0))
            painter.drawText(QPointF(x0 + PADDING + SWATCH_W + 6, y), label)
            y += ROW_H

        # 7. Well dot
        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.setBrush(WELL_COLOR)
        cx = x0 + PADDING + SWATCH_W / 2
        painter.drawEllipse(QPointF(cx, y - 4), 4, 4)
        painter.setPen(QPen(TEXT_COLOR, 0))
        painter.drawText(QPointF(x0 + PADDING + SWATCH_W + 6, y), "井位")
