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

        # Adaptive decimation: when more traces would be drawn than there are
        # visible columns, widen the trace step so at most one trace per pixel
        # column is emitted (keeps dense sections readable and cheap to draw).
        trace_step = self._trace_step
        if (n_traces + trace_step - 1) // trace_step > w:
            trace_step = max(trace_step, (n_traces + w - 1) // w)

        # Dynamic Gain: allow wiggles to occupy 2.0x their reserved space to naturally overlap
        wiggle_gain = x_scale * trace_step * 2.0

        # Pens / Brushes for professional appearance
        baseline_pen = QPen(QColor(230, 230, 230))
        baseline_pen.setWidthF(1.0)

        wiggle_pen = QPen(QColor(30, 30, 30))
        wiggle_pen.setWidthF(1.0)

        fill_brush = QBrush(QColor(0, 0, 0, 200)) # Strong, premium black VA fill

        # Shared per-sample vertical positions (identical for every trace).
        y_coords = np.arange(n_samples) * y_scale
        y_coords_list = y_coords.tolist()

        for t in range(0, n_traces, trace_step):
            centre_x = float(t * x_scale + (x_scale / 2.0))

            # Vectorized per-trace geometry (no per-sample Python loop).
            # ``v`` is upcast to float64 so the arithmetic below reproduces
            # the values the old Python loop produced with plain floats.
            v = (self._data[:, t] / amax).astype(np.float64)
            xs = centre_x + v * wiggle_gain
            pos = v >= 0.0

            # 1. Draw Baseline (QPointF overload: the plain float overload
            #    truncates fractional coordinates in PySide6)
            painter.setPen(baseline_pen)
            painter.drawLine(QPointF(centre_x, 0.0), QPointF(centre_x, float(h)))

            # 2. Positive fill lobes with zero-crossing interpolation points.
            #    All lobe coordinates are assembled in one numpy pass, then
            #    every lobe is emitted as its own polygon: merging them into
            #    a single polygon changes the anti-aliasing along the shared
            #    baseline, so lobes stay separate for bit-identical output.
            d = np.diff(pos.astype(np.int8))
            starts = np.flatnonzero(d == 1) + 1
            ends = np.flatnonzero(d == -1) + 1
            if pos[0]:
                starts = np.concatenate(([0], starts))
            if pos[-1]:
                ends = np.concatenate((ends, [n_samples]))
            if starts.size:
                m = starts.size
                # Interpolated baseline crossings (pos->neg and neg->pos).
                yc_in = np.empty(m)
                yc_out = np.empty(m)
                not_first = starts != 0
                not_last = ends != n_samples
                frac_in = -v[starts[not_first] - 1] / (
                    v[starts[not_first]] - v[starts[not_first] - 1]
                )
                yc_in[not_first] = y_coords[starts[not_first] - 1] + frac_in * (
                    y_coords[starts[not_first]] - y_coords[starts[not_first] - 1]
                )
                yc_in[~not_first] = y_coords[0]
                frac_out = v[ends[not_last] - 1] / (
                    v[ends[not_last] - 1] - v[ends[not_last]]
                )
                yc_out[not_last] = y_coords[ends[not_last] - 1] + frac_out * (
                    y_coords[ends[not_last]] - y_coords[ends[not_last] - 1]
                )
                yc_out[~not_last] = y_coords[n_samples - 1]

                # Concatenate every lobe as [baseline-in][curve points][baseline-out].
                xs_lobe = xs[pos]
                ys_lobe = y_coords[pos]
                run_len = ends - starts
                cum = np.concatenate(([0], np.cumsum(run_len)))
                lobe_start = cum[:-1] + 2 * np.arange(m)
                lobe_end = cum[1:] + 2 * np.arange(m) + 1
                n_pts = xs_lobe.size + 2 * m
                all_x = np.empty(n_pts)
                all_y = np.empty(n_pts)
                all_x[lobe_start] = centre_x
                all_x[lobe_end] = centre_x
                all_y[lobe_start] = yc_in
                all_y[lobe_end] = yc_out
                curve_mask = np.ones(n_pts, dtype=bool)
                curve_mask[lobe_start] = False
                curve_mask[lobe_end] = False
                all_x[curve_mask] = xs_lobe
                all_y[curve_mask] = ys_lobe

                # 3. Render filled lobes
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(fill_brush)
                lx = all_x.tolist()
                ly = all_y.tolist()
                for k in range(m):
                    s = int(lobe_start[k])
                    e = int(lobe_end[k]) + 1
                    painter.drawPolygon(
                        QPolygonF([QPointF(a, b) for a, b in zip(lx[s:e], ly[s:e])])
                    )

            # 4. Render continuous line. Zero-crossing points are collinear
            #    with their connecting segments, so they are intentionally
            #    omitted here to keep rasterization bit-identical to the
            #    previous implementation.
            painter.setPen(wiggle_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolyline(
                QPolygonF([QPointF(a, b) for a, b in zip(xs.tolist(), y_coords_list)])
            )

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
