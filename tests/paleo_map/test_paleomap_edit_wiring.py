"""PaleoMapCanvas edit-engine wiring (#504).

The canvas creates its EditEngine but never called set_facies_layer, so
polygon hit-testing was dead: every edit-mode click fell through to deselect
and the whole polygon-editing feature set (selection, drag, delete, insert/
delete vertex, edit attributes) was unreachable in the shipped widget — only
tests that wired the engine manually masked the gap. These tests drive the
real canvas mouse-press path.
"""
from __future__ import annotations

import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

_TRIANGLE = [
    {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[100.0, 20.0], [110.0, 20.0], [105.0, 30.0], [100.0, 20.0]]
            ],
        },
        "properties": {"id": "tri1", "facies": "砂岩"},
    }
]


def _press_at(canvas, screen_pt: QPointF) -> None:
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(screen_pt),
        QPointF(screen_pt),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.mousePressEvent(ev)


def test_edit_mode_click_selects_loaded_polygon(qtbot):
    """A click inside a loaded polygon must select it through the canvas
    event path (was: silently deselected, engine layer never wired)."""
    from geoviz_paleo_map import PaleoMapCanvas

    canvas = PaleoMapCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.load_features(_TRIANGLE, period_name="测试")
    # Center the viewport on the triangle centroid before entering edit mode
    # (no paint cycle runs offscreen, so fit-on-paint never happens).
    canvas._viewport.center_world = (105.0, 25.0)
    canvas._viewport.zoom = 6.0
    canvas.edit_mode = True

    center = canvas._viewport.lnglat_to_screen(105.0, 25.0)
    _press_at(canvas, center)
    assert canvas.edit_engine.selected_id == "tri1"


def test_edit_mode_second_click_starts_polygon_drag(qtbot):
    """Clicking the already-selected polygon must start a drag (the other
    dead branch of handle_mouse_press)."""
    from geoviz_paleo_map import PaleoMapCanvas
    from geoviz_paleo_map.edit_engine import EditState

    canvas = PaleoMapCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.load_features(_TRIANGLE, period_name="测试")
    canvas._viewport.center_world = (105.0, 25.0)
    canvas._viewport.zoom = 6.0
    canvas.edit_mode = True

    center = canvas._viewport.lnglat_to_screen(105.0, 25.0)
    _press_at(canvas, center)
    assert canvas.edit_engine.selected_id == "tri1"
    _press_at(canvas, center)
    assert canvas.edit_engine._state == EditState.DRAGGING_POLYGON


def test_edit_mode_click_outside_polygon_deselects(qtbot):
    """Empty-space clicks still deselect (the fall-through must keep
    working now that the layer is wired)."""
    from geoviz_paleo_map import PaleoMapCanvas

    canvas = PaleoMapCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.load_features(_TRIANGLE, period_name="测试")
    canvas._viewport.center_world = (105.0, 25.0)
    canvas._viewport.zoom = 6.0
    canvas.edit_mode = True

    center = canvas._viewport.lnglat_to_screen(105.0, 25.0)
    _press_at(canvas, center)
    assert canvas.edit_engine.selected_id == "tri1"
    far_away = canvas._viewport.lnglat_to_screen(180.0, 80.0)
    _press_at(canvas, far_away)
    assert canvas.edit_engine.selected_id is None
