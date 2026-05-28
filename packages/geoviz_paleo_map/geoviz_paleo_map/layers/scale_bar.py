"""ScaleBarLayer — bottom-left bar + dynamic km label.

The bar's pixel length is proportional to zoom (grows when zoomed in,
shrinks when zoomed out), so it changes smoothly on every scroll tick.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


BAR_COLOR = QColor("#334155")
BAR_MIN_PX = 40.0
BAR_MAX_PX = 160.0


def _smooth_scale_km(extent_km: float) -> float:
    """Bar's real-world km — directly proportional to zoom."""
    if extent_km <= 0:
        return 1.0
    return extent_km * 0.3


class ScaleBarLayer(PaleoLayer):
    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        bbox = viewport.world_bbox()
        mid_lat = (bbox[1] + bbox[3]) / 2
        deg_to_km = 111.32 * math.cos(math.radians(mid_lat))
        extent_km = (bbox[2] - bbox[0]) * deg_to_km
        scale_km = _smooth_scale_km(extent_km)

        if scale_km >= 1:
            label = f"{scale_km:.1f} km"
        else:
            label = f"{scale_km * 1000:.0f} m"

        # Bar length proportional to zoom: maps extent range to pixel range
        # Extent 2000km → 40px, extent 100km → 160px
        bar_px = BAR_MAX_PX - (extent_km - 100) / (2000 - 100) * (BAR_MAX_PX - BAR_MIN_PX)
        bar_px = max(BAR_MIN_PX, min(BAR_MAX_PX, bar_px))

        x0 = 16.0
        y0 = viewport.height - 24.0
        pen = QPen(BAR_COLOR, 2.0)
        painter.setPen(pen)
        painter.drawLine(QPointF(x0, y0), QPointF(x0 + bar_px, y0))
        painter.drawLine(QPointF(x0, y0 - 4), QPointF(x0, y0 + 4))
        painter.drawLine(QPointF(x0 + bar_px, y0 - 4),
                         QPointF(x0 + bar_px, y0 + 4))

        font = QFont("Sans Serif", 8)
        painter.setFont(font)
        painter.setPen(QPen(BAR_COLOR, 0))
        metrics = painter.fontMetrics()
        w = metrics.horizontalAdvance(label)
        painter.drawText(
            QPointF(x0 + bar_px / 2 - w / 2, y0 + 14),
            label,
        )
