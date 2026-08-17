from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush

from ..models import LithologyInterval
from ..pattern_map import FACIES_COLORS
from .label_layout import compute_label_policy, fit_label_text
from .pattern_engine import PatternEngine
from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT

_shared_pattern_engine = PatternEngine()

# Sort keys by length descending for fuzzy matching
_SORTED_COLOR_KEYS = sorted(FACIES_COLORS.keys(), key=len, reverse=True)


class LithologyTrack(BaseTrack):
    """Lithology column with SVG pattern fills."""

    def __init__(self, intervals: list[LithologyInterval], label: str = "Lithology",
                 width: int = 80, show_description: bool = True,
                 pattern_engine: PatternEngine | None = None,
                 header_height: int = 56, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._intervals = intervals

        self._show_description = show_description
        self._pattern_engine = pattern_engine or _shared_pattern_engine

    @property
    def intervals(self):
        """Interval payload (#582): the section canvas discovers stratigraphy
        tracks via a public ``intervals`` attribute; the private-only
        ``_intervals`` made its horizon-link/facies-fill layer dead code."""
        return self._intervals

    def _fallback_color(self, lithology: str) -> QColor:
        hex_color = FACIES_COLORS.get(lithology)
        if hex_color is None:
            for key in _SORTED_COLOR_KEYS:
                if key in lithology:
                    hex_color = FACIES_COLORS[key]
                    break
        return QColor(hex_color or "#e0e0e0")

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect.adjusted(-2, -2, 2, 2))

        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        desc_font = QFont()
        interval_rects: list[tuple[LithologyInterval, QRectF]] = []
        for interval in self._intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)
            if y_bottom < rect.top() or y_top > rect.bottom():
                continue
            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())
            interval_rects.append((interval, QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)))

        policy = compute_label_policy(rect, self.depth_span, [r.height() for _, r in interval_rects])
        desc_font.setPixelSize(policy.font_px)
        painter.setFont(desc_font)
        metrics = painter.fontMetrics()

        for interval, interval_rect in interval_rects:

            # Try SVG pattern fill first, fallback to color
            brush = self._pattern_engine.get_brush(interval.lithology)
            if brush is not None:
                painter.fillRect(interval_rect, brush)
            else:
                painter.fillRect(interval_rect, QBrush(self._fallback_color(interval.lithology)))

            # Border
            painter.setPen(QPen(QColor(ECHARTS_BORDER), 0.5))
            painter.drawRect(interval_rect)

            painter.setPen(QPen(QColor(ECHARTS_TEXT), 1))
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            lines = fit_label_text(interval.lithology, text_rect, policy, metrics)
            if lines:
                if policy.vertical:
                    painter.save()
                    painter.translate(text_rect.center())
                    painter.rotate(-90)
                    rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                     text_rect.height(), text_rect.width())
                    painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, lines[0])
                    painter.restore()
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, "\n".join(lines))

        painter.setClipping(False)
        painter.setPen(QPen(QColor(ECHARTS_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
