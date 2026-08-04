"""Placement controller + window tool-mode smoke tests (Task 7).

Offscreen Qt: we exercise the mode state machine and item creation, not
real mouse pixels. The controller installs as a Qt event filter on the
QGraphicsView.
"""

import pytest
from PySide6.QtCore import QPointF, QRectF, Qt

from geoviz_paleo_map.cartography.items.free import ITEM_CLASSES
from geoviz_paleo_map.cartography.placement import PlacementController
from geoviz_paleo_map.cartography.window import CartographyLayoutWindow


def test_window_has_tool_modes(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    assert win.current_tool_mode() == "select"
    win.set_tool_mode("rect")
    assert win.current_tool_mode() == "rect"


def test_placement_click_mode_creates_item(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_tool_mode("rect")
    ctrl = win._placement
    ctrl.begin_click(QPointF(30.0, 20.0))
    ctrl.end_click(QPointF(80.0, 60.0))
    free = [it for it in win._scene.items() if hasattr(it, "kind")]
    assert len(free) == 1
    assert free[0].kind == "rect"
    assert free[0].to_record()["geometry"]["x"] == 30.0


def test_placement_text_single_click(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_tool_mode("text")
    ctrl = win._placement
    ctrl.begin_click(QPointF(20.0, 15.0))
    ctrl.end_click(QPointF(20.0, 15.0))
    free = [it for it in win._scene.items() if hasattr(it, "kind")]
    assert len(free) == 1
    assert free[0].kind == "text"


def test_placement_freehand_drag(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_tool_mode("freehand")
    ctrl = win._placement
    ctrl.begin_click(QPointF(10.0, 10.0))
    ctrl.add_point(QPointF(20.0, 15.0))
    ctrl.add_point(QPointF(30.0, 10.0))
    ctrl.end_click(QPointF(30.0, 10.0))
    free = [it for it in win._scene.items() if hasattr(it, "kind")]
    assert len(free) == 1
    assert free[0].kind == "freehand"
    assert len(free[0].to_record()["geometry"]["points"]) >= 3


def test_placement_polygon_double_click_closes(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_tool_mode("polygon")
    ctrl = win._placement
    ctrl.begin_click(QPointF(0.0, 0.0))
    ctrl.add_point(QPointF(40.0, 0.0))
    ctrl.add_point(QPointF(20.0, 30.0))
    ctrl.finish_polygon()
    free = [it for it in win._scene.items() if hasattr(it, "kind")]
    assert len(free) == 1
    assert free[0].kind == "polygon"
    assert len(free[0].to_record()["geometry"]["points"]) == 3


def test_placement_esc_resets_to_select(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_tool_mode("rect")
    ctrl = win._placement
    ctrl.begin_click(QPointF(10.0, 10.0))
    ctrl.cancel()
    assert win.current_tool_mode() == "select"
    assert len([it for it in win._scene.items() if hasattr(it, "kind")]) == 0


def test_placement_clamps_to_paper(qtbot):
    win = CartographyLayoutWindow()
    qtbot.addWidget(win)
    win.set_tool_mode("rect")
    ctrl = win._placement
    # Click beyond the paper bottom-right corner.
    paper = win._scene.paper_rect()
    beyond = QPointF(paper.right() + 100, paper.bottom() + 100)
    ctrl.begin_click(QPointF(paper.right() - 50, paper.bottom() - 30))
    ctrl.end_click(beyond)
    free = [it for it in win._scene.items() if hasattr(it, "kind")]
    assert len(free) == 1
    g = free[0].to_record()["geometry"]
    assert g["x"] + g["w"] <= paper.right() + 0.1
    assert g["y"] + g["h"] <= paper.bottom() + 0.1
