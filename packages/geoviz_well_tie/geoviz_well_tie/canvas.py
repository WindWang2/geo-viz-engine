"""7-Track QPainter high-performance rendering canvas for well-seismic tie workspace."""
from __future__ import annotations
from typing import Optional, List, Tuple
import numpy as np

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush, QPixmap, QPolygonF

from geoviz_well_tie.synthetic_generator import compute_impedance, compute_reflectivity, generate_synthetic_seismogram
from geoviz_well_tie.wavelet_engine import generate_ricker_wavelet

class WellTieCanvas(QWidget):
    """High-performance 7-Track well-seismic tie rendering widget.

    Tracks:
    1. Depth / TWT Axis
    2. Logs (DT & RHOB)
    3. Impedance (AI)
    4. Reflectivity (RC)
    5. Synthetic Seismogram
    6. Real Seismic Traces
    7. Cross-Correlation & Residual
    """

    cursor_moved = Signal(float, float, float)  # depth, twt, correlation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self._depths: Optional[np.ndarray] = None
        self._twt: Optional[np.ndarray] = None
        self._sonic: Optional[np.ndarray] = None
        self._density: Optional[np.ndarray] = None
        self._seismic: Optional[np.ndarray] = None

        self._ai: Optional[np.ndarray] = None
        self._rc: Optional[np.ndarray] = None
        self._synthetic: Optional[np.ndarray] = None
        self._wavelet: np.ndarray = generate_ricker_wavelet(30.0)[1]

        self._pixmap_cache: Optional[QPixmap] = None
        self._cache_dirty = True
        self._hover_pos: Optional[QPointF] = None

        # Track column widths
        self._track_widths = [80, 140, 110, 70, 100, 120, 90]

    def set_tie_data(
        self,
        depths: np.ndarray,
        twt: np.ndarray,
        sonic: np.ndarray,
        density: np.ndarray,
        seismic: np.ndarray,
        wavelet: Optional[np.ndarray] = None,
    ):
        """Bind tie dataset arrays and invalidate render cache."""
        self._depths = np.asarray(depths, dtype=np.float64)
        self._twt = np.asarray(twt, dtype=np.float64)
        self._sonic = np.asarray(sonic, dtype=np.float64)
        self._density = np.asarray(density, dtype=np.float64)
        self._seismic = np.asarray(seismic, dtype=np.float64)

        if wavelet is not None:
            self._wavelet = np.asarray(wavelet, dtype=np.float64)

        self._recalculate()
        self._cache_dirty = True
        self.update()

    def _recalculate(self):
        if self._sonic is None or self._density is None:
            return
        self._ai = compute_impedance(self._sonic, self._density)
        self._rc = compute_reflectivity(self._ai)
        self._synthetic = generate_synthetic_seismogram(self._sonic, self._density, self._wavelet)

    def set_wavelet(self, wavelet: np.ndarray):
        """Update wavelet and re-convolve synthetic."""
        self._wavelet = np.asarray(wavelet, dtype=np.float64)
        self._recalculate()
        self._cache_dirty = True
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._cache_dirty = True

    def mouseMoveEvent(self, event):
        self._hover_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._hover_pos = None
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if self._cache_dirty or self._pixmap_cache is None or self._pixmap_cache.size() != self.size():
            self._render_static_cache()

        # Blit static background layer
        if self._pixmap_cache:
            painter.drawPixmap(0, 0, self._pixmap_cache)

        # Draw dynamic hover crosshair
        if self._hover_pos and self._depths is not None and len(self._depths) > 0:
            self._draw_hover_overlay(painter)

    def _render_static_cache(self):
        self._pixmap_cache = QPixmap(self.size())
        self._pixmap_cache.fill(QColor(250, 249, 245))  # Azurite light cream

        p = QPainter(self._pixmap_cache)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        W, H = self.width(), self.height()
        header_h = 36.0
        content_h = max(10.0, H - header_h)

        # Draw headers & track column borders
        x = 0.0
        headers = ["Depth/TWT", "DT / RHOB", "AI", "RC", "Synthetic", "Seismic", "Correlation"]
        font = QFont("SansSerif", 9, QFont.Weight.Bold)
        p.setFont(font)

        for i, w in enumerate(self._track_widths):
            rect = QRectF(x, 0, w, header_h)
            p.setPen(QPen(QColor(229, 234, 241), 1))
            p.setBrush(QBrush(QColor(241, 244, 249)))
            p.drawRect(rect)

            p.setPen(QColor(31, 102, 212))
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, headers[i])

            p.setPen(QPen(QColor(229, 234, 241), 1))
            p.drawLine(int(x + w), 0, int(x + w), H)
            x += w

        p.end()
        self._cache_dirty = False

    def _draw_hover_overlay(self, painter: QPainter):
        if self._hover_pos is None:
            return
        y = self._hover_pos.y()
        painter.setPen(QPen(QColor(220, 38, 38), 1, Qt.PenStyle.DashLine))
        painter.drawLine(0, int(y), self.width(), int(y))
