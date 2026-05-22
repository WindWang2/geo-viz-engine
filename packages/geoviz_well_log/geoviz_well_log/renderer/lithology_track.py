from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush

from ..models import LithologyInterval
from ..pattern_map import FACIES_COLORS
from .pattern_engine import PatternEngine
from .track_base import BaseTrack

_shared_pattern_engine = PatternEngine()


class LithologyTrack(BaseTrack):
    """Lithology column with SVG pattern fills."""

    def __init__(self, intervals: list[LithologyInterval], label: str = "Lithology",
                 width: int = 80, show_description: bool = True,
                 pattern_engine: PatternEngine | None = None,
                 header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._intervals = intervals
        self._show_description = show_description
        self._pattern_engine = pattern_engine or _shared_pattern_engine

    def _fallback_color(self, lithology: str) -> QColor:
        hex_color = FACIES_COLORS.get(lithology, "#e0e0e0")
        return QColor(hex_color)

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect)

        desc_font = QFont()
        desc_font.setPointSize(6)

        for interval in self._intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)

            # Try SVG pattern fill first, fallback to color
            brush = self._pattern_engine.get_brush(interval.lithology)
            if brush is not None:
                painter.fillRect(interval_rect, brush)
            else:
                painter.fillRect(interval_rect, QBrush(self._fallback_color(interval.lithology)))

            # Border
            painter.setPen(QPen(QColor("#666666"), 0.5))
            painter.drawRect(interval_rect)

            # Description text (vertical, along right edge)
            if self._show_description and interval.description and interval_rect.height() > 16:
                painter.setFont(desc_font)
                painter.setPen(QPen(QColor("#555555"), 1))
                painter.save()
                tx = interval_rect.right() - 4
                ty = interval_rect.center().y()
                painter.translate(tx, ty)
                painter.rotate(-90)
                text_w = interval_rect.height() - 4
                text_h = 10
                painter.drawText(QRectF(-text_w / 2, -text_h / 2, text_w, text_h),
                                 Qt.AlignmentFlag.AlignCenter, interval.description)
                painter.restore()

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
