from __future__ import annotations

import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

from .track_base import nice_depth_interval


class DepthRuler(QWidget):
    """Depth ruler widget showing depth labels and cursor depth indicator."""

    _TARGET_PIXEL_SPACING = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(50)
        self._depth_top = 0.0
        self._depth_bottom = 1000.0
        self._cursor_depth: float | None = None
        # Top insets that must be excluded from the depth mapping so ruler
        # labels align with the canvas content next to it: the well name
        # label above the canvas and the track header band inside the canvas.
        self._label_inset = 0.0
        self._header_inset = 0.0

    def set_depth_range(self, top: float, bottom: float):
        self._depth_top = top
        self._depth_bottom = bottom
        self.update()

    def set_geometry_insets(self, label_px: float = 0.0, header_px: float = 0.0):
        """Set the vertical insets (px) excluded from the depth-to-Y mapping.

        ``label_px`` is the height of the well-name label above the canvas,
        ``header_px`` the track header band height inside the canvas. Together
        they keep ruler ticks aligned with the canvas content, matching the
        ``_y_to_depth`` / ``depth_to_y`` transforms used by the canvases.
        """
        self._label_inset = float(label_px)
        self._header_inset = float(header_px)
        self.update()

    def set_cursor_depth(self, depth: float | None):
        self._cursor_depth = depth
        self.update()

    def _depth_to_y(self, depth: float) -> float:
        """Convert depth value to widget Y coordinate (canvas-aligned mapping)."""
        span = self._depth_bottom - self._depth_top
        if span <= 0:
            return 0.0
        ratio = (depth - self._depth_top) / span
        usable = self.height() - self._label_inset - self._header_inset
        if usable <= 0:
            return 0.0
        return self._label_inset + self._header_inset + ratio * usable

    def _compute_nice_intervals(self, top: float, bottom: float, height: int) -> float:
        """Compute a nice label interval for the given depth range and pixel height."""
        return nice_depth_interval(bottom - top, height, min_px=self._TARGET_PIXEL_SPACING)

    def paintEvent(self, event):
        if self._depth_bottom <= self._depth_top:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(self.rect(), QColor("#f8fafc"))

        # Left border
        painter.setPen(QPen(QColor("#cbd5e1"), 2))
        painter.drawLine(0, 0, 0, h)

        # Compute label interval
        interval = self._compute_nice_intervals(self._depth_top, self._depth_bottom, h)

        # Draw depth labels and tick marks
        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#64748b")))

        fm = QFontMetrics(font)
        start = math.ceil(self._depth_top / interval) * interval
        depth = start
        while depth <= self._depth_bottom:
            y = self._depth_to_y(depth)
            if 0 <= y <= h:
                # Tick mark (6px wide)
                painter.setPen(QPen(QColor("#94a3b8"), 1))
                painter.drawLine(0, int(y), 6, int(y))
                # Depth label
                painter.setPen(QPen(QColor("#64748b")))
                label = f"{depth:.0f}" if depth == int(depth) else f"{depth:.1f}"
                text_rect = QRectF(8, y - fm.height() / 2, w - 10, fm.height())
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, label)
            depth += interval

        # Cursor depth indicator
        if self._cursor_depth is not None:
            cy = self._depth_to_y(self._cursor_depth)
            if 0 <= cy <= h:
                # Highlight band
                band_h = 20
                band_top = max(0, cy - band_h / 2)
                band_rect = QRectF(0, band_top, w, band_h)
                painter.fillRect(band_rect, QColor(254, 242, 242))
                painter.setPen(QPen(QColor("#ef4444"), 1))
                painter.drawLine(0, int(band_top), w, int(band_top))
                painter.drawLine(0, int(band_top + band_h), w, int(band_top + band_h))
                # Depth label
                painter.setPen(QPen(QColor("#dc2626")))
                bold_font = QFont(font)
                bold_font.setBold(True)
                painter.setFont(bold_font)
                label = f"{self._cursor_depth:.0f}m" if self._cursor_depth == int(self._cursor_depth) else f"{self._cursor_depth:.1f}m"
                text_rect = QRectF(0, band_top + 2, w, band_h - 4)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.end()
