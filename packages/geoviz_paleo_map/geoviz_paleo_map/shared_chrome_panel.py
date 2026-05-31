"""SharedChromePanel — single chrome strip shared between two PaleoMapCanvas.

Compare mode renders two canvases side-by-side. Each canvas hides its own
chrome (Title/NorthArrow/ScaleBar/Legend) via `show_chrome=False`; this
widget sits between them and paints one merged legend (A+B facies),
plus a north arrow and a scale bar referencing the left canvas's viewport.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from geoviz_paleo_map.canvas import PaleoMapCanvas
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen


BG_COLOR = QColor(255, 255, 255, 242)
BORDER_COLOR = QColor("#cbd5e1")
TITLE_COLOR = QColor("#334155")
TEXT_COLOR = QColor("#4a5568")
ARROW_COLOR = QColor("#334155")
BAR_COLOR = QColor("#334155")
WELL_COLOR = QColor("#e53e3e")
SWATCH_W = 18
SWATCH_H = 12
ROW_H = 16
PADDING = 12
PANEL_WIDTH = 200


class SharedChromePanel(QWidget):
    """Vertical strip: north arrow at top, merged legend, scale bar at bottom."""

    def __init__(self, canvas_a: PaleoMapCanvas, canvas_b: PaleoMapCanvas,
                 parent: QWidget | None = None, *, overlay: bool = False):
        super().__init__(parent)
        self._canvas_a = canvas_a
        self._canvas_b = canvas_b
        self._overlay = overlay
        # Share resolver from canvas_a (both canvases share the same engine in practice).
        self._resolver: FaciesStyleResolver = canvas_a._resolver
        self.setFixedWidth(PANEL_WIDTH)
        if overlay:
            self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        else:
            self.setStyleSheet("background: #f8fafc;")

        # Refresh on any facies / zoom change on either canvas.
        canvas_a.facies_changed.connect(self.update)
        canvas_b.facies_changed.connect(self.update)
        canvas_a.zoom_changed.connect(lambda _: self.update())
        canvas_b.zoom_changed.connect(lambda _: self.update())

    def merged_facies(self) -> set[str]:
        return self._canvas_a.facies_names() | self._canvas_b.facies_names()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

            self._paint_north_arrow(painter)
            legend_bottom = self._paint_legend(painter)
            self._paint_scale_bar(painter, legend_bottom)
        finally:
            painter.end()

    # --- North arrow at top ---

    def _paint_north_arrow(self, painter: QPainter) -> None:
        cx = self.width() / 2
        y0 = 20
        polygon = QPolygonF([
            QPointF(cx, y0),
            QPointF(cx - 8, y0 + 22),
            QPointF(cx + 8, y0 + 22),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(ARROW_COLOR)
        painter.drawPolygon(polygon)
        painter.setPen(QPen(ARROW_COLOR, 0))
        font = QFont("Sans Serif", 10)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance("N")
        painter.drawText(QPointF(cx - w / 2, y0 + 38), "N")

    # --- Merged legend in the middle ---

    def _paint_legend(self, painter: QPainter) -> float:
        facies = sorted(self.merged_facies())
        fixed_rows = 4  # confirmed, inferred, fault, well
        box_w = self.width() - 16
        box_h = PADDING * 2 + ROW_H * (1 + len(facies)) + 6 + ROW_H * fixed_rows
        x0 = 8.0
        y0 = 60.0

        painter.setPen(QPen(BORDER_COLOR, 1))
        painter.setBrush(BG_COLOR)
        painter.drawRoundedRect(QRectF(x0, y0, box_w, box_h), 6, 6)

        title_font = QFont("Sans Serif", 9)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(QPen(TITLE_COLOR, 0))
        painter.drawText(QPointF(x0 + PADDING, y0 + PADDING + 12), "图例")

        body_font = QFont("Sans Serif", 8)
        painter.setFont(body_font)

        y = y0 + PADDING + ROW_H + 4
        for name in facies:
            style = self._resolver.resolve(name)
            sw_x = x0 + PADDING
            sw_y = y - SWATCH_H + 2
            painter.setPen(QPen(QColor("#aaa"), 1))
            painter.setBrush(style.brush)
            painter.drawRect(QRectF(sw_x, sw_y, SWATCH_W, SWATCH_H))
            painter.setPen(QPen(TEXT_COLOR, 0))
            painter.drawText(QPointF(sw_x + SWATCH_W + 6, y), name)
            y += ROW_H

        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.drawLine(QPointF(x0 + PADDING, y - 4),
                         QPointF(x0 + box_w - PADDING, y - 4))
        y += 4

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

        painter.setPen(QPen(QColor("#ffffff"), 1.5))
        painter.setBrush(WELL_COLOR)
        cx = x0 + PADDING + SWATCH_W / 2
        painter.drawEllipse(QPointF(cx, y - 4), 4, 4)
        painter.setPen(QPen(TEXT_COLOR, 0))
        painter.drawText(QPointF(x0 + PADDING + SWATCH_W + 6, y), "井位")

        return y0 + box_h

    # --- Scale bar at bottom (uses canvas_a's viewport for the reading) ---

    def _paint_scale_bar(self, painter: QPainter, top_y: float) -> None:
        vp = self._canvas_a._viewport
        bbox = vp.world_bbox()
        mid_lat = (bbox[1] + bbox[3]) / 2
        deg_to_km = 111.32 * math.cos(math.radians(mid_lat))
        extent_km = (bbox[2] - bbox[0]) * deg_to_km
        scale_km = extent_km * 0.3 if extent_km > 0 else 1.0

        if scale_km >= 1:
            label = f"{scale_km:.1f} km"
        else:
            label = f"{scale_km * 1000:.0f} m"

        bar_min, bar_max = 40.0, 160.0
        bar_px = bar_max - (extent_km - 100) / (2000 - 100) * (bar_max - bar_min)
        bar_px = max(bar_min, min(bar_max, bar_px))
        bar_px = min(bar_px, self.width() - 32)

        x0 = (self.width() - bar_px) / 2
        y0 = max(top_y + 32, self.height() - 32)
        pen = QPen(BAR_COLOR, 2.0)
        painter.setPen(pen)
        painter.drawLine(QPointF(x0, y0), QPointF(x0 + bar_px, y0))
        painter.drawLine(QPointF(x0, y0 - 4), QPointF(x0, y0 + 4))
        painter.drawLine(QPointF(x0 + bar_px, y0 - 4), QPointF(x0 + bar_px, y0 + 4))

        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        painter.setPen(QPen(BAR_COLOR, 0))
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(label)
        painter.drawText(QPointF(x0 + bar_px / 2 - w / 2, y0 + 14), label)
