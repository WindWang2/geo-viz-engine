from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF, QBrush

from ..models import IntervalItem
from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT

_TRACT_COLORS: dict[str, str] = {
    "TST": "#93c5fd",
    "HST": "#fde047",
    "LST": "#70AD47",
    "海侵体系域": "#93c5fd",
    "高位体系域": "#fde047",
    "低位体系域": "#70AD47",
}

_TRACT_SHAPES: dict[str, str] = {
    "TST": "triangle_up",
    "海侵体系域": "triangle_up",
    "HST": "triangle_down",
    "高位体系域": "triangle_down",
    "LST": "rectangle",
    "低位体系域": "rectangle",
}


class SystemsTractTrack(BaseTrack):
    """Systems tract column with geometric shape fills (TST/HST/LST)."""

    def __init__(self, intervals: list[IntervalItem], label: str = "Systems Tract",
                 width: int = 60, header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._intervals = intervals

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect)

        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        for interval in self._intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)
            color = QColor(_TRACT_COLORS.get(interval.name, "#b0b0b0"))
            shape = _TRACT_SHAPES.get(interval.name, "rectangle")

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(ECHARTS_BORDER), 0.5))

            if shape == "triangle_up":
                polygon = QPolygonF([
                    interval_rect.bottomLeft(),
                    interval_rect.bottomRight(),
                    QPointF(interval_rect.center().x(), interval_rect.top()),
                ])
                painter.drawPolygon(polygon)
            elif shape == "triangle_down":
                polygon = QPolygonF([
                    interval_rect.topLeft(),
                    interval_rect.topRight(),
                    QPointF(interval_rect.center().x(), interval_rect.bottom()),
                ])
                painter.drawPolygon(polygon)
            else:
                painter.drawRect(interval_rect)

            # Label
            painter.setPen(QPen(QColor(ECHARTS_TEXT), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            if interval_rect.height() > 14:
                painter.save()
                painter.translate(text_rect.center())
                painter.rotate(-90)
                rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                 text_rect.height(), text_rect.width())
                painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, interval.name)
                painter.restore()

        painter.setClipping(False)
        painter.setPen(QPen(QColor(ECHARTS_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
