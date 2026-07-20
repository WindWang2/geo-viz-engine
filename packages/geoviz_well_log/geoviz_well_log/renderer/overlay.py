from __future__ import annotations

import bisect
from PySide6.QtCore import QRectF, QPoint, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QCursor

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canvas import WellLogCanvas


class CrosshairOverlay:
    """Crosshair depth cursor overlay with semi-transparent info panel."""

    def __init__(self, canvas: WellLogCanvas):
        self._canvas = canvas
        self._cursor_x: float | None = None
        self._cursor_y: float | None = None

    @property
    def visible(self) -> bool:
        return self._cursor_y is not None

    def set_cursor_pos(self, x: float | None, y: float | None):
        self._cursor_x = x
        self._cursor_y = y

    def set_cursor_y(self, y: float | None):
        self._cursor_y = y

    def depth_at_y(self, y: float) -> float:
        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None or self._canvas.height() <= 0:
            return 0.0
        header_h = max((t.header_height for t in self._canvas.tracks), default=56)
        content_h = self._canvas.height() - header_h
        if content_h <= 0:
            return 0.0
        cy = y - header_h
        ratio = cy / content_h
        depth = track.depth_top + ratio * track.depth_span
        return max(track.depth_top, min(depth, track.depth_bottom))

    def _collect_values(self, depth: float) -> list[tuple[str, str]]:
        """Collect (label, value) pairs from all tracks at given depth."""
        rows: list[tuple[str, str]] = []
        for track in self._canvas.tracks:
            name = track.label
            from .curve_track import CurveTrack
            if isinstance(track, CurveTrack):
                for curve in track._curves:
                    depths = track._sorted_depths.get(curve.name, curve.depth)
                    values = track._sorted_values.get(curve.name, curve.values)
                    if len(depths) < 2:
                        continue
                    idx = bisect.bisect_left(depths, depth)
                    # Clamp to valid range
                    idx = max(0, min(idx, len(depths) - 1))
                    # Find bracketing indices for interpolation
                    if idx > 0 and depth < depths[idx]:
                        i0, i1 = idx - 1, idx
                    elif idx < len(depths) - 1 and depth > depths[idx]:
                        i0, i1 = idx, idx + 1
                    else:
                        i0, i1 = idx, idx
                    d0, d1 = depths[i0], depths[i1]
                    v0, v1 = values[i0], values[i1]
                    if d1 - d0 > 0:
                        interp = v0 + (depth - d0) / (d1 - d0) * (v1 - v0)
                    else:
                        interp = v0
                    rows.append((curve.name, f"{interp:.2f}"))
            else:
                from .interval_track import IntervalTrack
                from .lithology_track import LithologyTrack
                from .facies_track import FaciesTrack
                from .systems_tract import SystemsTractTrack
                if isinstance(track, LithologyTrack):
                    for iv in track._intervals:
                        if iv.top <= depth <= iv.bottom:
                            rows.append((name, iv.lithology))
                            break
                elif isinstance(track, FaciesTrack):
                    for attr in ("phase", "sub_phase", "micro_phase"):
                        for iv in getattr(track._facies_data, attr, []):
                            if iv.top <= depth <= iv.bottom:
                                rows.append((name, iv.name))
                                break
                elif isinstance(track, SystemsTractTrack):
                    for iv in track._intervals:
                        if iv.top <= depth <= iv.bottom:
                            rows.append((name, iv.name))
                            break
                elif isinstance(track, IntervalTrack):
                    for iv in track._intervals:
                        if iv.top <= depth <= iv.bottom:
                            rows.append((name, iv.name))
                            break
        return rows

    def paint_overlay(self, painter: QPainter, rect: QRectF):
        if self._cursor_y is None:
            return
        cursor_y = self._cursor_y
        if cursor_y < rect.top() or cursor_y > rect.bottom():
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dashed horizontal red cursor line
        pen = QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(rect.left()), int(cursor_y),
                         int(rect.right()), int(cursor_y))

        # Semi-transparent info panel
        depth = self.depth_at_y(cursor_y)
        rows = self._collect_values(depth)

        font = QFont("SansSerif", 9)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Build panel lines
        lines = [f"📍 深度: {depth:.2f} m"]
        for label, value in rows:
            lines.append(f"{label}: {value}")

        line_h = fm.height() + 4
        max_w = max(fm.horizontalAdvance(l) for l in lines) + 24
        panel_h = len(lines) * line_h + 12
        panel_w = max(160.0, float(max_w))

        # Position: follow mouse cursor inside canvas coordinates
        if self._cursor_x is not None:
            cursor_x = self._cursor_x
        else:
            cursor_x = float(self._canvas.mapFromGlobal(QCursor.pos()).x())

        px = cursor_x + 16
        py = cursor_y + 12

        # Keep panel within visible bounds
        if px + panel_w > rect.right():
            px = cursor_x - panel_w - 12
        if py + panel_h > rect.bottom():
            py = cursor_y - panel_h - 12
        px = max(rect.left() + 4, min(px, rect.right() - panel_w - 4))
        py = max(rect.top() + 4, min(py, rect.bottom() - panel_h - 4))

        panel_rect = QRectF(px, py, panel_w, panel_h)

        # Draw sleek dark slate panel background with crisp rounded corners
        painter.setPen(QPen(QColor(15, 23, 42, 180), 1))
        painter.setBrush(QBrush(QColor(15, 23, 42, 230)))
        painter.drawRoundedRect(panel_rect, 6, 6)

        # Title: Depth
        ty = py + 6
        painter.setFont(QFont("SansSerif", 9, QFont.Weight.Bold))
        painter.setPen(QColor("#38bdf8"))  # Cyan accent color for depth header
        depth_rect = QRectF(px + 10, ty, panel_w - 20, line_h)
        painter.drawText(depth_rect, Qt.AlignmentFlag.AlignVCenter, lines[0])

        # Content rows
        painter.setFont(font)
        painter.setPen(QColor("#f8fafc"))  # White text
        for i, line in enumerate(lines[1:], start=1):
            text_rect = QRectF(px + 10, ty + i * line_h, panel_w - 20, line_h)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, line)

        painter.restore()
