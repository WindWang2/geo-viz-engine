"""FreeGraphicsItem subclasses: serialization round-trips + paint smoke.

Record contract: spec §3.5 (frozen). Items store geometry internally as
``rect=(0,0,w,h) + pos=(x,y)`` (box kinds) or local points + pos=bbox origin
(point kinds); ``to_record`` always emits paper-absolute mm.
"""

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QImage, QPainter

from geoviz_paleo_map.cartography.items.free import ITEM_CLASSES, records
from geoviz_paleo_map.cartography.items.free.base import FreeGraphicsItem, mm_font
from geoviz_paleo_map.cartography.items.free.box_items import (
    FreeEllipseItem,
    FreeRectItem,
)


def _roundtrip(item):
    """item -> record -> parse -> from_normalized -> record (must be identical)."""
    rec1 = item.to_record()
    norm = records.parse_record(rec1)
    assert norm is not None, f"own to_record rejected by parse_record: {rec1}"
    item2 = ITEM_CLASSES[norm["kind"]].from_normalized(norm)
    assert item2 is not None
    assert item2.id == item.id
    return item2.to_record()


def _paint_smoke(item):
    img = QImage(120, 90, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    item.paint(p, None, None)
    p.end()


def test_base_stores_style_and_id():
    item = FreeRectItem(QRectF(10.0, 10.0, 40.0, 20.0))
    assert isinstance(item, FreeGraphicsItem)
    assert item.kind == "rect"
    assert item.id and isinstance(item.id, str)
    assert item.stroke == "#000000" and item.fill is None
    assert item.width_mm == 0.3 and item.font_mm == 3.5
    # free items draw no default frame
    assert item.pen().style() == Qt.PenStyle.NoPen


def test_rect_roundtrip():
    item = FreeRectItem(QRectF(10.0, 10.0, 40.0, 20.0))
    item.fill = "#ff0000"
    rec = _roundtrip(item)
    assert rec["geometry"] == {"x": 10.0, "y": 10.0, "w": 40.0, "h": 20.0}
    assert rec["style"]["fill"] == "#ff0000"


def test_ellipse_roundtrip():
    item = FreeEllipseItem(QRectF(5.0, 6.0, 30.0, 12.0))
    rec = _roundtrip(item)
    assert rec["kind"] == "ellipse"
    assert rec["geometry"] == {"x": 5.0, "y": 6.0, "w": 30.0, "h": 12.0}
    assert rec["props"] == {}


def test_box_items_survive_move_and_resize():
    item = FreeRectItem(QRectF(10.0, 10.0, 40.0, 20.0))
    item.setPos(QPointF(30.0, 25.0))
    assert item.to_record()["geometry"] == {"x": 30.0, "y": 25.0, "w": 40.0, "h": 20.0}
    item.resize_to(QRectF(0, 0, 55.0, 30.0))
    assert item.to_record()["geometry"] == {"x": 30.0, "y": 25.0, "w": 55.0, "h": 30.0}


def test_apply_style_updates_fields():
    item = FreeRectItem(QRectF(0.0, 0.0, 10.0, 10.0))
    item.apply_style({"stroke": "#00ff00", "fill": "#0000ff", "width_mm": 1.5, "font_mm": 5.0})
    assert item.stroke == "#00ff00"
    assert item.fill == "#0000ff"
    assert item.width_mm == 1.5
    assert item.font_mm == 5.0


def test_paint_smoke_box_items(qtbot):
    _paint_smoke(FreeRectItem(QRectF(0.0, 0.0, 40.0, 20.0)))
    _paint_smoke(FreeEllipseItem(QRectF(0.0, 0.0, 40.0, 20.0)))


def test_mm_font_scales_points():
    f = mm_font(3.5)
    assert f.pointSizeF() == pytest.approx(3.5 * 72.0 / 25.4)
