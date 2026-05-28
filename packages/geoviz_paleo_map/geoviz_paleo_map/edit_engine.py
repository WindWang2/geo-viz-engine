# packages/geoviz_paleo_map/geoviz_paleo_map/edit_engine.py
"""EditEngine — manages selection, drag operations, and edit mode state."""
from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QCursor

from geoviz_paleo_map.edit_commands import (
    EditCommand, UndoManager, MoveVertexCmd, MovePolygonCmd,
    InsertVertexCmd, DeleteVertexCmd, CreatePolygonCmd,
    DeletePolygonCmd, EditAttributesCmd, CompositeCommand,
)
from geoviz_paleo_map.edit_overlay import EditOverlayLayer
from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.topology import TopologyModel
from geoviz_paleo_map.viewport import PaleoMapViewport


class EditState(Enum):
    IDLE = auto()
    DRAGGING_VERTEX = auto()
    DRAGGING_POLYGON = auto()
    DRAWING_POLYGON = auto()


class EditEngine:
    """Manages editing interactions on a TopologyModel."""

    def __init__(self, overlay: EditOverlayLayer, undo_mgr: UndoManager):
        self._model: TopologyModel | None = None
        self._overlay = overlay
        self._undo_mgr = undo_mgr
        self._state = EditState.IDLE
        self._selected_id: str | None = None
        self._drag_vertex_id: int | None = None
        self._drag_start_world: tuple[float, float] | None = None
        self._drag_polygon_old_positions: list[tuple[float, float]] | None = None
        self._drawing_vertices: list[tuple[float, float]] = []
        self._facies_layer: FaciesPolygonsLayer | None = None

    def set_model(self, model: TopologyModel | None) -> None:
        self._model = model
        self._overlay.set_model(model)
        self._selected_id = None
        self._state = EditState.IDLE

    def set_facies_layer(self, layer: FaciesPolygonsLayer | None) -> None:
        self._facies_layer = layer

    @property
    def selected_id(self) -> str | None:
        return self._selected_id

    def select(self, feature_id: str | None) -> None:
        self._selected_id = feature_id
        self._overlay.set_selected(feature_id)
        if self._facies_layer is not None:
            self._facies_layer.set_selected(feature_id)

    def handle_mouse_press(self, screen_pt: QPointF,
                           viewport: PaleoMapViewport,
                           button: Qt.MouseButton) -> bool:
        """Handle mouse press. Returns True if the event was consumed."""
        if self._model is None:
            return False

        if button == Qt.MouseButton.LeftButton:
            # Check vertex handle hit
            vid = self._overlay.hit_test_vertex(screen_pt, viewport)
            if vid is not None:
                self._state = EditState.DRAGGING_VERTEX
                self._drag_vertex_id = vid
                v = self._model.get_vertex(vid)
                if v:
                    self._drag_start_world = (v.x, v.y)
                return True

            # Check polygon hit for selection/drag
            if self._facies_layer is not None:
                fid = self._facies_layer.hit_test_polygon(screen_pt, viewport)
                if fid:
                    if fid == self._selected_id:
                        # Start polygon drag
                        self._state = EditState.DRAGGING_POLYGON
                        wx, wy = viewport.screen_to_world(screen_pt)
                        self._drag_start_world = (wx, wy)
                        ref = self._model.get_feature(fid)
                        if ref and ref.rings:
                            self._drag_polygon_old_positions = [
                                (self._model.get_vertex(vid).x, self._model.get_vertex(vid).y)
                                for vid in ref.rings[0].vertex_ids
                            ]
                    else:
                        self.select(fid)
                    return True

            # Click on empty space: deselect
            self.select(None)
            return True

        return False

    def handle_mouse_move(self, screen_pt: QPointF,
                          viewport: PaleoMapViewport) -> bool:
        """Handle mouse move during drag. Returns True if consumed."""
        if self._model is None:
            return False

        self._overlay.set_mouse_position(screen_pt)

        if self._state == EditState.DRAGGING_VERTEX and self._drag_vertex_id is not None:
            wx, wy = viewport.screen_to_world(screen_pt)
            affected = self._model.move_vertex(self._drag_vertex_id, wx, wy)
            if self._facies_layer is not None:
                self._facies_layer.rebuild_dirty_paths(set(affected))
            return True

        if self._state == EditState.DRAGGING_POLYGON and self._drag_start_world is not None:
            wx, wy = viewport.screen_to_world(screen_pt)
            dx = wx - self._drag_start_world[0]
            dy = wy - self._drag_start_world[1]
            ref = self._model.get_feature(self._selected_id) if self._selected_id else None
            if ref:
                affected = set()
                for ring in ref.rings:
                    for i, vid in enumerate(ring.vertex_ids):
                        if self._drag_polygon_old_positions and i < len(self._drag_polygon_old_positions):
                            ox, oy = self._drag_polygon_old_positions[i]
                            self._model.move_vertex(vid, ox + dx, oy + dy)
                            affected.add(self._selected_id)
                if self._facies_layer is not None:
                    self._facies_layer.rebuild_dirty_paths(affected)
            return True

        return False

    def handle_mouse_release(self, screen_pt: QPointF,
                             viewport: PaleoMapViewport,
                             button: Qt.MouseButton) -> EditCommand | None:
        """Handle mouse release. Returns the command to commit, or None."""
        if button != Qt.MouseButton.LeftButton:
            return None

        cmd = None

        if self._state == EditState.DRAGGING_VERTEX and self._drag_vertex_id is not None:
            v = self._model.get_vertex(self._drag_vertex_id) if self._model else None
            if v and self._drag_start_world:
                old_x, old_y = self._drag_start_world
                if abs(v.x - old_x) > 1e-9 or abs(v.y - old_y) > 1e-9:
                    cmd = MoveVertexCmd(self._drag_vertex_id, old_x, old_y, v.x, v.y)

        elif self._state == EditState.DRAGGING_POLYGON and self._drag_start_world and self._drag_polygon_old_positions:
            wx, wy = viewport.screen_to_world(screen_pt)
            dx = wx - self._drag_start_world[0]
            dy = wy - self._drag_start_world[1]
            if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                cmd = MovePolygonCmd(self._selected_id, dx, dy, self._drag_polygon_old_positions)

        self._state = EditState.IDLE
        self._drag_vertex_id = None
        self._drag_start_world = None
        self._drag_polygon_old_positions = None
        return cmd

    def handle_double_click(self, screen_pt: QPointF,
                            viewport: PaleoMapViewport) -> EditCommand | None:
        """Handle double-click: insert vertex on edge."""
        if self._model is None or self._selected_id is None:
            return None
        edge = self._overlay.hit_test_edge(screen_pt, viewport)
        if edge is None:
            return None
        # Compute insertion point (midpoint of edge in screen coords, then convert)
        v1 = self._model.get_vertex(edge[0])
        v2 = self._model.get_vertex(edge[1])
        if v1 is None or v2 is None:
            return None
        mid_x = (v1.x + v2.x) / 2
        mid_y = (v1.y + v2.y) / 2
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        # Find the ring and insert index
        for ri, ring in enumerate(ref.rings):
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                if (ids[i] == edge[0] and ids[i + 1] == edge[1]) or \
                   (ids[i] == edge[1] and ids[i + 1] == edge[0]):
                    return InsertVertexCmd(mid_x, mid_y, edge, self._selected_id, ri, i + 1)
        return None

    def delete_selected_vertex(self, vertex_id: int) -> EditCommand | None:
        """Create a command to delete a vertex. Returns None if unsafe."""
        if self._model is None or self._selected_id is None:
            return None
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        v = self._model.get_vertex(vertex_id)
        if v is None:
            return None
        for ri, ring in enumerate(ref.rings):
            if vertex_id in ring.vertex_ids:
                if len(ring.vertex_ids) <= 4:  # minimum: 3 + closing
                    return None
                idx = ring.vertex_ids.index(vertex_id)
                return DeleteVertexCmd(vertex_id, v.x, v.y, self._selected_id, ri, idx)
        return None

    def delete_selected_polygon(self) -> EditCommand | None:
        """Create a command to delete the selected polygon."""
        if self._model is None or self._selected_id is None:
            return None
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        ring_coords = []
        for ring in ref.rings:
            coords = []
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v:
                    coords.append((v.x, v.y))
            ring_coords.append(coords)
        cmd = DeletePolygonCmd(
            self._selected_id, ring_coords, ref.level,
            ref.properties, ref.parent_id, ref.source_file,
        )
        self.select(None)
        return cmd

    def create_polygon_start(self) -> None:
        """Enter polygon creation mode."""
        self._state = EditState.DRAWING_POLYGON
        self._drawing_vertices = []

    def create_polygon_add_point(self, world_x: float, world_y: float) -> None:
        self._drawing_vertices.append((world_x, world_y))

    def create_polygon_finish(self, feature_id: str,
                              level: str = "facies",
                              properties: dict | None = None) -> EditCommand | None:
        """Finish polygon creation and return the command."""
        if len(self._drawing_vertices) < 3:
            self._state = EditState.IDLE
            self._drawing_vertices = []
            return None
        cmd = CreatePolygonCmd(
            feature_id=feature_id,
            vertices=list(self._drawing_vertices),
            level=level,
            properties=properties or {},
        )
        self._state = EditState.IDLE
        self._drawing_vertices = []
        return cmd

    def create_polygon_cancel(self) -> None:
        self._state = EditState.IDLE
        self._drawing_vertices = []

    @property
    def is_drawing(self) -> bool:
        return self._state == EditState.DRAWING_POLYGON
