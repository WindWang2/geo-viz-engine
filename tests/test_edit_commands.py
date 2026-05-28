"""Tests for edit commands and undo/redo manager."""
from __future__ import annotations

import pytest
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder, RingRef
from geoviz_paleo_map.edit_commands import (
    EditCommand, UndoManager, MoveVertexCmd, MovePolygonCmd,
    InsertVertexCmd, DeleteVertexCmd, CreatePolygonCmd,
    DeletePolygonCmd, EditAttributesCmd, CompositeCommand,
)


def _make_model_with_two_features() -> TopologyModel:
    features = [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩", "level": "facies", "name": "砂岩A"},
            "geometry": {"type": "Polygon", "coordinates": [[[0,0],[5,0],[5,10],[0,10],[0,0]]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "B", "facies": "泥岩", "level": "facies", "name": "泥岩B"},
            "geometry": {"type": "Polygon", "coordinates": [[[5,0],[10,0],[10,10],[5,10],[5,0]]]},
        },
    ]
    return TopologyBuilder.from_features(features)


def test_move_vertex_cmd():
    model = _make_model_with_two_features()
    # Find a vertex at x=5 (shared edge)
    ref_a = model.get_feature("A")
    shared_vid = None
    for vid in ref_a.rings[0].vertex_ids:
        v = model.get_vertex(vid)
        if v is not None and abs(v.x - 5.0) < 0.1 and abs(v.y - 0.0) < 0.1:
            shared_vid = vid
            break
    assert shared_vid is not None

    cmd = MoveVertexCmd(shared_vid, 5.0, 0.0, 6.0, 1.0)
    cmd.execute(model)
    v = model.get_vertex(shared_vid)
    assert v.x == 6.0
    assert v.y == 1.0

    cmd.undo(model)
    v = model.get_vertex(shared_vid)
    assert v.x == 5.0
    assert v.y == 0.0


def test_move_polygon_cmd():
    model = _make_model_with_two_features()
    ref = model.get_feature("A")
    old_positions = [(model.get_vertex(vid).x, model.get_vertex(vid).y)
                     for vid in ref.rings[0].vertex_ids]

    cmd = MovePolygonCmd("A", 1.0, 2.0, old_positions)
    cmd.execute(model)
    for vid in ref.rings[0].vertex_ids:
        v = model.get_vertex(vid)
        # Each vertex should have shifted by (1, 2)
        idx = ref.rings[0].vertex_ids.index(vid)
        assert abs(v.x - (old_positions[idx][0] + 1.0)) < 1e-9
        assert abs(v.y - (old_positions[idx][1] + 2.0)) < 1e-9

    cmd.undo(model)
    for vid in ref.rings[0].vertex_ids:
        v = model.get_vertex(vid)
        idx = ref.rings[0].vertex_ids.index(vid)
        assert abs(v.x - old_positions[idx][0]) < 1e-9
        assert abs(v.y - old_positions[idx][1]) < 1e-9


def test_insert_vertex_cmd():
    model = _make_model_with_two_features()
    ref = model.get_feature("A")
    ids = ref.rings[0].vertex_ids
    original_len = len(ids)
    # Insert between first and second vertex
    edge = (ids[0], ids[1])
    cmd = InsertVertexCmd(2.5, 0.0, edge, "A", 0, 1)
    cmd.execute(model)
    new_ids = ref.rings[0].vertex_ids
    assert len(new_ids) == original_len + 1
    # New vertex should be between the two original vertices
    new_vid = new_ids[1]
    new_v = model.get_vertex(new_vid)
    assert abs(new_v.x - 2.5) < 1e-9

    cmd.undo(model)
    assert len(ref.rings[0].vertex_ids) == original_len


def test_delete_vertex_cmd():
    model = _make_model_with_two_features()
    ref = model.get_feature("A")
    ids = ref.rings[0].vertex_ids
    original_len = len(ids)
    # Delete the second vertex (index 1)
    vid_to_delete = ids[1]
    v = model.get_vertex(vid_to_delete)
    cmd = DeleteVertexCmd(vid_to_delete, v.x, v.y, "A", 0, 1)
    cmd.execute(model)
    assert len(ref.rings[0].vertex_ids) == original_len - 1

    cmd.undo(model)
    assert len(ref.rings[0].vertex_ids) == original_len
    assert vid_to_delete in ref.rings[0].vertex_ids


