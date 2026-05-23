from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import QWidget

from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT


class DepthTrack(BaseTrack):
    """Depth ruler track with adaptive tick spacing."""

    def __init__(self, top_depth: float = 0.0, bottom_depth: float = 100.0,
                 width: int = 60, header_height: int = 56, parent=None):
        super().__init__(label="Depth", width=width, header_height=header_height, parent=parent)
        self._tick_interval = 10.0
        self.set_depth_range(top_depth, bottom_depth)

    @property
    def tick_interval(self) -> float:
        return self._tick_interval

    def _compute_tick_interval(self, rect_height: float) -> float:
        span = self.depth_span
        if span <= 0:
            return 10.0
        candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
        for c in candidates:
            num_ticks = span / c
            pixels_per_tick = rect_height / num_ticks
            if pixels_per_tick >= 20:
                return float(c)
        return float(candidates[-1])

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setClipRect(rect)

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

        start = (self.depth_top // interval) * interval
        if start < self.depth_top:
            start += interval
        depth = start
        while depth <= self.depth_bottom:
            y = self._depth_to_y(depth, rect)
            if rect.top() <= y <= rect.bottom():
                # Centered label
                text_rect = QRectF(rect.left(), y - 8, rect.width(), 16)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, f"{depth:.0f}")
            depth += interval

        # Right edge border only
        pen = QPen(QColor(ECHARTS_BORDER), 1)
        painter.setPen(pen)
        painter.drawLine(QPointF(rect.right(), rect.top()), QPointF(rect.right(), rect.bottom()))
        painter.restore()
