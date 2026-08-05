# packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/base_item.py
"""Base draggable and resizable paper graphics item with selection feedback.

Resize model: when the item is selected, ``hit_handle`` maps an item-coord
position to one of the 8 handles (corners + edge midpoints). A handle drag
is tracked in **scene coordinates** (``_resize_scene_rect`` captured at
press) so repeated ``resize_to`` normalisation during the drag cannot
accumulate frame error. ``resize_to`` accepts a local rect with a possibly
non-zero origin (top/left drags) and normalises it to ``pos + (0,0,w,h)``;
subclasses carrying geometry beyond the plain rect (point lists, text wrap)
override :meth:`_remap_content`.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPen, QBrush, QPainter
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

MIN_ITEM_SIZE_MM = 2.0


class LayoutGraphicsItem(QGraphicsRectItem):
    """Base item for interactive paper elements supporting drag and resize handles."""

    handle_size = 4.0  # mm (scene units); was a paint() local

    def __init__(self, rect: QRectF, parent=None):
        super().__init__(rect, parent)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setPen(QPen(QColor("#1f66d4"), 1.0))
        self.setBrush(QBrush(QColor("#ffffff")))
        self._resize_handle: str | None = None
        self._resize_scene_rect = QRectF()

    # -- handles --------------------------------------------------------

    def _handle_points(self) -> dict[str, QPointF]:
        r = self.rect()
        return {
            "tl": r.topLeft(),
            "t": (r.topLeft() + r.topRight()) / 2,
            "tr": r.topRight(),
            "r": (r.topRight() + r.bottomRight()) / 2,
            "br": r.bottomRight(),
            "b": (r.bottomLeft() + r.bottomRight()) / 2,
            "bl": r.bottomLeft(),
            "l": (r.topLeft() + r.bottomLeft()) / 2,
        }

    def hit_handle(self, pos: QPointF) -> str | None:
        """Handle id under item-coord ``pos`` (selected items only)."""
        if not self.isSelected():
            return None
        tol = self.handle_size
        for name, p in self._handle_points().items():
            if abs(pos.x() - p.x()) <= tol and abs(pos.y() - p.y()) <= tol:
                return name
        return None

    # -- resize ---------------------------------------------------------

    def resize_to(self, new_local: QRectF) -> None:
        """Apply a resize given in item coordinates (origin may be non-zero).

        Normalises to ``pos + (0,0,w,h)``: the position shifts by the local
        origin, the rect becomes origin-zero. Subclass content hook runs
        first so it can read the old frame.
        """
        old = QRectF(self.rect())
        if (
            old.width() <= 0 or old.height() <= 0
            or new_local.width() <= 0 or new_local.height() <= 0
        ):
            return
        self._remap_content(old, new_local)
        self.setPos(self.pos() + new_local.topLeft())
        self.setRect(QRectF(0, 0, new_local.width(), new_local.height()))
        self.update()

    def _remap_content(self, old: QRectF, new_local: QRectF) -> None:
        """Subclass hook for content not described by the plain rect."""

    # -- mouse ----------------------------------------------------------

    def mousePressEvent(self, event) -> None:
        handle = self.hit_handle(event.pos())
        if handle is not None and event.button() == Qt.MouseButton.LeftButton:
            self._resize_handle = handle
            self._resize_scene_rect = self.mapToScene(self.rect()).boundingRect()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._resize_handle is None:
            super().mouseMoveEvent(event)
            return
        r = QRectF(self._resize_scene_rect)
        s = event.scenePos()
        h = self._resize_handle
        if "l" in h:
            r.setLeft(min(s.x(), r.right() - MIN_ITEM_SIZE_MM))
        if "r" in h:
            r.setRight(max(s.x(), r.left() + MIN_ITEM_SIZE_MM))
        if "t" in h:
            r.setTop(min(s.y(), r.bottom() - MIN_ITEM_SIZE_MM))
        if "b" in h:
            r.setBottom(max(s.y(), r.top() + MIN_ITEM_SIZE_MM))
        self.resize_to(self.mapFromScene(r).boundingRect())

    def mouseReleaseEvent(self, event) -> None:
        if self._resize_handle is not None:
            self._resize_handle = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # -- paint ----------------------------------------------------------

    def paint(self, painter: QPainter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            self._paint_selection_handles(painter)

    def _paint_selection_handles(self, painter: QPainter) -> None:
        painter.setPen(QPen(QColor("#1f66d4"), 1.5))
        painter.setBrush(QBrush(QColor("#ffffff")))
        hs = self.handle_size
        for p in self._handle_points().values():
            painter.drawRect(QRectF(p.x() - hs / 2, p.y() - hs / 2, hs, hs))