def test_edit_attributes_cmd():
    model = _make_model_with_two_features()
    cmd = EditAttributesCmd("A", {"facies": "砂岩"}, {"facies": "石灰岩"})
    cmd.execute(model)
    assert model.get_feature("A").properties["facies"] == "石灰岩"

    cmd.undo(model)
    assert model.get_feature("A").properties["facies"] == "砂岩"


def test_undo_manager_basic():
    model = TopologyModel()
    v = model.add_vertex(0.0, 0.0)
    mgr = UndoManager()

    cmd = MoveVertexCmd(v.id, 0.0, 0.0, 1.0, 1.0)
    mgr.execute(cmd, model)
    assert v.x == 1.0

    mgr.undo(model)
    assert v.x == 0.0

    mgr.redo(model)
    assert v.x == 1.0


def test_undo_manager_clears_redo_on_new():
    model = TopologyModel()
    v = model.add_vertex(0.0, 0.0)
    mgr = UndoManager()

    cmd1 = MoveVertexCmd(v.id, 0.0, 0.0, 1.0, 0.0)
    mgr.execute(cmd1, model)
    mgr.undo(model)

    cmd2 = MoveVertexCmd(v.id, 0.0, 0.0, 0.0, 1.0)
    mgr.execute(cmd2, model)
    assert not mgr.can_redo()


def test_undo_manager_max_depth():
    model = TopologyModel()
    v = model.add_vertex(0.0, 0.0)
    mgr = UndoManager(max_depth=3)

    for i in range(5):
        old_x = v.x
        cmd = MoveVertexCmd(v.id, old_x, 0.0, float(i + 1), 0.0)
        mgr.execute(cmd, model)

    # Only last 3 should be undoable
    for _ in range(3):
        mgr.undo(model)
    assert not mgr.can_undo()


def test_composite_command():
    model = TopologyModel()
    v = model.add_vertex(0.0, 0.0)
    cmd1 = MoveVertexCmd(v.id, 0.0, 0.0, 1.0, 0.0)
    cmd2 = MoveVertexCmd(v.id, 1.0, 0.0, 1.0, 1.0)

    composite = CompositeCommand([cmd1, cmd2])
    composite.execute(model)
    assert v.x == 1.0
    assert v.y == 1.0

    composite.undo(model)
    assert v.x == 0.0
    assert v.y == 0.0


def test_create_polygon_cmd():
    model = TopologyModel()
    cmd = CreatePolygonCmd(
        feature_id="new",
        vertices=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        level="facies",
        properties={"facies": "砂岩"},
    )
    cmd.execute(model)
    assert model.get_feature("new") is not None
    assert len(model.get_feature("new").rings[0].vertex_ids) == 5  # 4 + closing

    cmd.undo(model)
    assert model.get_feature("new") is None


def test_delete_polygon_cmd():
    model = _make_model_with_two_features()
    ref = model.get_feature("A")
    ring_coords = [(model.get_vertex(vid).x, model.get_vertex(vid).y)
                   for vid in ref.rings[0].vertex_ids]

    cmd = DeletePolygonCmd("A", [ring_coords], "facies", {"facies": "砂岩"})
    cmd.execute(model)
    assert model.get_feature("A") is None

    cmd.undo(model)
    assert model.get_feature("A") is not None


def test_undo_manager_can_undo_can_redo_and_clear():
    model = TopologyModel()
    v = model.add_vertex(0.0, 0.0)
    mgr = UndoManager()

    assert not mgr.can_undo()
    assert not mgr.can_redo()

    cmd = MoveVertexCmd(v.id, 0.0, 0.0, 5.0, 5.0)
    mgr.execute(cmd, model)
    assert mgr.can_undo()
    assert not mgr.can_redo()

    mgr.undo(model)
    assert not mgr.can_undo()
    assert mgr.can_redo()

    mgr.clear()
    assert not mgr.can_undo()
    assert not mgr.can_redo()


