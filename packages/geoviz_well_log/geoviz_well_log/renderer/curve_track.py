from __future__ import annotations

import bisect
from math import log10

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QFont
from PySide6.QtWidgets import QWidget

from ..models import CurveData, LineStyle
from .track_base import BaseTrack


class CurveTrack(BaseTrack):
    """Log curve track with viewport culling and adaptive downsampling."""

    def __init__(self, curves: list[CurveData], label: str = "",
                 width: int = 150, log_scale: bool = False,
                 header_height: int = 32, parent=None):
        super().__init__(label=label or (curves[0].name if curves else ""),
                         width=width, header_height=header_height, parent=parent)
        self._curves = curves
        self._log_scale = log_scale
        # Pre-sort depths for binary search
        for c in self._curves:
            if c.depth != sorted(c.depth):
                pairs = sorted(zip(c.depth, c.values))
                c.depth = [p[0] for p in pairs]
                c.values = [p[1] for p in pairs]

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def _value_to_x(self, value: float, display_range: tuple[float, float],
                    rect: QRectF) -> float:
        lo, hi = display_range
        if self._log_scale:
            if value <= 0:
                value = lo
            lo = max(lo, 1e-10)
            hi = max(hi, 1e-10)
            t = (log10(value) - log10(lo)) / (log10(hi) - log10(lo))
        else:
            t = (value - lo) / (hi - lo) if hi != lo else 0.5
        return rect.left() + t * rect.width()

    def _visible_data(self, curve: CurveData) -> tuple[list[float], list[float]]:
        margin = (self.depth_bottom - self.depth_top) * 0.01
        top = self.depth_top - margin
        bottom = self.depth_bottom + margin
        start = bisect.bisect_left(curve.depth, top)
        end = bisect.bisect_right(curve.depth, bottom)
        return curve.depth[start:end], curve.values[start:end]

    def _downsample(self, depths: list[float], values: list[float],
                    pixel_height: int) -> tuple[list[float], list[float]]:
        if len(depths) <= pixel_height * 2:
            return depths, values
        arr_v = np.array(values)
        step = max(1, len(arr_v) // pixel_height)
        result_d: list[float] = []
        result_v: list[float] = []
        for i in range(0, len(arr_v), step):
            chunk = arr_v[i:i + step]
            max_idx = i + int(np.argmax(chunk))
            min_idx = i + int(np.argmin(chunk))
            result_d.append(depths[max_idx])
            result_v.append(values[max_idx])
            result_d.append(depths[min_idx])
            result_v.append(values[min_idx])
        return result_d, result_v

    def _make_pen(self, curve: CurveData) -> QPen:
        pen = QPen(QColor(curve.color), 1.5)
        if curve.line_style == LineStyle.DASHED:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif curve.line_style == LineStyle.DOTTED:
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        return pen

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipRect(rect)

        # Light grid
        painter.setPen(QPen(QColor("#e5e7eb"), 0.5, Qt.PenStyle.DotLine))
        painter.drawLine(int(rect.left()), int(rect.top()), int(rect.left()), int(rect.bottom()))

        pixel_height = max(1, int(rect.height()))

        for curve in self._curves:
            depths, values = self._visible_data(curve)
            depths, values = self._downsample(depths, values, pixel_height)
            if len(depths) < 2:
                continue

            path = QPainterPath()
            first = True
            for d, v in zip(depths, values):
                x = self._value_to_x(v, curve.display_range, rect)
                y = self._depth_to_y(d, rect)
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)

            painter.setPen(self._make_pen(curve))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # Display range labels
        if self._curves:
            c = self._curves[0]
            lo, hi = c.display_range
            font = QFont()
            font.setPointSize(6)
            painter.setFont(font)
            painter.setPen(QColor("#999999"))
            painter.drawText(QRectF(rect.left(), rect.top() + 2, rect.width(), 12),
                             Qt.AlignmentFlag.AlignLeft, f"{lo}")
            painter.drawText(QRectF(rect.left(), rect.bottom() - 14, rect.width(), 12),
                             Qt.AlignmentFlag.AlignLeft, f"{hi}")

        # Border
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setClipping(False)
        painter.drawRect(rect)
        painter.restore()
