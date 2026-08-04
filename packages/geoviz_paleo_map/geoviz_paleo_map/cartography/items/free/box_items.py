"""Box-kind free graphics: FreeRectItem, FreeEllipseItem."""

from __future__ import annotations

from PySide6.QtCore import QRectF

from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem


class FreeRectItem(FreeGraphicsItem):
    kind = "rect"

    def __init__(self, rect_scene: QRectF, parent=None) -> None:
        super().__init__(QRectF(0, 0, rect_scene.width(), rect_scene.height()), parent)
        self.setPos(rect_scene.topLeft())

    def paint_content(self, painter) -> None:
        painter.setPen(self.stroke_pen())
        painter.setBrush(self.fill_brush())
        painter.drawRect(self.rect())

    def geometry_record(self) -> dict:
        return self.frame_geometry_record()

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreeRectItem":
        g = rec["geometry"]
        item = cls(QRectF(g["x"], g["y"], g["w"], g["h"]))
        item._init_from_normalized(rec)
        return item


class FreeEllipseItem(FreeGraphicsItem):
    kind = "ellipse"

    def __init__(self, rect_scene: QRectF, parent=None) -> None:
        super().__init__(QRectF(0, 0, rect_scene.width(), rect_scene.height()), parent)
        self.setPos(rect_scene.topLeft())

    def paint_content(self, painter) -> None:
        painter.setPen(self.stroke_pen())
        painter.setBrush(self.fill_brush())
        painter.drawEllipse(self.rect())

    def geometry_record(self) -> dict:
        return self.frame_geometry_record()

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreeEllipseItem":
        g = rec["geometry"]
        item = cls(QRectF(g["x"], g["y"], g["w"], g["h"]))
        item._init_from_normalized(rec)
        return item
