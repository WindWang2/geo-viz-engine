from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget

from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT


class DepthTrack(BaseTrack):
    """Depth ruler track with adaptive tick spacing."""

    def __init__(self, top_depth: float = 0.0, bottom_depth: float = 100.0,
                 width: int = 60, header_height: int = 56, label: str = "Depth", parent=None):
        super().__init__(label=label, width=width, header_height=header_height, parent=parent)
        self._tick_interval = 10.0
        self.set_depth_range(top_depth, bottom_depth)

    @property
    def tick_interval(self) -> float:
        return self._tick_interval

    def _compute_tick_interval(self, rect_height: float) -> float:
        # Delegate to the shared mantissa/exponent nice-number walk on
        # BaseTrack: the previous integer-only table [1..5000] left spans
        # below 1 depth unit with no representable interval (WL-13).
        return self._compute_grid_interval(rect_height, self.depth_span)

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setClipRect(rect.adjusted(-2, -2, 2, 2))

        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        self._tick_interval = self._compute_tick_interval(rect.height())

        # Safety guard against zero interval (infinite loop)
        interval = self._tick_interval
        if interval <= 0:
            interval = 10.0

        # Draw depth labels centered in track
        font = painter.font()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ECHARTS_TEXT))

        # Sub-unit intervals need fractional labels: with the old fixed
        # "{depth:.0f}" every tick inside a <1-unit window collapsed onto the
        # same integer text (WL-13).
        decimals = max(0, -math.floor(math.log10(interval))) if interval > 0 else 0

        start = (self.depth_top // interval) * interval
        if start < self.depth_top:
            start += interval
        depth = start
        while depth <= self.depth_bottom:
            y = self._depth_to_y(depth, rect)
            if rect.top() <= y <= rect.bottom():
                # Centered label
                text_rect = QRectF(rect.left(), y - 8, rect.width(), 16)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{depth:.{decimals}f}")
            depth += interval

        # Right edge border only
        pen = QPen(QColor(ECHARTS_BORDER), 1)
        painter.setPen(pen)
        painter.drawLine(QPointF(rect.right(), rect.top()), QPointF(rect.right(), rect.bottom()))
        painter.restore()
