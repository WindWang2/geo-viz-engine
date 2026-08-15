"""ScaleBarLayer — bottom-left bar + dynamic km label.

The bar's km value is a "nice" round length from the 0.5/1/2/5 x 10^n km
series, chosen so the bar is ~100 px long on screen. Its pixel length is
derived from that same km value and the real km-per-pixel rate of the visible
extent, so the label always equals the actual bar length.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.label_policy import chrome_font_size
from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


BAR_COLOR = QColor("#334155")
BAR_MIN_PX = 40.0
BAR_MAX_PX = 160.0
BAR_TARGET_PX = 100.0


def _smooth_scale_km(extent_km: float) -> float:
    """Bar's real-world km — directly proportional to zoom."""
    if extent_km <= 0:
        return 1.0
    return extent_km * 0.3


def _nice_bar_km(target_km: float) -> float:
    """Nearest length from the 0.5/1/2/5 x 10^n km series to the target."""
    if target_km <= 0:
        return 0.5
    mag = 10 ** math.floor(math.log10(target_km))
    best = 5.0 * mag
    best_diff = float("inf")
    for cand in (0.5, 1.0, 2.0, 5.0, 10.0):
        val = cand * mag
        diff = abs(val - target_km)
        if diff < best_diff:
            best_diff = diff
            best = val
    return best


class ScaleBarLayer(PaleoLayer):
    is_chrome = True

    def reserved_rect(self, viewport: PaleoMapViewport) -> QRectF:
        """Screen rect this scale bar occupies, for label collision avoidance."""
        x0 = 16.0
        y0 = viewport.height - 24.0
        # Reserve the widest possible bar + the label row beneath it.
        return QRectF(x0 - 4, y0 - 8, BAR_MAX_PX + 8, 30)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        bbox = viewport.world_bbox()
        mid_lat = (bbox[1] + bbox[3]) / 2
        deg_to_km = 111.32 * math.cos(math.radians(mid_lat))
        extent_km = (bbox[2] - bbox[0]) * deg_to_km

        # Real km-per-pixel of the visible extent. The label and the bar length
        # both derive from this same rate, so the label always matches the bar.
        km_per_px = extent_km / max(1.0, float(viewport.width))
        if km_per_px <= 0:
            return
        bar_km = _nice_bar_km(BAR_TARGET_PX * km_per_px)
        bar_px = bar_km / km_per_px

        if bar_km >= 1:
            label = f"{bar_km:g} km"
        else:
            label = f"{bar_km * 1000:g} m"

        x0 = 16.0
        y0 = viewport.height - 24.0
        pen = QPen(BAR_COLOR, 2.0)
        painter.setPen(pen)
        painter.drawLine(QPointF(x0, y0), QPointF(x0 + bar_px, y0))
        painter.drawLine(QPointF(x0, y0 - 4), QPointF(x0, y0 + 4))
        painter.drawLine(QPointF(x0 + bar_px, y0 - 4),
                         QPointF(x0 + bar_px, y0 + 4))

        font = QFont("Sans Serif", chrome_font_size(viewport.width, viewport.height, 8))
        painter.setFont(font)
        painter.setPen(QPen(BAR_COLOR, 0))
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(label)
        painter.drawText(
            QPointF(x0 + bar_px / 2 - w / 2, y0 + 14),
            label,
        )
