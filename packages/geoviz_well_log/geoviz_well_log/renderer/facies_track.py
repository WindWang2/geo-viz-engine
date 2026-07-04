from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush

from ..models import IntervalItem, FaciesData
from ..pattern_map import FACIES_COLORS
from .label_layout import compute_label_policy, fit_label_text
from .pattern_engine import PatternEngine
from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT

_shared_pattern_engine = PatternEngine()


class FaciesTrack(BaseTrack):
    """Facies column with SVG pattern fills and color fallback."""

    def __init__(self, facies_data: FaciesData, label: str = "Facies",
                 width: int = 80, nested: bool = False,
                 header_height: int = 32, group_name: str = "",
                 pattern_engine: PatternEngine | None = None,
                 parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         group_name=group_name, parent=parent)
        self._facies_data = facies_data
        self._nested = nested
        self._pattern_engine = pattern_engine or _shared_pattern_engine

    def _paint_column(self, painter: QPainter, rect: QRectF, intervals: list[IntervalItem]):
        painter.save()
        painter.setClipRect(rect.adjusted(-2, -2, 2, 2))

        font = QFont()
        font.setBold(True)
        interval_rects: list[tuple[IntervalItem, QRectF]] = []
        for iv in intervals:
            y_top = self._depth_to_y(iv.top, rect)
            y_bottom = self._depth_to_y(iv.bottom, rect)
            if y_bottom < rect.top() or y_top > rect.bottom():
                continue
            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())
            interval_rects.append((iv, QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)))

        policy = compute_label_policy(rect, self.depth_span, [r.height() for _, r in interval_rects])
        font.setPixelSize(policy.font_px)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        for iv, iv_rect in interval_rects:

            # Try SVG pattern fill first, fallback to color
            brush = self._pattern_engine.get_brush(iv.name)
            if brush is not None:
                painter.fillRect(iv_rect, brush)
            else:
                hex_color = FACIES_COLORS.get(iv.name, "#e0e0e0")
                painter.fillRect(iv_rect, QBrush(QColor(hex_color)))

            # Border
            painter.setPen(QPen(QColor(ECHARTS_BORDER), 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(iv_rect)

            painter.setPen(QPen(QColor(ECHARTS_TEXT), 1))
            text_rect = QRectF(iv_rect.left() + 2, iv_rect.top() + 1,
                               iv_rect.width() - 4, iv_rect.height() - 2)
            lines = fit_label_text(iv.name, text_rect, policy, metrics)
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

    def paint_content(self, painter: QPainter, rect: QRectF):
        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        if self._nested:
            col_width = rect.width() / 3
            phase_rect = QRectF(rect.left(), rect.top(), col_width, rect.height())
            sub_rect = QRectF(rect.left() + col_width, rect.top(), col_width, rect.height())
            micro_rect = QRectF(rect.left() + 2 * col_width, rect.top(), col_width, rect.height())

            if self._facies_data.phase:
                self._paint_column(painter, phase_rect, self._facies_data.phase)
            if self._facies_data.sub_phase:
                self._paint_column(painter, sub_rect, self._facies_data.sub_phase)
            if self._facies_data.micro_phase:
                self._paint_column(painter, micro_rect, self._facies_data.micro_phase)
        else:
            if self._facies_data.micro_phase:
                self._paint_column(painter, rect, self._facies_data.micro_phase)
            elif self._facies_data.sub_phase:
                self._paint_column(painter, rect, self._facies_data.sub_phase)
            elif self._facies_data.phase:
                self._paint_column(painter, rect, self._facies_data.phase)
