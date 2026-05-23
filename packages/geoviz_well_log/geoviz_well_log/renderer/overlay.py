from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canvas import WellLogCanvas


class CrosshairOverlay:
    """Crosshair depth cursor overlay for WellLogCanvas.

    Not a QWidget -- renders via paint_overlay() called from canvas paintEvent.
    """

    def __init__(self, canvas: WellLogCanvas):
        self._canvas = canvas
        self._cursor_y: float | None = None

    def set_cursor_y(self, y: float | None):
        """Set cursor y-position (pixels) or None to hide."""
        self._cursor_y = y

    def depth_at_y(self, y: float) -> float:
        """Convert pixel y-coordinate to depth value."""
        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None or self._canvas.height() <= 0:
            return 0.0
        ratio = y / self._canvas.height()
        depth = track.depth_top + ratio * track.depth_span
        return max(track.depth_top, min(depth, track.depth_bottom))

    def paint_overlay(self, painter: QPainter, rect: QRectF):
        """Draw crosshair line and depth tooltip."""
        if self._cursor_y is None:
            return
        if self._cursor_y < rect.top() or self._cursor_y > rect.bottom():
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dashed horizontal line
        pen = QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(rect.left()), int(self._cursor_y),
                         int(rect.right()), int(self._cursor_y))

        # Depth tooltip
        depth = self.depth_at_y(self._cursor_y)
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        label = f"{depth:.1f} m"
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(label) + 8
        text_height = fm.height() + 4

        tooltip_x = rect.right() - text_width - 4
        tooltip_y = self._cursor_y - text_height - 2
        if tooltip_y < rect.top():
            tooltip_y = self._cursor_y + 4

        tooltip_rect = QRectF(tooltip_x, tooltip_y, text_width, text_height)
        painter.fillRect(tooltip_rect, QColor("#fef2f2"))
        painter.setPen(QPen(QColor("#ef4444"), 0.5))
        painter.drawRect(tooltip_rect)
        painter.setPen(QColor("#dc2626"))
        painter.drawText(tooltip_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.restore()
