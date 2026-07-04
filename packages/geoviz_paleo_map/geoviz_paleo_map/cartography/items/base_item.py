# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/base_item.py
"""Base draggable and resizable paper graphics item with selection feedback."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

class LayoutGraphicsItem(QGraphicsRectItem):
    """Base item for interactive paper elements supporting drag and resize handles."""

    def __init__(self, rect: QRectF, parent=None):
        super().__init__(rect, parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setPen(QPen(QColor("#1f66d4"), 1.0))
        self.setBrush(QBrush(QColor("#ffffff")))

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            # Draw 8 selection handles
            painter.setPen(QPen(QColor("#1f66d4"), 1.5))
            painter.setBrush(QBrush(QColor("#ffffff")))
            r = self.rect()
            handle_size = 4.0
            
            pts = [
                r.topLeft(), r.topRight(), r.bottomLeft(), r.bottomRight(),
                (r.topLeft() + r.topRight()) / 2,
                (r.bottomLeft() + r.bottomRight()) / 2,
                (r.topLeft() + r.bottomLeft()) / 2,
                (r.topRight() + r.bottomRight()) / 2
            ]
            for p in pts:
                painter.drawRect(QRectF(p.x() - handle_size/2, p.y() - handle_size/2, handle_size, handle_size))
