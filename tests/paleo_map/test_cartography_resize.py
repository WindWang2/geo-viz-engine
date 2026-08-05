# geo-viz-engine/tests/paleo_map/test_cartography_resize.py
"""Real resize-handle behaviour on LayoutGraphicsItem (Task 2).

The 8 handles used to be paint-only. Now a selected item can be resized by
dragging a handle; ``resize_to`` normalises any local rect (possibly with a
non-zero origin mid-drag) to ``pos + (0,0,w,h)``.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtWidgets import QGraphicsScene

from geoviz_paleo_map.cartography.items.base_item import LayoutGraphicsItem


def _item(rect=QRectF(0, 0, 40.0, 20.0), pos=QPointF(10.0, 10.0)):
    scene = QGraphicsScene()
    item = LayoutGraphicsItem(rect)
    item.setPos(pos)
    scene.addItem(item)
    return scene, item


def test_hit_handle_requires_selection():
    _, item = _item()
    assert item.hit_handle(QPointF(40.0, 20.0)) is None  # not selected
    item.setSelected(True)
    assert item.hit_handle(QPointF(40.0, 20.0)) == "br"
    assert item.hit_handle(QPointF(0.0, 0.0)) == "tl"
    assert item.hit_handle(QPointF(20.0, 0.0)) == "t"
    assert item.hit_handle(QPointF(20.0, 10.0)) is None  # centre: no handle


def test_resize_to_grows_from_origin():
    _, item = _item()
    item.resize_to(QRectF(0, 0, 60.0, 30.0))
    assert item.pos() == QPointF(10.0, 10.0)
    assert item.rect() == QRectF(0, 0, 60.0, 30.0)


def test_resize_to_normalises_nonzero_origin():
    # Mid-drag from a top/left handle the local rect has a non-zero origin;
    # resize_to must fold it into pos and zero the rect origin.
    _, item = _item()
    item.resize_to(QRectF(5.0, 4.0, 35.0, 16.0))
    assert item.pos() == QPointF(15.0, 14.0)
    assert item.rect() == QRectF(0, 0, 35.0, 16.0)


def test_resize_to_rejects_degenerate():
    _, item = _item()
    item.resize_to(QRectF(0, 0, 0.0, 10.0))
    assert item.rect() == QRectF(0, 0, 40.0, 20.0)  # unchanged


def test_remap_content_hook_called():
    calls = []

    class Spy(LayoutGraphicsItem):
        def _remap_content(self, old, new_local):
            calls.append((QRectF(old), QRectF(new_local)))

    scene = QGraphicsScene()
    spy = Spy(QRectF(0, 0, 10.0, 10.0))
    scene.addItem(spy)
    spy.resize_to(QRectF(0, 0, 20.0, 20.0))
    assert calls == [(QRectF(0, 0, 10.0, 10.0), QRectF(0, 0, 20.0, 20.0))]


def test_handle_size_is_class_attribute():
    assert LayoutGraphicsItem.handle_size == 4.0
