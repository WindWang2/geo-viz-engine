"""Tests for EditEngine — selection, drag, and polygon creation."""
from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest
from PySide6.QtCore import QPointF, Qt

from geoviz_paleo_map.edit_commands import UndoManager, MoveVertexCmd, MovePolygonCmd
from geoviz_paleo_map.edit_engine import EditEngine, EditState
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder, RingRef
from geoviz_paleo_map.viewport import PaleoMapViewport


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_triangle_model() -> TopologyModel:
    """Three vertices forming a triangle, one feature 'tri'."""
    model = TopologyModel()
    v0 = model.add_vertex(100.0, 20.0)
    v1 = model.add_vertex(110.0, 20.0)
    v2 = model.add_vertex(105.0, 30.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v0.id])
    model.add_feature("tri", [ring], "facies", None, None, {"facies": "砂岩"})
    return model


def _make_square_model() -> TopologyModel:
    """Four vertices forming a square, one feature 'sq'."""
    model = TopologyModel()
    v0 = model.add_vertex(100.0, 20.0)
    v1 = model.add_vertex(110.0, 20.0)
    v2 = model.add_vertex(110.0, 30.0)
    v3 = model.add_vertex(100.0, 30.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v3.id, v0.id])
    model.add_feature("sq", [ring], "facies", None, None, {"facies": "砂岩"})
    return model


def _make_viewport() -> PaleoMapViewport:
    """Center at (105, 25), zoom=1, 800x600."""
    return PaleoMapViewport(center_lng=105.0, center_lat=25.0,
                            zoom=1.0, width=800, height=600)


def _make_engine() -> tuple[EditEngine, MagicMock, MagicMock]:
    """Create EditEngine with mocked overlay and facies layer."""
    overlay = MagicMock()
    facies_layer = MagicMock()
    undo_mgr = UndoManager()
    engine = EditEngine(overlay, undo_mgr)
    engine.set_facies_layer(facies_layer)
    return engine, overlay, facies_layer


# ---------------------------------------------------------------------------
# set_model / set_facies_layer / select
# ---------------------------------------------------------------------------

def test_set_model_resets_state():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    assert engine._model is model
    overlay.set_model.assert_called_with(model)
    assert engine._selected_id is None
    assert engine._state == EditState.IDLE


def test_set_model_none():
    engine, overlay, _ = _make_engine()
    engine.set_model(None)
    assert engine._model is None
    overlay.set_model.assert_called_with(None)


def test_set_facies_layer():
    engine, _, facies_layer = _make_engine()
    layer = MagicMock()
    engine.set_facies_layer(layer)
    assert engine._facies_layer is layer


def test_select_sets_id():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    assert engine.selected_id == "tri"
    overlay.set_selected.assert_called_with("tri")
    facies_layer.set_selected.assert_called_with("tri")


def test_select_none():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    engine.select(None)
    assert engine.selected_id is None
    overlay.set_selected.assert_called_with(None)


# ---------------------------------------------------------------------------
# handle_mouse_press
# ---------------------------------------------------------------------------

def test_handle_mouse_press_no_model():
    engine, overlay, _ = _make_engine()
    vp = _make_viewport()
    result = engine.handle_mouse_press(QPointF(400, 300), vp, Qt.MouseButton.LeftButton)
    assert result is False


def test_handle_mouse_press_vertex_hit():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    # Mock: vertex hit returns vertex ID 0
    overlay.hit_test_vertex.return_value = 0
    vp = _make_viewport()
    pt = QPointF(400, 300)

    result = engine.handle_mouse_press(pt, vp, Qt.MouseButton.LeftButton)
    assert result is True
    assert engine._state == EditState.DRAGGING_VERTEX
    assert engine._drag_vertex_id == 0
    v = model.get_vertex(0)
    assert engine._drag_start_world == (v.x, v.y)


def test_handle_mouse_press_polygon_hit_select():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    # No vertex hit
    overlay.hit_test_vertex.return_value = None
    # Polygon hit on "tri" — not currently selected
    facies_layer.hit_test_polygon.return_value = "tri"
    vp = _make_viewport()

    result = engine.handle_mouse_press(QPointF(400, 300), vp, Qt.MouseButton.LeftButton)
    assert result is True
    assert engine.selected_id == "tri"
    assert engine._state == EditState.IDLE  # just selected, not dragging


def test_handle_mouse_press_polygon_hit_drag():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")  # already selected
    overlay.hit_test_vertex.return_value = None
    facies_layer.hit_test_polygon.return_value = "tri"
    vp = _make_viewport()

    result = engine.handle_mouse_press(QPointF(400, 300), vp, Qt.MouseButton.LeftButton)
    assert result is True
    assert engine._state == EditState.DRAGGING_POLYGON
    assert engine._drag_polygon_old_positions is not None


