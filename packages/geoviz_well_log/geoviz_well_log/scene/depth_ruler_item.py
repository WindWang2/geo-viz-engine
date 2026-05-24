from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget


class DepthRulerItem(QGraphicsObject):
    """Shared depth ruler rendered as a QGraphicsObject.

    Renders depth labels with adaptive tick spacing.
    Positioned at the left side of the scene.
    """

    _NICE_NUMBERS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    _TARGET_PIXEL_SPACING = 60
    _WIDTH = 50

    def __init__(self, height: float = 800, parent=None):
        super().__init__(parent)
        self._depth_top = 0.0
        self._depth_bottom = 1000.0
        self._height = height
        self._cursor_depth: float | None = None
        self.setZValue(100)  # Above wells

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self._WIDTH, self._height)

    def set_depth_range(self, top: float, bottom: float):
        self._depth_top = top
        self._depth_bottom = bottom
        self.update()

    def set_height(self, height: float):
        self.prepareGeometryChange()
        self._height = height
        self.update()

    def set_cursor_depth(self, depth: float | None):
        self._cursor_depth = depth
        self.update()

    def depth_to_y(self, depth: float) -> float:
        span = self._depth_bottom - self._depth_top
        if span <= 0:
            return 0.0
        ratio = (depth - self._depth_top) / span
        return ratio * self._height

    def _compute_nice_intervals(self, top: float, bottom: float, height: float) -> float:
        span = bottom - top
        if span <= 0 or height <= 0:
            return 1.0
        raw = (span / height) * self._TARGET_PIXEL_SPACING
        exp = math.floor(math.log10(raw)) if raw > 0 else 0
        base = 10 ** exp
        for n in self._NICE_NUMBERS:
            candidate = n * base
            if candidate >= raw:
                return candidate
        return self._NICE_NUMBERS[-1] * base

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None):
        if self._depth_bottom <= self._depth_top:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self._WIDTH
        h = self._height

        # Background
        painter.fillRect(QRectF(0, 0, w, h), QColor("#f8fafc"))

        # Right border
        painter.setPen(QPen(QColor("#cbd5e1"), 2))
        painter.drawLine(int(w), 0, int(w), int(h))

        # Compute label interval
        interval = self._compute_nice_intervals(self._depth_top, self._depth_bottom, h)

        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        fm = QFontMetrics(font)

        start = math.ceil(self._depth_top / interval) * interval
        depth = start
        while depth <= self._depth_bottom:
            y = self.depth_to_y(depth)
            if 0 <= y <= h:
                # Tick mark
                painter.setPen(QPen(QColor("#94a3b8"), 1))
                painter.drawLine(int(w - 6), int(y), int(w), int(y))
                # Label
                painter.setPen(QPen(QColor("#64748b")))
                label = f"{depth:.0f}" if depth == int(depth) else f"{depth:.1f}"
                text_rect = QRectF(2, y - fm.height() / 2, w - 10, fm.height())
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, label)
            depth += interval

        # Cursor depth indicator
        if self._cursor_depth is not None:
            cy = self.depth_to_y(self._cursor_depth)
            if 0 <= cy <= h:
                band_h = 20
                band_top = max(0, cy - band_h / 2)
                painter.fillRect(QRectF(0, band_top, w, band_h), QColor(254, 242, 242))
                painter.setPen(QPen(QColor("#ef4444"), 1))
                painter.drawLine(0, int(band_top), int(w), int(band_top))
                painter.drawLine(0, int(band_top + band_h), int(w), int(band_top + band_h))
                painter.setPen(QColor("#dc2626"))
                bold_font = QFont(font)
                bold_font.setBold(True)
                painter.setFont(bold_font)
                label = f"{self._cursor_depth:.0f}m" if self._cursor_depth == int(self._cursor_depth) else f"{self._cursor_depth:.1f}m"
                text_rect = QRectF(0, band_top + 2, w, band_h - 4)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.restore()
