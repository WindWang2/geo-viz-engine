"""ColorbarWidget rendering continuous colormap spectrum and discrete lithology swatches."""
from __future__ import annotations
from typing import List, Tuple, Optional
import numpy as np

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QLinearGradient

from geoviz_plots.surface.surface_widget import COLORMAPS

class ColorbarWidget(QWidget):
    """Vertical colorbar widget with continuous gradient spectrum and discrete swatch legend modes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(65)

        self._mode = "continuous"  # "continuous" | "discrete"
        self._vmin = 0.0
        self._vmax = 1.0
        self._colormap_name = "viridis"
        self._swatches: List[Tuple[str, QColor]] = []

    def set_continuous_range(self, vmin: float, vmax: float, colormap_name: str = "viridis"):
        self._mode = "continuous"
        self._vmin = float(vmin)
        self._vmax = float(vmax)
        self._colormap_name = colormap_name if colormap_name in COLORMAPS else "viridis"
        self.update()

    def set_discrete_swatches(self, swatches: List[Tuple[str, QColor]]):
        self._mode = "discrete"
        self._swatches = list(swatches)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        margin_top, margin_bottom = 20.0, 30.0
        bar_w = 20.0
        bar_x = 10.0
        bar_h = max(10.0, H - margin_top - margin_bottom)

        if self._mode == "continuous":
            # Draw gradient bar
            bar_rect = QRectF(bar_x, margin_top, bar_w, bar_h)
            grad = QLinearGradient(bar_x, margin_top + bar_h, bar_x, margin_top)

            cmap_stops = COLORMAPS.get(self._colormap_name, COLORMAPS["viridis"])
            for pos, col in cmap_stops:
                grad.setColorAt(pos, col)

            painter.setBrush(QBrush(grad))
            painter.setPen(QPen(QColor(88, 104, 120), 1))
            painter.drawRect(bar_rect)

            # Draw tick labels
            painter.setPen(QColor(210, 210, 210))
            painter.setFont(QFont("SansSerif", 8))

            ticks = np.linspace(self._vmin, self._vmax, 5)
            for val in ticks:
                norm_y = (val - self._vmin) / max(1e-6, (self._vmax - self._vmin))
                py = margin_top + bar_h * (1.0 - norm_y)
                painter.drawLine(int(bar_x + bar_w), int(py), int(bar_x + bar_w + 4), int(py))
                painter.drawText(QRectF(bar_x + bar_w + 6, py - 8, 30, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"{val:.1f}")

        else:
            # Draw discrete swatches
            if not self._swatches:
                return
            n = len(self._swatches)
            row_h = min(24.0, bar_h / n)
            font = QFont("SansSerif", 8)
            painter.setFont(font)

            for i, (name, color) in enumerate(self._swatches):
                py = margin_top + i * row_h
                swatch_rect = QRectF(bar_x, py + 2, 14, row_h - 4)
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(88, 104, 120), 1))
                painter.drawRect(swatch_rect)

                painter.setPen(QColor(210, 210, 210))
                painter.drawText(QRectF(bar_x + 18, py, W - bar_x - 18, row_h), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
