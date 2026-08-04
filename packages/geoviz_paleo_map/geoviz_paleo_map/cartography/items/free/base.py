"""FreeGraphicsItem — base class for the nine paper free-graphic kinds.

Unifies: ``id`` (uuid4), ``kind``, style storage (``stroke``/``fill``/
``width_mm``/``font_mm``), the ``to_record()`` / ``from_normalized()``
serialization contract (spec §3.5), selection decoration without the default
frame, and the context menu (属性 / 删除).

Internal geometry convention: box kinds keep ``rect=(0,0,w,h)`` with the
paper-absolute position in ``pos``; point kinds keep local points with
``pos=bbox.topLeft``. ``to_record`` always emits paper-absolute mm.
"""

from __future__ import annotations

import uuid

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen
from PySide6.QtWidgets import QMenu

from geoviz_paleo_map.cartography.items.base_item import LayoutGraphicsItem
from geoviz_paleo_map.cartography.items.free import records

POINTS_PER_MM = 72.0 / 25.4


def mm_font(font_mm: float, bold: bool = False) -> QFont:
    """QFont whose point size renders ``font_mm`` millimetres tall on paper.

    Font sizes are stored/edited in mm (paper-deliverable intuition, spec
    §3.1); painting converts mm -> pt (1 pt = 25.4/72 mm).
    """
    font = QFont("Sans Serif")
    font.setPointSizeF(font_mm * POINTS_PER_MM)
    font.setBold(bold)
    return font


class FreeGraphicsItem(LayoutGraphicsItem):
    """Common id/kind/style/serialization for paper free graphics."""

    kind: str = ""

    def __init__(self, rect: QRectF, parent=None) -> None:
        super().__init__(rect, parent)
        self.id = str(uuid.uuid4())
        self.stroke: str = records.DEFAULT_STYLE["stroke"]
        self.fill: str | None = None
        self.width_mm: float = records.DEFAULT_STYLE["width_mm"]
        self.font_mm: float = records.DEFAULT_STYLE["font_mm"]
        # Free graphics paint their own content; the base frame (blue pen /
        # white brush set by LayoutGraphicsItem) must not show.
        self.setPen(QPen(Qt.PenStyle.NoPen))
        self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    # -- style ----------------------------------------------------------

    def stroke_pen(self) -> QPen:
        pen = QPen(QColor(self.stroke), self.width_mm)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def fill_brush(self) -> QBrush:
        if self.fill is None:
            return QBrush(Qt.BrushStyle.NoBrush)
        return QBrush(QColor(self.fill))

    def apply_style(self, style: dict) -> None:
        self.stroke = style["stroke"]
        self.fill = style["fill"]
        self.width_mm = style["width_mm"]
        self.font_mm = style["font_mm"]
        self.update()

    # -- serialization (spec §3.5) --------------------------------------

    def style_record(self) -> dict:
        return {
            "stroke": self.stroke,
            "fill": self.fill,
            "width_mm": self.width_mm,
            "font_mm": self.font_mm,
        }

    def geometry_record(self) -> dict:
        raise NotImplementedError

    def props_record(self) -> dict:
        return {}

    def to_record(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "style": self.style_record(),
            "geometry": self.geometry_record(),
            "props": self.props_record(),
        }

    def _init_from_normalized(self, rec: dict) -> None:
        """Shared tail of every ``from_normalized``: id + style."""
        self.id = rec["id"]
        self.apply_style(rec["style"])

    @classmethod
    def from_normalized(cls, rec: dict) -> "FreeGraphicsItem":
        """Build from ``records.parse_record`` output. Subclasses implement."""
        raise NotImplementedError

    def set_frame_from_geometry(self, g: dict) -> None:
        """Box-kind helper: absolute ``{x,y,w,h}`` -> pos + origin-zero rect."""
        self.setRect(0, 0, g["w"], g["h"])
        self.setPos(g["x"], g["y"])

    def frame_geometry_record(self) -> dict:
        """Box-kind helper: pos + rect -> absolute ``{x,y,w,h}``."""
        p = self.pos()
        r = self.rect()
        return {"x": p.x() + r.x(), "y": p.y() + r.y(), "w": r.width(), "h": r.height()}

    # -- paint ------------------------------------------------------------

    def paint(self, painter, option, widget=None) -> None:
        self.paint_content(painter)
        if self.isSelected():
            self._paint_selection_handles(painter)

    def paint_content(self, painter) -> None:
        raise NotImplementedError

    # -- context menu (属性 / 删除; spec §3.4) ----------------------------

    def contextMenuEvent(self, event) -> None:
        self.setSelected(True)
        menu = QMenu()
        prop_action = menu.addAction("属性")
        del_action = menu.addAction("删除")
        chosen = menu.exec(event.screenPos())
        if chosen is del_action:
            scene = self.scene()
            if scene is not None:
                scene.removeItem(self)
        # "属性": selection alone drives the window's property panel.
