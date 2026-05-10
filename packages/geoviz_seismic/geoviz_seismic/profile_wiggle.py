from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import (
    QBrush,
    QColor,
    QPainter,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)

# Optional VisPy import -- graceful fallback to QPainter when unavailable.
try:
    import vispy.app

    vispy.app.use_app("pyside6")
    from vispy.scene import SceneCanvas

    _HAS_VISPY = True
except ImportError:
    _HAS_VISPY = False


class ProfileWiggle(QWidget):
    """Wiggle-trace profile renderer.

    When VisPy is available the traces are drawn on a GPU-accelerated
    :class:`vispy.scene.SceneCanvas`.  Otherwise a pure QPainter fallback
    is used (with a one-time info-level log message).
    """

    _fallback_warned = False

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._data: np.ndarray | None = None
        self._trace_step: int = 1
        self._vispy_canvas: SceneCanvas | None = None
        self._vispy_view = None

        if _HAS_VISPY:
            self._init_vispy()
        else:
            if not ProfileWiggle._fallback_warned:
                logger.info(
                    "VisPy not available. Wiggle using QPainter fallback. "
                    "For GPU acceleration: pip install geoviz-seismic[wiggle]"
                )
                ProfileWiggle._fallback_warned = True

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

        if _HAS_VISPY and self._vispy_view is not None:
            self._render_vispy()
        else:
            self.setMinimumSize(
                self._data.shape[1],
                self._data.shape[0],
            )
            self.update()

    def set_trace_step(self, step: int) -> None:
        """Update trace subsampling and re-render if data exists."""
        if step < 1:
            raise ValueError("trace_step must be >= 1")
        self._trace_step = step
        if self._data is not None:
            self.render(self._data, trace_step=step)

    # ------------------------------------------------------------------
    # VisPy backend
    # ------------------------------------------------------------------

    def _init_vispy(self) -> None:
        self._vispy_canvas = SceneCanvas(keys="interactive", parent=self)
        self._vispy_view = self._vispy_canvas.central_widget.add_view()

    def _render_vispy(self) -> None:
        """Rebuild the VisPy scene with current data and trace step."""
        # Remove old visuals
        self._vispy_view.camera = "panzoom"
        while self._vispy_view.children:
            self._vispy_view.children[0].parent = None

        from vispy.scene import LineVisual

        n_samples, n_traces = self._data.shape
        # Normalise amplitudes to a fixed pixel width.
        amax = np.nanmax(np.abs(self._data))
        if amax == 0:
            amax = 1.0
        scale = 0.4  # fraction of trace spacing

        for t in range(0, n_traces, self._trace_step):
            trace = self._data[:, t] / amax * scale
            x = np.full(n_samples, t, dtype=np.float32)
            y = np.arange(n_samples, dtype=np.float32) + trace * self._trace_step
            pos = np.column_stack([x, y]).astype(np.float32)
            LineVisual(pos=pos, parent=self._vispy_view.scene, color="black")

        self._vispy_canvas.draw()

    # ------------------------------------------------------------------
    # QPainter fallback
    # ------------------------------------------------------------------

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._data is None or _HAS_VISPY:
            super().paintEvent(event)
            return

        n_samples, n_traces = self._data.shape
        w = max(self.width(), n_traces)
        h = max(self.height(), n_samples)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        amax = np.nanmax(np.abs(self._data))
        if amax == 0:
            amax = 1.0

        x_scale = w / max(n_traces - 1, 1)
        y_scale = h / max(n_samples - 1, 1)
        wiggle_width = x_scale * self._trace_step * 0.4

        pen = QPen(QColor("black"))
        pen.setWidthF(1.0)
        painter.setPen(pen)
        fill_brush = QBrush(QColor(0, 0, 0, 40))
        neg_brush = QBrush(QColor(255, 255, 255, 0))

        for t in range(0, n_traces, self._trace_step):
            trace = self._data[:, t]
            centre_x = t * x_scale

            polygon = QPolygonF()
            polygon.append(QPointF(centre_x, 0))

            for s in range(n_samples):
                dx = (trace[s] / amax) * wiggle_width
                px = centre_x + dx
                py = s * y_scale
                polygon.append(QPointF(px, py))

            polygon.append(QPointF(centre_x, h - 1))

            # Fill positive excursions only.
            painter.setBrush(fill_brush)
            painter.drawPolygon(polygon)

            # Draw the wiggle line on top.
            painter.setBrush(neg_brush)
            line_poly = QPolygonF()
            for s in range(n_samples):
                dx = (trace[s] / amax) * wiggle_width
                line_poly.append(QPointF(centre_x + dx, s * y_scale))
            painter.drawPolyline(line_poly)

        painter.end()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if _HAS_VISPY and self._vispy_canvas is not None:
            self._vispy_canvas.resize(event.size().width(), event.size().height())
