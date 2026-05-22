from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtWidgets import QWidget

from ..models import IntervalItem, FaciesData
from ..pattern_map import FACIES_COLORS
from .track_base import BaseTrack


class FaciesTrack(BaseTrack):
    """Facies column with color fills. Supports single and nested display."""

    def __init__(self, facies_data: FaciesData, label: str = "Facies",
                 width: int = 80, nested: bool = False,
                 header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._facies_data = facies_data
        self._nested = nested

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def _get_color(self, name: str) -> QColor:
        hex_color = FACIES_COLORS.get(name, "#e0e0e0")
        return QColor(hex_color)

    def _paint_column(self, painter: QPainter, rect: QRectF, intervals: list[IntervalItem]):
        painter.save()
        painter.setClipRect(rect)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        for interval in intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)
            color = self._get_color(interval.name)

            painter.fillRect(interval_rect, QBrush(color))

            painter.setPen(QPen(QColor("#666666"), 0.5))
            painter.drawRect(interval_rect)

            painter.setPen(QPen(QColor("#333333"), 1))
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            if interval_rect.height() > 14:
                if rect.width() < 50:
                    painter.save()
                    painter.translate(text_rect.center())
                    painter.rotate(-90)
                    rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                     text_rect.height(), text_rect.width())
                    painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, interval.name)
                    painter.restore()
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, interval.name)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()

    def paint_content(self, painter: QPainter, rect: QRectF):
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
