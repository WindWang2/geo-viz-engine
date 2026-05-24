from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsObject, QStyleOptionGraphicsItem, QWidget,
    QMenu, QInputDialog, QColorDialog,
)


class AnnotationItem(QGraphicsObject):
    """A text annotation item on the cross-well scene.

    Draggable, with context menu for edit/color/delete.
    """

    annotation_changed = Signal()

    def __init__(self, text: str, x: float, y: float,
                 color: str = "#1a202c", parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color
        self._font = QFont("Sans", 11)

        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsMovable, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(50)

    @property
    def text(self) -> str:
        return self._text

    @property
    def color(self) -> str:
        return self._color

    def boundingRect(self) -> QRectF:
        fm = QFontMetrics(self._font)
        text_w = fm.horizontalAdvance(self._text) + 12
        text_h = fm.height() + 8
        return QRectF(-5, -text_h - 5, text_w + 10, text_h + 15)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem,
              widget: QWidget | None = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        fm = QFontMetrics(self._font)
        text_w = fm.horizontalAdvance(self._text) + 8
        text_h = fm.height() + 4

        color = QColor(self._color)

        # Background rectangle
        bg = QRectF(-3, -text_h + 2, text_w, text_h)
        painter.fillRect(bg, QColor(255, 255, 255, 220))
        painter.setPen(QPen(color, 1))
        painter.drawRect(bg)

        # Text
        painter.setFont(self._font)
        painter.setPen(color)
        painter.drawText(1, 0, self._text)

        # Small triangle pointer at bottom
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        pointer = QPolygonF([
            QPointF(-3, 2),
            QPointF(3, 2),
            QPointF(0, 7),
        ])
        painter.drawPolygon(pointer)

        # Selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor("#3b82f6"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.boundingRect().adjusted(-2, -2, 2, 2))

        painter.restore()

    def contextMenuEvent(self, event):
        menu = QMenu()
        edit_action = menu.addAction("编辑文字...")
        color_action = menu.addAction("更改颜色...")
        menu.addSeparator()
        delete_action = menu.addAction("删除标注")

        action = menu.exec(event.screenPos())
        if action == edit_action:
            new_text, ok = QInputDialog.getText(
                None, "编辑标注", "标注文字:", text=self._text)
            if ok and new_text.strip():
                self._text = new_text.strip()
                self.prepareGeometryChange()
                self.update()
                self.annotation_changed.emit()
        elif action == color_action:
            new_color = QColorDialog.getColor(
                QColor(self._color), None, "选择标注颜色")
            if new_color.isValid():
                self._color = new_color.name()
                self.update()
        elif action == delete_action:
            scene = self.scene()
            if scene:
                scene.removeItem(self)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
        self.annotation_changed.emit()