# ---------------------------------------------------------------------------
# Edge-case tests
# ---------------------------------------------------------------------------

def test_undo_manager_redo_on_empty_stack():
    """Redo with nothing on redo stack returns False."""
    model = TopologyModel()
    mgr = UndoManager()
    result = mgr.redo(model)
    assert result is False


def test_move_vertex_cmd_feature_not_found():
    """MoveVertexCmd.execute on a vertex that doesn't exist — no crash."""
    model = TopologyModel()
    # Vertex 999 doesn't exist in model
    cmd = MoveVertexCmd(999, 0.0, 0.0, 1.0, 1.0)
    # Should not raise
    cmd.execute(model)
    assert model.get_vertex(999) is None

    # Undo should also not crash
    cmd.undo(model)


def test_insert_vertex_cmd_undo_new_vertex_not_in_ring():
    """InsertVertexCmd.undo when _new_vertex_id not in ring — graceful."""
    model = _make_model_with_two_features()
    ref = model.get_feature("A")
    ids = ref.rings[0].vertex_ids
    edge = (ids[0], ids[1])

    cmd = InsertVertexCmd(2.5, 0.0, edge, "A", 0, 1)
    cmd.execute(model)
    new_vid = cmd._new_vertex_id
    assert new_vid is not None

    # Manually remove the vertex from ring to simulate inconsistency
    ring = ref.rings[0]
    if new_vid in ring.vertex_ids:
        ring.vertex_ids.remove(new_vid)

    # Undo should handle gracefully (idx < 0 → early return)
    cmd.undo(model)


def test_insert_vertex_cmd_undo_no_new_vertex():
    """InsertVertexCmd.undo when execute was never called."""
    model = _make_model_with_two_features()
    ref = model.get_feature("A")
    ids = ref.rings[0].vertex_ids
    edge = (ids[0], ids[1])

    cmd = InsertVertexCmd(2.5, 0.0, edge, "A", 0, 1)
    # Don't execute — _new_vertex_id is None
    cmd.undo(model)  # should not crash


def test_delete_vertex_cmd_vid_not_in_ring():
    """DeleteVertexCmd.execute when vertex_id not in ring — graceful."""
    model = _make_model_with_two_features()
    # Use a vertex ID that is valid but not in feature "A"'s ring
    # Create a standalone vertex
    v = model.add_vertex(999.0, 999.0)
    cmd = DeleteVertexCmd(v.id, v.x, v.y, "A", 0, 999)
    # execute should return early since vid not in ring
    cmd.execute(model)
    # Feature "A" should be unchanged
    assert model.get_feature("A") is not None


def test_delete_vertex_cmd_feature_not_found():
    """DeleteVertexCmd.execute when feature doesn't exist."""
    model = TopologyModel()
    cmd = DeleteVertexCmd(0, 0.0, 0.0, "nonexistent", 0, 0)
    cmd.execute(model)  # should not crash


def test_delete_polygon_cmd_feature_not_found():
    """DeletePolygonCmd.execute when feature doesn't exist."""
    model = TopologyModel()
    cmd = DeletePolygonCmd("nonexistent", [], "facies", {})
    cmd.execute(model)  # should not crash
    assert model.get_feature("nonexistent") is None


def test_edit_attributes_cmd_feature_not_found():
    """EditAttributesCmd.execute when feature doesn't exist."""
    model = TopologyModel()
    cmd = EditAttributesCmd("nonexistent", {}, {"key": "value"})
    cmd.execute(model)  # should not crash


def test_edit_attributes_cmd_undo_feature_not_found():
    """EditAttributesCmd.undo when feature doesn't exist."""
    model = TopologyModel()
    cmd = EditAttributesCmd("nonexistent", {}, {"key": "value"})
    # Don't execute, just undo — _snapshot is None
    cmd.undo(model)  # should not crash
