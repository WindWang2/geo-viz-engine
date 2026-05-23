from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .renderer.canvas import WellLogCanvas


class ConnectionOverlay(QWidget):
    """Transparent overlay drawing correlation polygons between WellLogCanvas widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._canvases: list[WellLogCanvas] = []
        self._links: list = []

    def set_canvases(self, canvases: list[WellLogCanvas]):
        self._canvases = list(canvases)
        self.update()

    def set_links(self, links: list):
        self._links = list(links)
        self.update()

    def add_link(self, link):
        """Append a single link and repaint."""
        self._links.append(link)
        self.update()

    @property
    def links(self) -> list:
        return list(self._links)

    # --- Backward-compatible stubs for ECharts-based CrossWellPage ---
    # These are no-ops; the new QPainter pipeline computes positions directly.

    def update_depth_cache(self, engine, depth, y_pixel):
        """No-op stub — legacy ECharts depth cache is unused by QPainter canvases."""
        pass

    @property
    def _depth_cache(self):
        return {}

    def depth_to_y(self, canvas: WellLogCanvas, depth: float) -> float:
        """Convert a depth value to Y pixel position within the canvas."""
        if not canvas.tracks:
            return 0.0
        header_h = max((t.header_height for t in canvas.tracks), default=56)
        content_h = canvas.height() - header_h
        if content_h <= 0:
            return 0.0
        track = canvas.tracks[0]
        span = track.depth_span
        if span <= 0:
            return header_h
        ratio = (depth - track.depth_top) / span
        return header_h + ratio * content_h

    def _canvas_left(self, canvas: WellLogCanvas) -> float:
        return canvas.mapTo(self, canvas.rect().topLeft()).x()

    def _canvas_right(self, canvas: WellLogCanvas) -> float:
        return canvas.mapTo(self, canvas.rect().topRight()).x()

    def paintEvent(self, event):
        self.paint_event(QPainter(self), QRectF(self.rect()))

    def paint_event(self, painter: QPainter, rect: QRectF):
        if not self._links or not self._canvases:
            return
        name_map = {}
        for c in self._canvases:
            if c.tracks:
                name_map[c.tracks[0].label] = c

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for link in self._links:
            source = name_map.get(link.source_well)
            target = name_map.get(link.target_well)
            if source is None or target is None:
                continue

            src_right = self._canvas_right(source)
            tgt_left = self._canvas_left(target)

            try:
                src_parts = link.source_interval_id.split("_")
                src_top = float(src_parts[0])
                src_bot = float(src_parts[1])
                tgt_parts = link.target_interval_id.split("_")
                tgt_top = float(tgt_parts[0])
                tgt_bot = float(tgt_parts[1])
            except (ValueError, IndexError):
                continue

            sy1 = self.depth_to_y(source, src_top)
            sy2 = self.depth_to_y(source, src_bot)
            ty1 = self.depth_to_y(target, tgt_top)
            ty2 = self.depth_to_y(target, tgt_bot)

            polygon = QPolygonF([
                (src_right, sy1),
                (tgt_left, ty1),
                (tgt_left, ty2),
                (src_right, sy2),
            ])

            color = QColor(link.color)
            color.setAlpha(120)
            painter.setPen(QPen(color.darker(120), 1))
            painter.setBrush(color)
            painter.drawPolygon(polygon)
