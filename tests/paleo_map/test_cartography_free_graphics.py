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
from geoviz_paleo_map.cartography.items.free.text_item import FreeTextItem
from geoviz_paleo_map.cartography.items.free.line_items import (
    FreeArrowItem,
    FreePolygonItem,
    FreehandItem,
)
from geoviz_paleo_map.cartography.items.free.image_item import FreeImageItem
from geoviz_paleo_map.cartography.items.free.symbol_items import (
    NorthArrowItem,
    ScaleBarItem,
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


# -- Task 4: FreeTextItem ------------------------------------------------

def test_text_roundtrip_minimal():
    item = FreeTextItem(QPointF(20.0, 15.0), text="井位图")
    rec = _roundtrip(item)
    assert rec["kind"] == "text"
    assert rec["geometry"] == {"x": 20.0, "y": 15.0}
    assert rec["props"] == {"text": "井位图", "align": "left"}


def test_text_roundtrip_with_wrap_and_align():
    item = FreeTextItem(QPointF(20.0, 15.0), text="长文本折行", wrap_w=30.0)
    item.align = "center"
    rec = _roundtrip(item)
    assert rec["geometry"] == {"x": 20.0, "y": 15.0, "w": 30.0}
    assert rec["props"]["align"] == "center"


def test_text_resize_sets_wrap_width():
    item = FreeTextItem(QPointF(20.0, 15.0), text="abc")
    assert "w" not in item.to_record()["geometry"]
    item.resize_to(QRectF(0, 0, 25.0, 8.0))
    geom = item.to_record()["geometry"]
    assert geom["w"] == 25.0
    assert geom["x"] == 20.0 and geom["y"] == 15.0
    assert item.rect().width() == 25.0
    assert item.rect().height() > 0


def test_text_font_mm_drives_height():
    small = FreeTextItem(QPointF(0.0, 0.0), text="Hg")
    large = FreeTextItem(QPointF(0.0, 0.0), text="Hg")
    large.apply_style({"stroke": "#000000", "fill": None, "width_mm": 0.3, "font_mm": 10.0})
    assert large.rect().height() > small.rect().height()


def test_paint_smoke_text(qtbot):
    _paint_smoke(FreeTextItem(QPointF(0.0, 0.0), text="冒烟", wrap_w=30.0))


# -- Task 5: arrow / polygon / freehand ----------------------------------

def test_arrow_roundtrip():
    pts = [(10.0, 10.0), (50.0, 10.0)]
    item = FreeArrowItem(pts)
    rec = _roundtrip(item)
    assert rec["kind"] == "arrow"
    assert rec["geometry"]["points"] == [[10.0, 10.0], [50.0, 10.0]]
    assert rec["props"] == {"head_mm": 3.0}


def test_polygon_roundtrip_with_fill():
    pts = [(0.0, 0.0), (40.0, 0.0), (20.0, 30.0)]
    item = FreePolygonItem(pts)
    item.fill = "#00ff00"
    rec = _roundtrip(item)
    assert rec["kind"] == "polygon"
    assert len(rec["geometry"]["points"]) == 3
    assert rec["style"]["fill"] == "#00ff00"


def test_freehand_roundtrip():
    pts = [(0.0, 0.0), (10.0, 5.0), (20.0, 0.0), (30.0, 5.0)]
    item = FreehandItem(pts)
    rec = _roundtrip(item)
    assert rec["kind"] == "freehand"
    assert rec["geometry"]["points"] == [[0.0, 0.0], [10.0, 5.0], [20.0, 0.0], [30.0, 5.0]]


def test_points_items_survive_move():
    item = FreeArrowItem([(10.0, 10.0), (50.0, 10.0)])
    item.setPos(QPointF(30.0, 25.0))
    rec = item.to_record()
    assert rec["geometry"]["points"] == [[30.0, 25.0], [70.0, 25.0]]


def test_points_resize_remaps_bbox():
    # Move bbox top-left by (20, 10) and double its size.
    pts = [(0.0, 0.0), (40.0, 0.0), (40.0, 20.0)]
    item = FreePolygonItem(pts)
    # bbox is (0,0,40,20).  Resize to (0,0,80,40) — scale x2 in both axes.
    item.resize_to(QRectF(0, 0, 80.0, 40.0))
    rec = item.to_record()
    assert rec["geometry"]["points"] == [[0.0, 0.0], [80.0, 0.0], [80.0, 40.0]]


def test_arrow_head_mm_applied():
    item = FreeArrowItem([(0.0, 0.0), (40.0, 0.0)])
    item.apply_style({"stroke": "#ff0000", "fill": None, "width_mm": 0.5, "font_mm": 3.5})
    assert item.width_mm == 0.5


def test_paint_smoke_points_items(qtbot):
    _paint_smoke(FreeArrowItem([(0.0, 0.0), (40.0, 10.0)]))
    _paint_smoke(FreePolygonItem([(0.0, 0.0), (40.0, 0.0), (20.0, 30.0)]))
    _paint_smoke(FreehandItem([(0.0, 0.0), (10.0, 5.0), (20.0, 0.0)]))


# -- Task 6: image / north_arrow / scale_bar ------------------------------

def test_image_roundtrip():
    item = FreeImageItem(QRectF(10.0, 10.0, 30.0, 20.0), path="/abs/logo.png")
    rec = _roundtrip(item)
    assert rec["kind"] == "image"
    assert rec["props"] == {"path": "/abs/logo.png"}
    assert rec["geometry"] == {"x": 10.0, "y": 10.0, "w": 30.0, "h": 20.0}


def test_image_missing_file_placeholder_paint(qtbot):
    item = FreeImageItem(QRectF(0.0, 0.0, 30.0, 20.0), path="/nonexistent/missing.png")
    assert item._pixmap is None
    _paint_smoke(item)  # must not crash; draws placeholder rect + text


def test_image_set_path_reloads():
    from PySide6.QtGui import QPixmap
    pm = QPixmap(4, 3)
    pm.fill(0xFF0000)
    item = FreeImageItem(QRectF(0.0, 0.0, 10.0, 10.0), path="/abs/x.png")
    item.set_pixmap(pm)
    assert item._pixmap is not None and item._pixmap.width() == 4


def test_north_arrow_roundtrip():
    item = NorthArrowItem(QRectF(50.0, 20.0, 15.0, 20.0))
    rec = _roundtrip(item)
    assert rec["kind"] == "north_arrow"
    assert rec["props"] == {}
    assert rec["geometry"] == {"x": 50.0, "y": 20.0, "w": 15.0, "h": 20.0}


def test_scale_bar_roundtrip():
    item = ScaleBarItem(QRectF(10.0, 180.0, 60.0, 10.0), denominator=25000)
    rec = _roundtrip(item)
    assert rec["kind"] == "scale_bar"
    assert rec["props"] == {"denominator": 25000}


def test_scale_bar_default_denominator():
    item = ScaleBarItem(QRectF(10.0, 180.0, 60.0, 10.0))
    assert item.denominator == 5000


def test_paint_smoke_symbols(qtbot):
    _paint_smoke(NorthArrowItem(QRectF(0.0, 0.0, 15.0, 20.0)))
    _paint_smoke(ScaleBarItem(QRectF(0.0, 0.0, 60.0, 10.0)))
