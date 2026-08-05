"""Points-kind free graphics: FreeArrowItem, FreePolygonItem, FreehandItem.

Geometry stored as local points + ``pos = bbox.topLeft``; ``to_record``
emits paper-absolute mm points. Resize applies a bounding-box affine map
via :meth:`_remap_content` (spec §3.2): ``p' = p * (new/old)``.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QPolygonF

from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem


class _PointsItem(FreeGraphicsItem):
    """Shared backbone for arrow / polygon / freehand."""

    def __init__(self, abs_points: list[tuple[float, float]], parent=None) -> None:
        xs = [p[0] for p in abs_points]
        ys = [p[1] for p in abs_points]
        x0, y0 = min(xs), min(ys)
        w = max(xs) - x0
        h = max(ys) - y0
        super().__init__(QRectF(0, 0, w, h), parent)
        self.setPos(x0, y0)
        self._local_points = [QPointF(px - x0, py - y0) for px, py in abs_points]

    # -- geometry helpers ----------------------------------------------

    def _abs_points(self) -> list[list[float]]:
        p = self.pos()
        return [[pt.x() + p.x(), pt.y() + p.y()] for pt in self._local_points]

    def geometry_record(self) -> dict:
        return {"points": self._abs_points()}

    def _remap_content(self, old: QRectF, new_local: QRectF) -> None:
        if old.width() <= 0 or old.height() <= 0:
            return
        sx = new_local.width() / old.width()
        sy = new_local.height() / old.height()
        self._local_points = [
            QPointF(pt.x() * sx, pt.y() * sy) for pt in self._local_points
        ]

    @classmethod
    def _set_points_from_record(cls, item: "_PointsItem", rec: dict) -> None:
        """Re-init local points from an already-parsed record."""
        pts = rec["geometry"]["points"]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, y0 = min(xs), min(ys)
        item.setPos(x0, y0)
        item._local_points = [QPointF(px - x0, py - y0) for px, py in pts]
        item.setRect(0, 0, max(xs) - x0, max(ys) - y0)


class FreeArrowItem(_PointsItem):
    kind = "arrow"

    def __init__(self, abs_points: list[tuple[float, float]], parent=None) -> None:
        super().__init__(abs_points, parent)
        self.head_mm = 3.0

    def paint_content(self, painter) -> None:
        painter.setPen(self.stroke_pen())
        poly = QPolygonF(self._local_points)
        painter.drawPolyline(poly)
        # Arrowhead on the last segment.
        if len(self._local_points) >= 2:
            p1 = self._local_points[-2]
            p2 = self._local_points[-1]
            self._draw_arrowhead(painter, p1, p2)

    def _draw_arrowhead(self, painter, p1: QPointF, p2: QPointF) -> None:
        dx = p2.x() - p1.x()
        dy = p2.y() - p1.y()
        length = math.hypot(dx, dy)
        if length < 0.001:
            return
        ux, uy = dx / length, dy / length
        head = self.head_mm
        # Two barbs perpendicular to the direction, `head` mm back from tip.
        bx, by = p2.x() - ux * head, p2.y() - uy * head
        px, py = -uy * head * 0.4, ux * head * 0.4
        painter.setBrush(__import__("PySide6.QtGui", fromlist=["QBrush"]).QBrush(
            __import__("PySide6.QtGui", fromlist=["QColor"]).QColor(self.stroke)
        ))
        arrow = QPolygonF([p2, QPointF(bx + px, by + py), QPointF(bx - px, by - py)])
        painter.drawPolygon(arrow)

    def props_record(self) -> dict:
        return {"head_mm": self.head_mm}

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreeArrowItem":
        pts = [tuple(p) for p in rec["geometry"]["points"]]
        item = cls(pts)
        item.head_mm = rec["props"]["head_mm"]
        item._init_from_normalized(rec)
        return item


class FreePolygonItem(_PointsItem):
    kind = "polygon"

    def paint_content(self, painter) -> None:
        painter.setPen(self.stroke_pen())
        painter.setBrush(self.fill_brush())
        painter.drawPolygon(QPolygonF(self._local_points))

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreePolygonItem":
        pts = [tuple(p) for p in rec["geometry"]["points"]]
        item = cls(pts)
        item._init_from_normalized(rec)
        return item


class FreehandItem(_PointsItem):
    kind = "freehand"

    def paint_content(self, painter) -> None:
        painter.setPen(self.stroke_pen())
        painter.drawPolyline(QPolygonF(self._local_points))

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreehandItem":
        pts = [tuple(p) for p in rec["geometry"]["points"]]
        item = cls(pts)
        item._init_from_normalized(rec)
        return item