def test_handle_mouse_press_empty_hit_deselects():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    overlay.hit_test_vertex.return_value = None
    facies_layer.hit_test_polygon.return_value = None
    vp = _make_viewport()

    result = engine.handle_mouse_press(QPointF(10, 10), vp, Qt.MouseButton.LeftButton)
    assert result is True
    assert engine.selected_id is None


def test_handle_mouse_press_right_button_ignored():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    vp = _make_viewport()

    result = engine.handle_mouse_press(QPointF(400, 300), vp, Qt.MouseButton.RightButton)
    assert result is False


# ---------------------------------------------------------------------------
# handle_mouse_move
# ---------------------------------------------------------------------------

def test_handle_mouse_move_no_model():
    engine, _, _ = _make_engine()
    vp = _make_viewport()
    result = engine.handle_mouse_move(QPointF(400, 300), vp)
    assert result is False


def test_handle_mouse_move_vertex_drag():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")

    # Simulate vertex drag state
    vid = 0
    v = model.get_vertex(vid)
    engine._state = EditState.DRAGGING_VERTEX
    engine._drag_vertex_id = vid
    engine._drag_start_world = (v.x, v.y)

    vp = _make_viewport()
    # Move to a new screen position — screen_to_world will give new world coords
    result = engine.handle_mouse_move(QPointF(450, 250), vp)
    assert result is True
    # Vertex should have moved
    new_v = model.get_vertex(vid)
    assert (new_v.x, new_v.y) != (100.0, 20.0)


def test_handle_mouse_move_polygon_drag():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    ref = model.get_feature("tri")

    # Record old positions
    old_positions = [(model.get_vertex(vid).x, model.get_vertex(vid).y)
                     for vid in ref.rings[0].vertex_ids]

    engine._state = EditState.DRAGGING_POLYGON
    engine._drag_start_world = (105.0, 25.0)
    engine._drag_polygon_old_positions = old_positions

    vp = _make_viewport()
    result = engine.handle_mouse_move(QPointF(420, 280), vp)
    assert result is True


def test_handle_mouse_move_idle():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    vp = _make_viewport()
    result = engine.handle_mouse_move(QPointF(400, 300), vp)
    assert result is False


# ---------------------------------------------------------------------------
# handle_mouse_release
# ---------------------------------------------------------------------------

def test_handle_mouse_release_vertex_drag_creates_command():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")

    vid = 0
    v = model.get_vertex(vid)
    old_x, old_y = v.x, v.y

    # Simulate drag: move vertex first
    engine._state = EditState.DRAGGING_VERTEX
    engine._drag_vertex_id = vid
    engine._drag_start_world = (old_x, old_y)
    model.move_vertex(vid, old_x + 5.0, old_y + 3.0)

    vp = _make_viewport()
    cmd = engine.handle_mouse_release(QPointF(400, 300), vp, Qt.MouseButton.LeftButton)
    assert cmd is not None
    assert isinstance(cmd, MoveVertexCmd)
    # State should be reset
    assert engine._state == EditState.IDLE
    assert engine._drag_vertex_id is None


def test_handle_mouse_release_no_movement_no_command():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)

    vid = 0
    v = model.get_vertex(vid)
    engine._state = EditState.DRAGGING_VERTEX
    engine._drag_vertex_id = vid
    engine._drag_start_world = (v.x, v.y)
    # Vertex was NOT moved (no handle_mouse_move called)

    vp = _make_viewport()
    cmd = engine.handle_mouse_release(QPointF(400, 300), vp, Qt.MouseButton.LeftButton)
    assert cmd is None  # no movement = no command


def test_handle_mouse_release_right_button():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    vp = _make_viewport()
    cmd = engine.handle_mouse_release(QPointF(400, 300), vp, Qt.MouseButton.RightButton)
    assert cmd is None


def test_handle_mouse_release_no_drag():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    vp = _make_viewport()
    cmd = engine.handle_mouse_release(QPointF(400, 300), vp, Qt.MouseButton.LeftButton)
    assert cmd is None


def test_handle_mouse_release_polygon_drag():
    engine, overlay, facies_layer = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    ref = model.get_feature("tri")

    old_positions = [(model.get_vertex(vid).x, model.get_vertex(vid).y)
                     for vid in ref.rings[0].vertex_ids]

    engine._state = EditState.DRAGGING_POLYGON
    engine._drag_start_world = (105.0, 25.0)
    engine._drag_polygon_old_positions = old_positions

    # Move vertices during drag
    vp = _make_viewport()
    engine.handle_mouse_move(QPointF(420, 280), vp)

    cmd = engine.handle_mouse_release(QPointF(420, 280), vp, Qt.MouseButton.LeftButton)
    assert cmd is not None
    assert isinstance(cmd, MovePolygonCmd)
    assert engine._state == EditState.IDLE


