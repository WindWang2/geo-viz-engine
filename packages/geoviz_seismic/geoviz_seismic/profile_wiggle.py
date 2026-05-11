from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
    QPolygonF,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

class ProfileWiggle(QWidget):
    """Wiggle-trace profile renderer using high-fidelity Pure QPainter with zero-crossing interpolation."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: np.ndarray | None = None
        self._trace_step: int = 1
        self._cached_pixmap: QPixmap | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_data(self) -> bool:
        """Return ``True`` after :meth:`render` has been called."""
        return self._data is not None

    def trace_step(self) -> int:
        """Return the current trace subsampling step."""
        return self._trace_step

    def render(self, data: np.ndarray, trace_step: int = 1) -> None:
        """Render wiggle traces from 2-D seismic data.

        Parameters
        ----------
        data:
            2-D ``float32`` array of shape ``(n_samples, n_traces)``.
        trace_step:
            Draw every *trace_step*-th trace (1 = all traces).
        """
        self._data = data.astype(np.float32, copy=False)
        self._trace_step = trace_step
        self._cached_pixmap = None  # invalidate cached drawing

        self.setMinimumSize(self._data.shape[1], self._data.shape[0])
        self.update()

    def set_trace_step(self, step: int) -> None:
        """Update trace subsampling and re-render if data exists."""
        if step < 1:
            raise ValueError("trace_step must be >= 1")
        self._trace_step = step
        if self._data is not None:
            self.render(self._data, trace_step=step)

    # ------------------------------------------------------------------
    # QPainter rendering pipeline
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._data is None:
            super().paintEvent(event)
            return

        if self._cached_pixmap is not None:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._cached_pixmap)
            painter.end()
            return

        n_samples, n_traces = self._data.shape
        w = self.width()
        h = self.height()

        if w < 2 or h < 2:
            return

        pixmap = QPixmap(w, h)
        pixmap.fill(QColor("#ffffff"))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        amax = np.nanmax(np.abs(self._data))
        if amax == 0:
            amax = 1.0

        x_scale = w / max(n_traces, 1)
        y_scale = h / max(n_samples - 1, 1)
        
        # Dynamic Gain: allow wiggles to occupy 2.0x their reserved space to naturally overlap
        wiggle_gain = x_scale * self._trace_step * 2.0

        # Pens / Brushes for professional appearance
        baseline_pen = QPen(QColor(230, 230, 230))
        baseline_pen.setWidthF(1.0)
        
        wiggle_pen = QPen(QColor(30, 30, 30))
        wiggle_pen.setWidthF(1.0)
        
        fill_brush = QBrush(QColor(0, 0, 0, 200)) # Strong, premium black VA fill

        y_coords = (np.arange(n_samples) * y_scale).tolist()

        for t in range(0, n_traces, self._trace_step):
            trace_raw = self._data[:, t]
            trace = (trace_raw / amax).tolist()
            centre_x = float(t * x_scale + (x_scale / 2.0))

            # 1. Draw Baseline
            painter.setPen(baseline_pen)
            painter.drawLine(QPointF(centre_x, 0), QPointF(centre_x, float(h)))

            # 2. Construct Line Path and Positive Fill Polygons with zero-crossing injection
            line_path = QPolygonF()
            polys = []
            current_poly = []

            for i in range(n_samples - 1):
                v1, v2 = trace[i], trace[i+1]
                y1, y2 = y_coords[i], y_coords[i+1]
                x1 = centre_x + v1 * wiggle_gain
                
                line_path.append(QPointF(x1, y1))

                # Fill logic
                if v1 >= 0:
                    if not current_poly:
                        current_poly.append(QPointF(centre_x, y1))
                    current_poly.append(QPointF(x1, y1))
                    
                    if v2 < 0:
                        # Crossed pos -> neg
                        frac = v1 / (v1 - v2)
                        yc = y1 + frac * (y2 - y1)
                        current_poly.append(QPointF(centre_x, yc))
                        polys.append(QPolygonF(current_poly))
                        current_poly = []
                else:
                    if v2 > 0:
                        # Crossed neg -> pos
                        frac = -v1 / (v2 - v1)
                        yc = y1 + frac * (y2 - y1)
                        current_poly = [QPointF(centre_x, yc)]

            # Last point
            v_last = trace[-1]
            y_last = y_coords[-1]
            x_last = centre_x + v_last * wiggle_gain
            line_path.append(QPointF(x_last, y_last))
            
            if v_last >= 0:
                if not current_poly:
                    current_poly.append(QPointF(centre_x, y_last))
                current_poly.append(QPointF(x_last, y_last))
                current_poly.append(QPointF(centre_x, y_last))
                polys.append(QPolygonF(current_poly))
            elif current_poly:
                current_poly.append(QPointF(centre_x, y_last))
                polys.append(QPolygonF(current_poly))

            # 3. Render filled lobes
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill_brush)
            for poly in polys:
                painter.drawPolygon(poly)

            # 4. Render continuous line
            painter.setPen(wiggle_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(line_path)

        painter.end()
        self._cached_pixmap = pixmap

        # Composite finished rendering
        target_painter = QPainter(self)
        target_painter.drawPixmap(0, 0, pixmap)
        target_painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._cached_pixmap = None
        self.update()
