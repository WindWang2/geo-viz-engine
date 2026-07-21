from __future__ import annotations

import bisect
import math
from math import log10

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QFont
from PySide6.QtWidgets import QWidget

from ..models import CurveData, LineStyle
from .downsample import get_downsample_provider
from .label_layout import compute_header_label_policy, fit_label_text
from .track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_TEXT


class CurveTrack(BaseTrack):
    """Log curve track with viewport culling and adaptive downsampling."""

    def __init__(self, curves: list[CurveData], label: str = "",
                 width: int = 150, log_scale: bool = False,
                 header_height: int | None = None, parent=None):
        # Dynamic header height: base 28px + 18px per curve, min 56px
        n_curves = len(curves)
        computed_hh = header_height if header_height is not None else max(56, 28 + n_curves * 18)
        super().__init__(label=label or (curves[0].name if curves else ""),
                         width=width, header_height=computed_hh, parent=parent)
        from ..robust_scale import compute_robust_display_range
        sanitized_curves = []
        for c in curves:
            lo, hi = c.display_range
            if lo <= -100.0 or hi > 1e5 or math.isclose(lo, hi):
                robust_range = compute_robust_display_range(c.values, c.name)
                c = CurveData(
                    name=c.name,
                    unit=c.unit,
                    depth=c.depth,
                    values=c.values,
                    display_range=robust_range,
                    color=c.color,
                    line_style=c.line_style,
                )
            sanitized_curves.append(c)
        self._curves = sanitized_curves
        self._log_scale = log_scale
        self._path_cache = {}
        # Store sorted copies — never mutate the original Pydantic models
        self._sorted_depths: dict[str, list[float]] = {}
        self._sorted_values: dict[str, list[float]] = {}
        for c in self._curves:
            if c.depth != sorted(c.depth):
                pairs = sorted(zip(c.depth, c.values))
                self._sorted_depths[c.name] = [p[0] for p in pairs]
                self._sorted_values[c.name] = [p[1] for p in pairs]
            else:
                self._sorted_depths[c.name] = list(c.depth)
                self._sorted_values[c.name] = list(c.values)

    def _value_to_x(self, value: float, display_range: tuple[float, float],
                    rect: QRectF) -> float:
        lo, hi = display_range
        if self._log_scale:
            if value <= 0:
                value = lo
            lo = max(lo, 1e-10)
            hi = max(hi, 1e-10)
            if lo == hi:
                t = 0.5
            else:
                t = (log10(value) - log10(lo)) / (log10(hi) - log10(lo))
        else:
            t = (value - lo) / (hi - lo) if hi != lo else 0.5
        return rect.left() + t * rect.width()

    def _visible_data(self, curve: CurveData) -> tuple[list[float], list[float]]:
        depths = self._sorted_depths.get(curve.name, curve.depth)
        values = self._sorted_values.get(curve.name, curve.values)
        if not depths or not values:
            return [], []
        margin = (self.depth_bottom - self.depth_top) * 0.05
        top = self.depth_top - margin
        bottom = self.depth_bottom + margin
        start = bisect.bisect_left(depths, top)
        end = bisect.bisect_right(depths, bottom)
        start = max(0, start - 1)
        end = min(len(depths), end + 1)
        return depths[start:end], values[start:end]

    def _downsample(self, depths: list[float], values: list[float],
                    pixel_height: int) -> tuple[list[float], list[float]]:
        return get_downsample_provider()(depths, values, pixel_height)

    def _make_pen(self, curve: CurveData) -> QPen:
        pen = QPen(QColor(curve.color), 1.5)
        if curve.line_style == LineStyle.DASHED:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif curve.line_style == LineStyle.DOTTED:
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        return pen

    def paint_header(self, painter: QPainter, rect: QRectF):
        """Draw header with centered track name and curve legends with min/max."""
        # Track name — centered at top, adaptive font with wrap
        policy = compute_header_label_policy(rect)
        font = painter.font()
        font.setPixelSize(policy.font_px)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(ECHARTS_TEXT))
        name_rect = QRectF(rect.left(), rect.top() + 2, rect.width(), policy.font_px + 6)
        lines = fit_label_text(self._label, name_rect.adjusted(4, 0, -4, 0), policy, painter.fontMetrics())
        painter.drawText(name_rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignCenter, "\n".join(lines))

        # Curve legends — each row: [swatch] name  min~max unit
        font.setPixelSize(10)
        font.setBold(False)
        painter.setFont(font)

        y_offset = rect.top() + 22
        row_height = 14
        for curve in self._curves:
            if y_offset + row_height > rect.bottom():
                break
            color = QColor(curve.color)

            # Color swatch (small filled rect)
            swatch_rect = QRectF(rect.left() + 6, y_offset + 4, 10, 5)
            painter.fillRect(swatch_rect, color)

            # Compute min/max from curve values
            vals = curve.values
            if vals:
                vmin = min(vals)
                vmax = max(vals)
                range_str = f"{vmin:.1f}~{vmax:.1f} {curve.unit}".strip()
            else:
                range_str = curve.unit

            # Curve name + range
            painter.setPen(color)
            label = f"{curve.name}  {range_str}"
            text_rect = QRectF(rect.left() + 20, y_offset, rect.width() - 24, row_height)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)
            y_offset += row_height

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # Expand clip slightly so 1.5px antialiased pen at boundaries isn't truncated
        painter.setClipRect(rect.adjusted(-2, -2, 2, 2))

        # Horizontal grid lines (ECharts splitLine parity)
        self.paint_grid(painter, rect)

        pixel_height = max(1, int(rect.height()))

        for curve in self._curves:
            cache_key = (
                self.depth_top,
                self.depth_bottom,
                rect.left(),
                rect.top(),
                rect.width(),
                rect.height(),
                self._log_scale,
            )
            
            cached = self._path_cache.get(curve.name)
            if cached is not None and cached[0] == cache_key:
                path = cached[1]
            else:
                depths, values = self._visible_data(curve)
                depths, values = self._downsample(depths, values, pixel_height)
                if len(depths) < 2:
                    continue

                # Vectorize coordinate mapping using numpy
                depths_arr = np.array(depths)
                values_arr = np.array(values)

                # y coordinate calculation
                ys = rect.top() + (depths_arr - self.depth_top) / (self.depth_bottom - self.depth_top) * rect.height()

                # x coordinate calculation based on display scale mode
                lo, hi = curve.display_range
                if self._log_scale:
                    clipped_vals = np.clip(values_arr, max(lo, 1e-10), None)
                    log_lo = log10(max(lo, 1e-10))
                    log_hi = log10(max(hi, 1e-10))
                    if log_lo == log_hi:
                        xs = np.full_like(values_arr, rect.left() + 0.5 * rect.width())
                    else:
                        t_arr = (np.log10(clipped_vals) - log_lo) / (log_hi - log_lo)
                        xs = rect.left() + t_arr * rect.width()
                else:
                    if hi == lo:
                        xs = np.full_like(values_arr, rect.left() + 0.5 * rect.width())
                    else:
                        t_arr = (values_arr - lo) / (hi - lo)
                        xs = rect.left() + t_arr * rect.width()

                path = QPainterPath()
                first = True
                for x, y in zip(xs, ys):
                    if np.isnan(x) or np.isnan(y) or np.isinf(x) or np.isinf(y):
                        first = True
                        continue
                    if first:
                        path.moveTo(float(x), float(y))
                        first = False
                    else:
                        path.lineTo(float(x), float(y))

                self._path_cache[curve.name] = (cache_key, path)

            painter.setPen(self._make_pen(curve))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # Display range labels (multi-scale side-by-side)
        if self._curves:
            K = len(self._curves)
            W = rect.width()
            font = QFont()
            font.setPixelSize(10)
            painter.setFont(font)
            for i, curve in enumerate(self._curves):
                lo, hi = curve.display_range
                color = QColor(curve.color)
                painter.setPen(color)
                x_start = rect.left() + i * (W / K)
                col_width = W / K
                lo_str = f"{int(lo)}" if lo == int(lo) else f"{lo:.1f}"
                hi_str = f"{int(hi)}" if hi == int(hi) else f"{hi:.1f}"
                painter.drawText(QRectF(x_start + 2, rect.top() + 2, col_width - 4, 12),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, lo_str)
                painter.drawText(QRectF(x_start + 2, rect.bottom() - 14, col_width - 4, 12),
                                 Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, hi_str)


        # Border
        painter.setPen(QPen(QColor(ECHARTS_BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setClipping(False)
        painter.drawRect(rect)
        painter.restore()
