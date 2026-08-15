"""Formation-top marker overlay track for the QPainter (Legacy) backend.

WL-14 (#410): the workbench wraps well data in ``WellLogDataWithMarkers`` and
the native engine adapter consumes ``data.markers``, but ``build_qpainter_tracks``
had no consumer for them, so saved correlation tops silently disappeared on
the Legacy backend. ``MarkerTrack`` is a zero-width full-canvas overlay track:
``WellLogCanvas.paint_all`` paints it last across the whole canvas so marker
lines stay visible over every track without changing the layout.

Markers are duck-typed (``depth``/``reference_depth`` + ``label``/``name``),
mirroring ``geoviz_well_log.adapt_well_log_data``'s ``_append_markers``, so no
engine-side schema change is needed.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, QPointF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont

from .track_base import BaseTrack

# Deterministic palette, styled like the cross-well formation-top overlays.
_MARKER_COLORS = [
    "#0ea5e9", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6", "#14b8a6",
]


def marker_depth(marker) -> float | None:
    """Extract the marker depth (``depth`` or ``reference_depth``) or None."""
    raw = getattr(marker, "depth", None)
    if raw is None:
        raw = getattr(marker, "reference_depth", None)
    try:
        d = float(raw)
    except (TypeError, ValueError):
        return None
    return d if np.isfinite(d) else None


def marker_label(marker) -> str:
    """Extract the marker display label (``label`` or ``name``)."""
    raw = getattr(marker, "label", None)
    if raw is None:
        raw = getattr(marker, "name", None)
    return str(raw or "")


class MarkerTrack(BaseTrack):
    """Full-canvas overlay track drawing dashed formation-top marker lines."""

    _overlay_track = True

    def __init__(self, markers: list, parent=None):
        super().__init__(label="", width=0, header_height=0, parent=parent)
        self._markers: list[tuple[float, str]] = []
        for m in markers:
            d = marker_depth(m)
            if d is not None:
                self._markers.append((d, marker_label(m)))

    @property
    def markers(self) -> list[tuple[float, str]]:
        """Normalized (depth, label) pairs in source order."""
        return list(self._markers)

    def paint_content(self, painter: QPainter, rect: QRectF):
        if not self._markers or rect.height() <= 0 or self.depth_span <= 0:
            return
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        for i, (depth, label) in enumerate(self._markers):
            y = self._depth_to_y(depth, rect)
            if y < rect.top() or y > rect.bottom():
                continue
            color = QColor(_MARKER_COLORS[i % len(_MARKER_COLORS)])
            painter.setPen(QPen(color, 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            if label:
                painter.setPen(QPen(color, 1.0))
                painter.drawText(QPointF(rect.left() + 4, y - 3), label)
