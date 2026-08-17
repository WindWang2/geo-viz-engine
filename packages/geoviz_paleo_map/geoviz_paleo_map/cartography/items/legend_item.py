# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/legend_item.py
"""Multi-column legend box graphics item."""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPen, QPainter
from .base_item import LayoutGraphicsItem

class LegendGraphicsItem(LayoutGraphicsItem):
    """Interactive multi-column legend graphics item."""

    EMPTY_PLACEHOLDER = "（图例待配置）"
    _TITLE_H = 20.0
    _ROW_H = 14.0
    _PAD = 6.0

    def __init__(
        self,
        rect: QRectF = QRectF(0, 0, 90, 60),
        title: str = "图例 (Legend)",
        items: list[tuple[str, str]] | None = None, # list of (label, color_hex)
        columns: int = 2,
        parent=None,
    ):
        super().__init__(rect, parent)
        self.title = title
        self.items = list(items) if items else []
        self.columns = max(1, columns)
        self._fit_height_to_items()

    def paint(self, painter: QPainter, option, widget=None):
        painter.save()
        r = self.rect()
        
        # Background & border
        painter.setPen(QPen(QColor("#1a2433"), 1.0))
        painter.fillRect(r, QColor(255, 255, 255, 240))
        painter.drawRect(r)

        # Title
        font = QFont("SimSun", 9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(QRectF(r.left() + 4, r.top() + 4, r.width() - 8, 14),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.title)

        # Draw items in grid
        font.setPixelSize(8)
        font.setBold(False)
        painter.setFont(font)

        col_w = (r.width() - 8) / self.columns
        row_h = self._ROW_H
        start_y = r.top() + self._TITLE_H

        if not self.items:
            painter.drawText(
                QRectF(r.left() + 4, start_y, r.width() - 8, row_h),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                self.EMPTY_PLACEHOLDER,
            )
            painter.restore()
            super().paint(painter, option, widget)
            return

        for idx, (label, color_str) in enumerate(self.items):
            col = idx % self.columns
            row = idx // self.columns
            x = r.left() + 4 + col * col_w
            y = start_y + row * row_h

            if y + row_h > r.bottom():
                break

            # Swatch
            swatch_rect = QRectF(x, y + 3, 12, 8)
            painter.fillRect(swatch_rect, QColor(color_str))
            painter.setPen(QPen(QColor("#000000"), 0.5))
            painter.drawRect(swatch_rect)

            # Text
            painter.setPen(QPen(QColor("#1a2433"), 1.0))
            painter.drawText(QRectF(x + 16, y, col_w - 18, row_h),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, label)

        painter.restore()
        super().paint(painter, option, widget)

    def set_items(self, items: list[tuple[str, str]]) -> None:
        self.items = list(items)
        self._fit_height_to_items()
        self.update()

    def truncated_count(self) -> int:
        """How many entries would not fit the current rect."""
        if not self.items:
            return 0
        r = self.rect()
        rows_fit = max(0, int((r.height() - self._TITLE_H - 2) // self._ROW_H))
        return max(0, len(self.items) - rows_fit * self.columns)

    def _content_height(self) -> float:
        if not self.items:
            return self._TITLE_H + self._ROW_H + self._PAD
        rows = math.ceil(len(self.items) / self.columns)
        return self._TITLE_H + rows * self._ROW_H + self._PAD

    def _fit_height_to_items(self) -> None:
        needed = self._content_height()
        r = QRectF(self.rect())
        if r.height() < needed:
            r.setHeight(needed)
            self.setRect(r)
