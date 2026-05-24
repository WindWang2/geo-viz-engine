from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF
from PySide6.QtWidgets import (
    QGraphicsObject, QStyleOptionGraphicsItem, QWidget,
    QMenu, QColorDialog,
)
from PySide6.QtGui import QAction

from .well_item import WellItem


class CorrelationBand(QGraphicsObject):
    """A correlation polygon between two WellItem objects.

    Auto-adapts its polygon geometry when either well is dragged.
    Selectable with highlight border, right-clickable for color change.
    """

    def __init__(self, source_well: WellItem, target_well: WellItem,
                 source_interval_id: str, target_interval_id: str,
                 color: str = "#f59e0b", is_manual: bool = False,
                 parent=None):
        super().__init__(parent)
        self._source_well = source_well
        self._target_well = target_well
        self._source_interval_id = source_interval_id
        self._target_interval_id = target_interval_id
        self._color = color
        self._is_manual = is_manual

        self._polygon = QPolygonF()
        self._bounding_rect = QRectF()

        self.setZValue(-1)  # Behind wells
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

        self._recompute_polygon()

    # --- Properties ---

    @property
    def source_well(self) -> WellItem:
        return self._source_well

    @property
    def target_well(self) -> WellItem:
        return self._target_well

    @property
    def source_interval_id(self) -> str:
        return self._source_interval_id

    @property
    def target_interval_id(self) -> str:
        return self._target_interval_id

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, hex_color: str):
        self._color = hex_color
        self.update()

    @property
    def is_manual(self) -> bool:
        return self._is_manual

    # --- Geometry ---

    def boundingRect(self) -> QRectF:
        return self._bounding_rect.adjusted(-2, -2, 2, 2)

    def _depth_id_parts(self, interval_id: str) -> tuple[float, float] | None:
        try:
            parts = interval_id.split("_")
            return float(parts[0]), float(parts[1])
        except (ValueError, IndexError):
            return None

    def update_geometry(self):
        self.prepareGeometryChange()
        self._recompute_polygon()
        self.update()

    def _recompute_polygon(self):
        src_parts = self._depth_id_parts(self._source_interval_id)
        tgt_parts = self._depth_id_parts(self._target_interval_id)
        if src_parts is None or tgt_parts is None:
            self._polygon = QPolygonF()
            self._bounding_rect = QRectF()
            return

        src_top, src_bot = src_parts
        tgt_top, tgt_bot = tgt_parts

        # Source right edge in scene coordinates
        src_pos = self._source_well.scenePos()
        sx = src_pos.x() + self._source_well.column_width

        # Target left edge
        tx = self._target_well.scenePos().x()

        # Y positions from depth mapping (source/target may have different headers)
        sy1 = src_pos.y() + self._source_well.depth_to_y(src_top)
        sy2 = src_pos.y() + self._source_well.depth_to_y(src_bot)
        ty1 = self._target_well.scenePos().y() + self._target_well.depth_to_y(tgt_top)
        ty2 = self._target_well.scenePos().y() + self._target_well.depth_to_y(tgt_bot)

        self._polygon = QPolygonF([
            QPointF(sx, sy1),
            QPointF(tx, ty1),
            QPointF(tx, ty2),
            QPointF(sx, sy2),
        ])
        self._bounding_rect = self._polygon.boundingRect()

    # --- Rendering ---

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None):
        if self._polygon.isEmpty():
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        color = QColor(self._color)
        color.setAlpha(100)
        painter.setPen(QPen(color.darker(130), 1))
        painter.setBrush(color)
        painter.drawPolygon(self._polygon)

        # Selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor("#3b82f6"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(self._polygon)

        painter.restore()

    # --- Interaction ---

    def shape(self):
        from PySide6.QtGui import QPainterPath
        path = QPainterPath()
        path.addPolygon(self._polygon)
        path.closeSubpath()
        return path

    def contextMenuEvent(self, event):
        menu = QMenu()
        color_action = menu.addAction("更改颜色...")
        sep = menu.addSeparator()
        delete_action = menu.addAction("删除条带")

        action = menu.exec(event.screenPos())
        if action == color_action:
            new_color = QColorDialog.getColor(QColor(self._color), None, "选择条带颜色")
            if new_color.isValid():
                self._color = new_color.name()
                self.update()
        elif action == delete_action:
            scene = self.scene()
            if scene:
                from .cross_well_scene import CrossWellScene
                if isinstance(scene, CrossWellScene) and self in scene._bands:
                    scene._bands.remove(self)
                scene.removeItem(self)
