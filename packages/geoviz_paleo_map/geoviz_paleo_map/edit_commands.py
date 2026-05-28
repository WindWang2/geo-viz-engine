"""Edit commands with execute/undo for topology-preserving polygon editing."""
from __future__ import annotations

from abc import ABC, abstractmethod

from geoviz_paleo_map.topology import TopologyModel, RingRef


class EditCommand(ABC):
    """Base class for reversible editing operations."""

    @abstractmethod
    def execute(self, model: TopologyModel) -> None: ...

    @abstractmethod
    def undo(self, model: TopologyModel) -> None: ...


class MoveVertexCmd(EditCommand):
    """Move a single vertex from old position to new position."""

    def __init__(self, vertex_id: int, old_x: float, old_y: float,
                 new_x: float, new_y: float):
        self.vertex_id = vertex_id
        self.old_x = old_x
        self.old_y = old_y
        self.new_x = new_x
        self.new_y = new_y

    def execute(self, model: TopologyModel) -> None:
        model.move_vertex(self.vertex_id, self.new_x, self.new_y)

    def undo(self, model: TopologyModel) -> None:
        model.move_vertex(self.vertex_id, self.old_x, self.old_y)


class MovePolygonCmd(EditCommand):
    """Move an entire polygon by a delta, storing old positions for undo."""

    def __init__(self, feature_id: str, dx: float, dy: float,
                 old_positions: list[tuple[float, float]]):
        self.feature_id = feature_id
        self.dx = dx
        self.dy = dy
        self.old_positions = old_positions

    def execute(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None:
            return
        for ring in ref.rings:
            for i, vid in enumerate(ring.vertex_ids):
                ox, oy = self.old_positions[i] if i < len(self.old_positions) else (0, 0)
                model.move_vertex(vid, ox + self.dx, oy + self.dy)

    def undo(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None:
            return
        for ring in ref.rings:
            for i, vid in enumerate(ring.vertex_ids):
                if i < len(self.old_positions):
                    ox, oy = self.old_positions[i]
                    model.move_vertex(vid, ox, oy)


class InsertVertexCmd(EditCommand):
    """Insert a new vertex on an edge of a feature's ring."""

    def __init__(self, x: float, y: float,
                 edge: tuple[int, int],
                 feature_id: str, ring_index: int, insert_index: int):
        self.x = x
        self.y = y
        self.edge = edge
        self.feature_id = feature_id
        self.ring_index = ring_index
        self.insert_index = insert_index
        self._new_vertex_id: int | None = None

    def execute(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None or self.ring_index >= len(ref.rings):
            return
        ring = ref.rings[self.ring_index]
        ids = ring.vertex_ids
        # Capture old edge before insertion
        if self.insert_index > 0 and self.insert_index < len(ids):
            old_v1 = ids[self.insert_index - 1]
            old_v2 = ids[self.insert_index]
            old_edge = (min(old_v1, old_v2), max(old_v1, old_v2))
            fids = model._edge_index.get(old_edge)
            if fids:
                fids.discard(self.feature_id)
                if not fids:
                    del model._edge_index[old_edge]
        # Now insert vertex
        v = model.add_vertex(self.x, self.y)
        self._new_vertex_id = v.id
        ring.vertex_ids.insert(self.insert_index, v.id)
        # Register new edges
        ids = ring.vertex_ids
        if self.insert_index > 0:
            e1 = (min(ids[self.insert_index - 1], v.id), max(ids[self.insert_index - 1], v.id))
            model._edge_index.setdefault(e1, set()).add(self.feature_id)
        if self.insert_index < len(ids) - 1:
            e2 = (min(v.id, ids[self.insert_index + 1]), max(v.id, ids[self.insert_index + 1]))
            model._edge_index.setdefault(e2, set()).add(self.feature_id)
        model.mark_dirty()

    def undo(self, model: TopologyModel) -> None:
        if self._new_vertex_id is None:
            return
        ref = model.get_feature(self.feature_id)
        if ref is None or self.ring_index >= len(ref.rings):
            return
        ring = ref.rings[self.ring_index]
        idx = ring.vertex_ids.index(self._new_vertex_id) if self._new_vertex_id in ring.vertex_ids else -1
        if idx < 0:
            return
        # Capture neighbors for edge restoration
        prev_vid = ring.vertex_ids[idx - 1] if idx > 0 else None
        next_vid = ring.vertex_ids[idx + 1] if idx < len(ring.vertex_ids) - 1 else None
        # Remove new edges from index
        for neighbor in [prev_vid, next_vid]:
            if neighbor is not None:
                edge = (min(self._new_vertex_id, neighbor), max(self._new_vertex_id, neighbor))
                fids = model._edge_index.get(edge)
                if fids:
                    fids.discard(self.feature_id)
                    if not fids:
                        del model._edge_index[edge]
        # Restore old edge
        if prev_vid is not None and next_vid is not None:
            old_edge = (min(prev_vid, next_vid), max(prev_vid, next_vid))
            model._edge_index.setdefault(old_edge, set()).add(self.feature_id)
        # Remove vertex from ring
        ring.vertex_ids.remove(self._new_vertex_id)
        # Remove vertex from model
        model._vertices.pop(self._new_vertex_id, None)
        model._vertex_to_features.pop(self._new_vertex_id, None)
        model.mark_dirty()


class DeleteVertexCmd(EditCommand):
    """Delete a vertex from a feature's ring."""

    def __init__(self, vertex_id: int, x: float, y: float,
                 feature_id: str, ring_index: int, remove_index: int):
        self.vertex_id = vertex_id
        self.x = x
        self.y = y
        self.feature_id = feature_id
        self.ring_index = ring_index
        self.remove_index = remove_index

    def execute(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None or self.ring_index >= len(ref.rings):
            return
        ring = ref.rings[self.ring_index]
        idx = ring.vertex_ids.index(self.vertex_id) if self.vertex_id in ring.vertex_ids else -1
        if idx < 0:
            return
        # Capture neighbors for edge cleanup
        prev_vid = ring.vertex_ids[idx - 1] if idx > 0 else None
        next_vid = ring.vertex_ids[idx + 1] if idx < len(ring.vertex_ids) - 1 else None
        # Clean edges connecting deleted vertex to neighbors
        for neighbor in [prev_vid, next_vid]:
            if neighbor is not None:
                edge = (min(self.vertex_id, neighbor), max(self.vertex_id, neighbor))
                fids = model._edge_index.get(edge)
                if fids:
                    fids.discard(self.feature_id)
                    if not fids:
                        del model._edge_index[edge]
        # Restore old edge between neighbors
        if prev_vid is not None and next_vid is not None:
            old_edge = (min(prev_vid, next_vid), max(prev_vid, next_vid))
            model._edge_index.setdefault(old_edge, set()).add(self.feature_id)
        # Remove vertex
        ring.vertex_ids.remove(self.vertex_id)
        model._vertex_to_features.pop(self.vertex_id, None)
        model.mark_dirty()

    def undo(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None or self.ring_index >= len(ref.rings):
            return
        ring = ref.rings[self.ring_index]
        # Restore vertex if removed
        if self.vertex_id not in model._vertices:
            from geoviz_paleo_map.topology import TopologyVertex
            model._vertices[self.vertex_id] = TopologyVertex(
                x=self.x, y=self.y, id=self.vertex_id)
        # Insert back at original position
        ring.vertex_ids.insert(self.remove_index, self.vertex_id)
        # Restore edges: remove the neighbor-to-neighbor edge, add edges to restored vertex
        if self.remove_index > 0 and self.remove_index < len(ring.vertex_ids) - 1:
            prev_vid = ring.vertex_ids[self.remove_index - 1]
            next_vid = ring.vertex_ids[self.remove_index + 1]
            # Remove the edge that was created between neighbors during execute
            old_edge = (min(prev_vid, next_vid), max(prev_vid, next_vid))
            fids = model._edge_index.get(old_edge)
            if fids:
                fids.discard(self.feature_id)
                if not fids:
                    del model._edge_index[old_edge]
            # Restore edges to deleted vertex
            for neighbor in [prev_vid, next_vid]:
                edge = (min(self.vertex_id, neighbor), max(self.vertex_id, neighbor))
                model._edge_index.setdefault(edge, set()).add(self.feature_id)
        # Restore vertex_to_features
        model._vertex_to_features.setdefault(self.vertex_id, set()).add(self.feature_id)
        model.mark_dirty()


class CreatePolygonCmd(EditCommand):
    """Create a new polygon feature."""

    def __init__(self, feature_id: str, vertices: list[tuple[float, float]],
                 level: str = "facies", parent_id: str | None = None,
                 source_file: str | None = None, properties: dict | None = None):
        self.feature_id = feature_id
        self.vertices = vertices
        self.level = level
        self.parent_id = parent_id
        self.source_file = source_file
        self.properties = properties or {}
        self._created_vertex_ids: list[int] = []

    def execute(self, model: TopologyModel) -> None:
        self._created_vertex_ids = []
        for x, y in self.vertices:
            v = model.add_vertex(x, y)
            self._created_vertex_ids.append(v.id)
        # Close the ring
        if self._created_vertex_ids:
            self._created_vertex_ids.append(self._created_vertex_ids[0])
        ring = RingRef(vertex_ids=list(self._created_vertex_ids))
        model.add_feature(
            feature_id=self.feature_id,
            rings=[ring],
            level=self.level,
            parent_id=self.parent_id,
            source_file=self.source_file,
            properties=self.properties,
        )

    def undo(self, model: TopologyModel) -> None:
        # Remove feature
        model._features.pop(self.feature_id, None)
        # Remove edges
        edges_to_remove = []
        for edge, fids in model._edge_index.items():
            if self.feature_id in fids:
                fids.discard(self.feature_id)
                if not fids:
                    edges_to_remove.append(edge)
        for edge in edges_to_remove:
            del model._edge_index[edge]
        # Remove vertices and their reverse index entries
        for vid in self._created_vertex_ids:
            model._vertices.pop(vid, None)
            vtf = model._vertex_to_features.get(vid)
            if vtf:
                vtf.discard(self.feature_id)
                if not vtf:
                    del model._vertex_to_features[vid]
        model._path_cache.pop(self.feature_id, None)
        model._dirty_ids.discard(self.feature_id)
        model.mark_dirty()


class DeletePolygonCmd(EditCommand):
    """Delete a polygon feature (stores snapshot for undo)."""

    def __init__(self, feature_id: str, ring_coords: list[list[tuple[float, float]]],
                 level: str, properties: dict, parent_id: str | None = None,
                 source_file: str | None = None):
        self.feature_id = feature_id
        self.ring_coords = ring_coords
        self.level = level
        self.properties = properties
        self.parent_id = parent_id
        self.source_file = source_file
        self._removed_vertex_ids: list[int] = []
        self._removed_edges: dict[tuple[int, int], set[str]] = {}

    def execute(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None:
            return
        # Snapshot vertex IDs and edges before removal
        self._removed_vertex_ids = []
        for ring in ref.rings:
            self._removed_vertex_ids.extend(ring.vertex_ids)
        # Remove edges
        edges_to_clean = []
        for edge, fids in model._edge_index.items():
            if self.feature_id in fids:
                fids.discard(self.feature_id)
                if not fids:
                    edges_to_clean.append(edge)
        for edge in edges_to_clean:
            self._removed_edges[edge] = set()
            del model._edge_index[edge]
        # Remove feature
        model._features.pop(self.feature_id, None)
        model._path_cache.pop(self.feature_id, None)
        model._dirty_ids.discard(self.feature_id)
        model.mark_dirty()

    def undo(self, model: TopologyModel) -> None:
        # Recreate vertices
        for ring_coords in self.ring_coords:
            for x, y in ring_coords:
                model.add_vertex(x, y)
        # Recreate feature
        rings = []
        idx = 0
        for ring_coords in self.ring_coords:
            vid_list = []
            for _ in ring_coords:
                vid_list.append(self._removed_vertex_ids[idx])
                idx += 1
            rings.append(RingRef(vertex_ids=vid_list))
        model.add_feature(
            feature_id=self.feature_id,
            rings=rings,
            level=self.level,
            parent_id=self.parent_id,
            source_file=self.source_file,
            properties=self.properties,
        )
        model.mark_dirty()


class EditAttributesCmd(EditCommand):
    """Edit a feature's properties."""

    def __init__(self, feature_id: str, old_props: dict, new_props: dict):
        self.feature_id = feature_id
        self.old_props = dict(old_props)  # full snapshot
        self.new_props = dict(new_props)
        self._snapshot: dict | None = None

    def execute(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None:
            return
        self._snapshot = dict(ref.properties)  # snapshot before change
        ref.properties.clear()
        ref.properties.update(self.new_props)
        model.mark_dirty()

    def undo(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None or self._snapshot is None:
            return
        ref.properties.clear()
        ref.properties.update(self._snapshot)
        model.mark_dirty()


class CompositeCommand(EditCommand):
    """A sequence of commands executed as one unit."""

    def __init__(self, commands: list[EditCommand]):
        self._commands = commands

    def execute(self, model: TopologyModel) -> None:
        for cmd in self._commands:
            cmd.execute(model)

    def undo(self, model: TopologyModel) -> None:
        for cmd in reversed(self._commands):
            cmd.undo(model)


class UndoManager:
    """Manages undo/redo stacks for edit commands."""

    def __init__(self, max_depth: int = 100):
        self._undo_stack: list[EditCommand] = []
        self._redo_stack: list[EditCommand] = []
        self._max_depth = max_depth

    def execute(self, cmd: EditCommand, model: TopologyModel) -> None:
        cmd.execute(model)
        self._undo_stack.append(cmd)
        if len(self._undo_stack) > self._max_depth:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def undo(self, model: TopologyModel) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo(model)
        self._redo_stack.append(cmd)
        return True

    def redo(self, model: TopologyModel) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.execute(model)
        self._undo_stack.append(cmd)
        return True

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def clear(self) -> None:
        self._undo_stack.clear()
        self._redo_stack.clear()
