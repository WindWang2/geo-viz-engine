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


def _deliver_resize(canvas, w: int, h: int) -> None:
    """Offscreen resize() does not always deliver QResizeEvent synchronously."""
    from PySide6.QtCore import QEvent, QSize
    from PySide6.QtGui import QResizeEvent

    canvas.resizeEvent(QResizeEvent(QSize(w, h), QSize(w + 1, h + 1)))


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


def test_resize_preserves_user_viewport(qtbot):
    """#550: once the user has panned/zoomed, a resize must not refit the
    viewport to the data bounds (the interaction flags existed but were
    never read; the guard landed without a locking test)."""
    from geoviz_paleo_map import PaleoMapCanvas

    canvas = PaleoMapCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(800, 600)
    canvas.load_features(_TRIANGLE, period_name="测试")
    canvas._viewport.center_world = (105.0, 25.0)
    canvas._viewport.zoom = 6.0

    # Simulate a user pan: interaction flag set, viewport moved.
    canvas._user_has_interacted = True
    canvas._viewport.pan_pixels(120.0, 40.0)
    center_before = canvas._viewport.center_world
    zoom_before = canvas._viewport.zoom

    _deliver_resize(canvas, 640, 480)
    assert canvas._viewport.center_world == center_before
    assert canvas._viewport.zoom == zoom_before

    # Without interaction the resize still auto-fits.
    canvas2 = PaleoMapCanvas()
    qtbot.addWidget(canvas2)
    canvas2.resize(800, 600)
    canvas2.load_features(_TRIANGLE, period_name="测试")
    assert canvas2._user_has_interacted is False
    canvas2._viewport.zoom = 10.0  # would be clamped down by a refit
    _deliver_resize(canvas2, 640, 480)
    assert canvas2._viewport.zoom < 10.0
