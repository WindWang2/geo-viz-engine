from __future__ import annotations

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


def clip_curve_depth_range(
    depths: np.ndarray, values: np.ndarray, top_depth: float, bottom_depth: float
) -> tuple[np.ndarray, np.ndarray]:
    """Clip curve depth and values arrays strictly to the visible viewport depth range."""
    if len(depths) == 0:
        return depths, values

    mask = (depths >= top_depth) & (depths <= bottom_depth)
    return depths[mask], values[mask]


def simplify_curve_screen_space(
    x_px: np.ndarray, y_px: np.ndarray, epsilon: float = 0.5
) -> tuple[np.ndarray, np.ndarray]:
    """Fast bucket min-max simplification for screen-space 60 FPS curve rendering."""
    n = len(x_px)
    if n <= 1000:
        return x_px, y_px

    bucket_size = max(2, n // 400)
    n_buckets = n // bucket_size

    x_trunc = x_px[: n_buckets * bucket_size].reshape(n_buckets, bucket_size)
    y_trunc = y_px[: n_buckets * bucket_size].reshape(n_buckets, bucket_size)

    idx_min = np.argmin(x_trunc, axis=1)
    idx_max = np.argmax(x_trunc, axis=1)

    rows = np.arange(n_buckets)
    rows_combined = np.repeat(rows, 2)
    idx_combined = np.column_stack([idx_min, idx_max]).ravel()

    return x_trunc[rows_combined, idx_combined], y_trunc[rows_combined, idx_combined]


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
        self._downsampled_cache = {}
        # Store sorted ndarray copies — never mutate the original Pydantic models
        self._sorted_depths: dict[str, np.ndarray] = {}
        self._sorted_values: dict[str, np.ndarray] = {}
        self._range_strs: dict[str, str] = {}
        for c in self._curves:
            if c.depth != sorted(c.depth):
                pairs = sorted(zip(c.depth, c.values))
                self._sorted_depths[c.name] = np.asarray([p[0] for p in pairs], dtype=np.float64)
                self._sorted_values[c.name] = np.asarray([p[1] for p in pairs], dtype=np.float64)
            else:
                self._sorted_depths[c.name] = np.asarray(c.depth, dtype=np.float64)
                self._sorted_values[c.name] = np.asarray(c.values, dtype=np.float64)
            vals = self._sorted_values[c.name]
            if len(vals) and not np.all(np.isnan(vals)):
                vmin = float(np.nanmin(vals))
                vmax = float(np.nanmax(vals))
                self._range_strs[c.name] = f"{vmin:.1f}~{vmax:.1f} {c.unit}".strip()
            else:
                self._range_strs[c.name] = c.unit

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

    def _visible_data(self, curve: CurveData) -> tuple[np.ndarray, np.ndarray]:
        depths = self._sorted_depths.get(curve.name)
        values = self._sorted_values.get(curve.name)
        if depths is None or values is None or len(depths) == 0:
            empty = np.empty(0, dtype=np.float64)
            return empty, empty
        margin = (self.depth_bottom - self.depth_top) * 0.05
        top = self.depth_top - margin
        bottom = self.depth_bottom + margin
        start = max(0, int(np.searchsorted(depths, top, side="left")) - 1)
        end = min(len(depths), int(np.searchsorted(depths, bottom, side="right")) + 1)
        return depths[start:end], values[start:end]

    def _downsample(self, depths: np.ndarray, values: np.ndarray,
                    pixel_height: int) -> tuple[np.ndarray, np.ndarray]:
        return get_downsample_provider()(depths, values, pixel_height)

    def _range_str_for(self, curve: CurveData) -> str:
        return self._range_strs.get(curve.name, curve.unit)

    def _cached_downsampled(self, curve: CurveData, rect: QRectF) -> tuple[np.ndarray, np.ndarray]:
        """Downsampled arrays cached on a quantized depth-window key."""
        pixel_height = max(1, int(rect.height()))
        span = max(1e-9, self.depth_bottom - self.depth_top)
        quantum = span / pixel_height
        key = (
            pixel_height,
            int(round(rect.width())),
            int(round(span)),
            int(round(self.depth_top / quantum)),
            int(round(self.depth_bottom / quantum)),
        )
        cached = self._downsampled_cache.get(curve.name)
        if cached is not None and cached[0] == key:
            return cached[1], cached[2]
        depths, values = self._visible_data(curve)
        depths, values = self._downsample(depths, values, pixel_height)
        self._downsampled_cache[curve.name] = (key, depths, values)
        return depths, values

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

            range_str = self._range_str_for(curve)

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

        for curve in self._curves:
            depths, values = self._cached_downsampled(curve, rect)
            if len(depths) < 2:
                continue

            # y coordinate calculation
            ys = rect.top() + (depths - self.depth_top) / (self.depth_bottom - self.depth_top) * rect.height()

            # x coordinate calculation based on display scale mode
            lo, hi = curve.display_range
            if self._log_scale:
                clipped_vals = np.clip(values, max(lo, 1e-10), None)
                log_lo = log10(max(lo, 1e-10))
                log_hi = log10(max(hi, 1e-10))
                if log_lo == log_hi:
                    xs = np.full_like(values, rect.left() + 0.5 * rect.width())
                else:
                    t_arr = (np.log10(clipped_vals) - log_lo) / (log_hi - log_lo)
                    xs = rect.left() + t_arr * rect.width()
            else:
                if hi == lo:
                    xs = np.full_like(values, rect.left() + 0.5 * rect.width())
                else:
                    t_arr = (values - lo) / (hi - lo)
                    xs = rect.left() + t_arr * rect.width()

            finite = np.isfinite(xs) & np.isfinite(ys)
            path = QPainterPath()
            first = True
            for x, y, ok in zip(xs, ys, finite):
                if not ok:
                    first = True
                    continue
                if first:
                    path.moveTo(float(x), float(y))
                    first = False
                else:
                    path.lineTo(float(x), float(y))

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
