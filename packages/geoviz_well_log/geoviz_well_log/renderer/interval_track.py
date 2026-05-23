from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush

from ..models import IntervalItem
from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT

_PASTEL_PALETTE = [
    "#d4e6f1", "#d5f5e3", "#fdebd0", "#e8daef",
    "#fcf3cf", "#fadbd8", "#d1f2eb", "#ebdef0",
]


class IntervalTrack(BaseTrack):
    """Generic interval column for stratigraphy, descriptions, etc."""

    def __init__(self, intervals: list[IntervalItem], label: str = "",
                 width: int = 80, colors: dict[str, str] | None = None,
                 header_height: int = 32, group_name: str = "", parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         group_name=group_name, parent=parent)
        self._intervals = intervals
        self._colors = colors or {}

    def _get_color(self, index: int, name: str) -> QColor:
        if name in self._colors:
            return QColor(self._colors[name])
        return QColor(_PASTEL_PALETTE[index % len(_PASTEL_PALETTE)])

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect)

        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        font = QFont()
        font.setBold(True)
        # will be set per-text-orientation below
        painter.setFont(font)

        for i, interval in enumerate(self._intervals):
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            # Skip intervals outside visible range
            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            # Clamp to rect
            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)
            color = self._get_color(i, interval.name)

            painter.fillRect(interval_rect, QBrush(color))

            # Border
            painter.setPen(QPen(QColor(ECHARTS_BORDER), 0.5))
            painter.drawRect(interval_rect)

            # Label
            painter.setPen(QPen(QColor(ECHARTS_TEXT), 1))
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            if interval_rect.height() > 14:
                if rect.width() < 50:
                    font.setPixelSize(11)
                    painter.setFont(font)
                    painter.save()
                    painter.translate(text_rect.center())
                    painter.rotate(-90)
                    rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                     text_rect.height(), text_rect.width())
                    painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, interval.name)
                    painter.restore()
                else:
                    font.setPixelSize(10)
                    painter.setFont(font)
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, interval.name)

        painter.setClipping(False)
        painter.setPen(QPen(QColor(ECHARTS_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
