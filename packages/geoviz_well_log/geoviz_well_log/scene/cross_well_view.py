from __future__ import annotations

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QPainter, QWheelEvent, QMouseEvent, QTransform
from PySide6.QtWidgets import QGraphicsView, QWidget

from .cross_well_scene import CrossWellScene


class CrossWellView(QGraphicsView):
    """QGraphicsView with unified zoom/pan for the cross-well canvas.

    - Wheel: zoom view transform (all items scale uniformly)
    - Middle-drag / Ctrl+left-drag: pan view
    - Double-click: reset view to fit
    """

    def __init__(self, scene: CrossWellScene, parent: QWidget | None = None):
        super().__init__(scene, parent)
        self._scene = scene
        self._panning = False
        self._pan_start = QPointF()
        self._zoom = 1.0

        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setStyleSheet("QGraphicsView { background: #ffffff; border: none; }")

    def wheelEvent(self, event: QWheelEvent):
        # Zoom in/out
        factor = 1.15
        if event.angleDelta().y() > 0:
            self._zoom *= factor
        else:
            self._zoom /= factor
        self._zoom = max(0.1, min(5.0, self._zoom))
        self.setTransform(QTransform().scale(self._zoom, self._zoom))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if (event.button() == Qt.MouseButton.MiddleButton
                or (event.button() == Qt.MouseButton.LeftButton
                    and event.modifiers() & Qt.KeyboardModifier.ControlModifier)):
            self._panning = True
            self._pan_start = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._panning:
            delta = event.position() - self._pan_start
            self._pan_start = event.position()
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - int(delta.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - int(delta.y())
            )
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        self.fit_scene()
        event.accept()

    def fit_scene(self):
        rect = self._scene.itemsBoundingRect().adjusted(-20, -40, 60, 40)
        if not rect.isEmpty():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            # Recalculate zoom from the transform
            transform = self.transform()
            self._zoom = transform.m11()
