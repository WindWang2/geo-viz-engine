"""NorthArrowItem + ScaleBarItem — paper-fixed cartographic symbols.

Adapted from ``geoviz_paleo_map.layers.north_arrow`` and ``scale_bar``,
but drawn at fixed mm dimensions on the paper instead of dynamic screen
pixels. The scale bar label is derived from ``denominator`` and ``w``.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFontMetricsF, QPen, QPolygonF

from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem, mm_font

_SYMBOL_COLOR = QColor("#334155")


class NorthArrowItem(FreeGraphicsItem):
    kind = "north_arrow"

    def __init__(self, rect_scene: QRectF, parent=None) -> None:
        super().__init__(QRectF(0, 0, rect_scene.width(), rect_scene.height()), parent)
        self.setPos(rect_scene.topLeft())

    def paint_content(self, painter) -> None:
        r = self.rect()
        cx = r.center().x()
        # Triangle occupies top 70% of the item; "N" sits at bottom.
        tri_h = r.height() * 0.7
        half_w = r.width() * 0.3
        polygon = QPolygonF([
            QPointF(cx, r.top()),
            QPointF(cx - half_w, r.top() + tri_h),
            QPointF(cx + half_w, r.top() + tri_h),
        ])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_SYMBOL_COLOR)
        painter.drawPolygon(polygon)
        # "N" label
        painter.setPen(QPen(_SYMBOL_COLOR, 0))
        painter.setFont(mm_font(self.font_mm, bold=True))
        fm = QFontMetricsF(painter.font())
        tw = fm.horizontalAdvance("N")
        painter.drawText(
            QPointF(cx - tw / 2, r.bottom()),
            "N",
        )

    def geometry_record(self) -> dict:
        return self.frame_geometry_record()

    @classmethod
    def from_normalized(cls, rec: dict) -> "NorthArrowItem":
        g = rec["geometry"]
        item = cls(QRectF(g["x"], g["y"], g["w"], g["h"]))
        item._init_from_normalized(rec)
        return item


class ScaleBarItem(FreeGraphicsItem):
    kind = "scale_bar"

    def __init__(self, rect_scene: QRectF, denominator: int = 5000, parent=None) -> None:
        super().__init__(QRectF(0, 0, rect_scene.width(), rect_scene.height()), parent)
        self.setPos(rect_scene.topLeft())
        self.denominator = denominator

    def _label(self) -> str:
        """Ground distance represented by the bar width, in m or km."""
        ground_m = self.rect().width() / 1000.0 * self.denominator
        if ground_m >= 1000:
            return f"{ground_m / 1000:.1f} km  (1:{self.denominator})"
        return f"{ground_m:.0f} m  (1:{self.denominator})"

    def paint_content(self, painter) -> None:
        r = self.rect()
        bar_y = r.top() + r.height() * 0.4
        pen = QPen(_SYMBOL_COLOR, max(0.5, self.width_mm))
        painter.setPen(pen)
        painter.drawLine(QPointF(r.left(), bar_y), QPointF(r.right(), bar_y))
        painter.drawLine(QPointF(r.left(), bar_y - 2.0), QPointF(r.left(), bar_y + 2.0))
        painter.drawLine(QPointF(r.right(), bar_y - 2.0), QPointF(r.right(), bar_y + 2.0))
        # Label beneath
        painter.setPen(QPen(_SYMBOL_COLOR, 0))
        painter.setFont(mm_font(self.font_mm))
        fm = QFontMetricsF(painter.font())
        label = self._label()
        tw = fm.horizontalAdvance(label)
        painter.drawText(QPointF(r.center().x() - tw / 2, r.bottom()), label)

    def geometry_record(self) -> dict:
        return self.frame_geometry_record()

    def props_record(self) -> dict:
        return {"denominator": self.denominator}

    @classmethod
    def from_normalized(cls, rec: dict) -> "ScaleBarItem":
        g = rec["geometry"]
        item = cls(QRectF(g["x"], g["y"], g["w"], g["h"]), denominator=rec["props"]["denominator"])
        item._init_from_normalized(rec)
        return item