# ---------------------------------------------------------------------------
# delete_selected_vertex
# ---------------------------------------------------------------------------

def test_delete_selected_vertex_returns_command():
    engine, overlay, _ = _make_engine()
    model = _make_square_model()
    engine.set_model(model)
    engine.select("sq")
    ref = model.get_feature("sq")
    # Pick vertex at index 1 (not the closing vertex)
    vid = ref.rings[0].vertex_ids[1]

    cmd = engine.delete_selected_vertex(vid)
    assert cmd is not None
    # The command type depends on vertex count; square has 5 vertices (4+close)
    from geoviz_paleo_map.edit_commands import DeleteVertexCmd
    assert isinstance(cmd, DeleteVertexCmd)


def test_delete_selected_vertex_no_selection():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    # Nothing selected
    cmd = engine.delete_selected_vertex(0)
    assert cmd is None


def test_delete_selected_vertex_no_model():
    engine, _, _ = _make_engine()
    cmd = engine.delete_selected_vertex(0)
    assert cmd is None


def test_delete_selected_vertex_too_few_vertices():
    """Triangle with 4 ids (3+close) — minimum, so deletion rejected."""
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")
    ref = model.get_feature("tri")
    vid = ref.rings[0].vertex_ids[1]

    cmd = engine.delete_selected_vertex(vid)
    # triangle has 4 vertex_ids (3 unique + closing), minimum is 4 => rejection
    assert cmd is None


def test_delete_selected_vertex_nonexistent_vertex():
    engine, overlay, _ = _make_engine()
    model = _make_square_model()
    engine.set_model(model)
    engine.select("sq")

    cmd = engine.delete_selected_vertex(9999)
    assert cmd is None


# ---------------------------------------------------------------------------
# delete_selected_polygon
# ---------------------------------------------------------------------------

def test_delete_selected_polygon_returns_command():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)
    engine.select("tri")

    cmd = engine.delete_selected_polygon()
    assert cmd is not None
    from geoviz_paleo_map.edit_commands import DeletePolygonCmd
    assert isinstance(cmd, DeletePolygonCmd)
    # Should deselect after delete
    assert engine.selected_id is None


def test_delete_selected_polygon_no_selection():
    engine, overlay, _ = _make_engine()
    model = _make_triangle_model()
    engine.set_model(model)

    cmd = engine.delete_selected_polygon()
    assert cmd is None


def test_delete_selected_polygon_no_model():
    engine, _, _ = _make_engine()
    cmd = engine.delete_selected_polygon()
    assert cmd is None


# ---------------------------------------------------------------------------
# create_polygon_start / add_point / finish / cancel
# ---------------------------------------------------------------------------

def test_create_polygon_start():
    engine, _, _ = _make_engine()
    engine.create_polygon_start()
    assert engine._state == EditState.DRAWING_POLYGON
    assert engine._drawing_vertices == []
    assert engine.is_drawing is True


def test_create_polygon_add_point():
    engine, _, _ = _make_engine()
    engine.create_polygon_start()
    engine.create_polygon_add_point(100.0, 20.0)
    engine.create_polygon_add_point(110.0, 20.0)
    engine.create_polygon_add_point(105.0, 30.0)
    assert len(engine._drawing_vertices) == 3


def test_create_polygon_finish_returns_command():
    engine, _, _ = _make_engine()
    engine.create_polygon_start()
    engine.create_polygon_add_point(100.0, 20.0)
    engine.create_polygon_add_point(110.0, 20.0)
    engine.create_polygon_add_point(105.0, 30.0)

    cmd = engine.create_polygon_finish("new_poly", level="facies",
                                       properties={"facies": "砂岩"})
    assert cmd is not None
    from geoviz_paleo_map.edit_commands import CreatePolygonCmd
    assert isinstance(cmd, CreatePolygonCmd)
    assert engine._state == EditState.IDLE
    assert engine.is_drawing is False


def test_create_polygon_finish_too_few_vertices():
    engine, _, _ = _make_engine()
    engine.create_polygon_start()
    engine.create_polygon_add_point(100.0, 20.0)
    engine.create_polygon_add_point(110.0, 20.0)

    cmd = engine.create_polygon_finish("new_poly")
    assert cmd is None
    assert engine._state == EditState.IDLE


def test_create_polygon_cancel():
    engine, _, _ = _make_engine()
    engine.create_polygon_start()
    engine.create_polygon_add_point(100.0, 20.0)
    engine.create_polygon_add_point(110.0, 20.0)

    engine.create_polygon_cancel()
    assert engine._state == EditState.IDLE
    assert engine._drawing_vertices == []
    assert engine.is_drawing is False
