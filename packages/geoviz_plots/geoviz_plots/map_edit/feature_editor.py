"""FeatureEditor: transactional, layer-level map geometry editor.

Promoted from ``paleo_workbench/mapping/feature_editor.py`` (Phase-2
promote-down, map #244 / PR-A #256). Stateful editor over a feature
collection: spatial hit testing, vertex snapping, coincident shared-node
synchronized movement, topology validation with TopologyError auto-rollback,
and transaction undo/redo history.

C++ bridge refactor (vs the Workbench original): the Workbench version called
``native_backend.dispatch("validate_ring", ring)``. The promoted version calls
the promoted ``geoviz_plots.map_edit.api.validate_ring`` directly (which itself
dispatches to ``map_edit_core`` when the C++ extension is built at the
consumer side, else falls back to pure Python). No ``native_backend``
dependency; the cycle is broken.
"""

from __future__ import annotations

import copy
import math
from typing import Any

from geoviz_plots.map_edit.api import (
    validate_ring as _validate_ring,
    validate_ring_local as _validate_ring_local,
)


def _is_xy(pt: Any) -> bool:
    return (
        isinstance(pt, (list, tuple))
        and len(pt) >= 2
        and isinstance(pt[0], (int, float))
        and isinstance(pt[1], (int, float))
    )


def _walk_vertex_slots(coords: Any):
    """Yield ``(container, index)`` for every nested GeoJSON ``[x, y]``."""
    if not isinstance(coords, (list, tuple)) or not coords:
        return
    first = coords[0]
    if isinstance(first, (int, float)):
        return
    if _is_xy(first):
        for i, pt in enumerate(coords):
            if _is_xy(pt):
                yield coords, i
        return
    for part in coords:
        yield from _walk_vertex_slots(part)


def _vertex_slots(geom: dict[str, Any]) -> list[tuple[list, int | None]]:
    coords = geom.get("coordinates", [])
    gtype = geom.get("type")
    if gtype == "Point" or (
        isinstance(coords, list)
        and len(coords) >= 2
        and isinstance(coords[0], (int, float))
    ):
        return [(coords, None)] if isinstance(coords, list) and len(coords) >= 2 else []
    return list(_walk_vertex_slots(coords))


def _vertex_xy(slot: tuple[list, int | None]) -> tuple[float, float]:
    container, idx = slot
    if idx is None:
        return float(container[0]), float(container[1])
    pt = container[idx]
    return float(pt[0]), float(pt[1])


def _set_vertex(slot: tuple[list, int | None], x: float, y: float) -> None:
    container, idx = slot
    if idx is None:
        container[0] = float(x)
        container[1] = float(y)
        return
    n = len(container)
    container[idx] = [float(x), float(y)]
    if n >= 2:
        if idx == 0:
            container[-1] = [float(x), float(y)]
        elif idx == n - 1:
            container[0] = [float(x), float(y)]


def _validate_whole_geometry(geom: dict[str, Any]) -> list[dict[str, Any]]:
    """Validate a feature geometry as a whole, not ring by ring.

    Polygon validity is not a per-ring property: interior rings must lie inside
    the exterior ring and rings must not cross or touch improperly. Checking
    each ring in isolation therefore accepts genuinely invalid polygons — an
    outer vertex dragged inside a hole, or a vertex dropped onto another vertex
    (a bow-tie) — and the per-ring edge-crossing test also misses some
    crossings depending on which vertex moved (#880).

    Shapely is the OGC oracle and is already a dependency of this package (it
    backs the merge/split operations in ``api``). When it is unavailable this
    returns no errors, leaving the per-ring checks as the only guard rather
    than failing the edit outright.
    """
    if geom.get("type") not in {"Polygon", "MultiPolygon"}:
        return []
    try:
        from shapely.geometry import shape
        from shapely.validation import explain_validity
    except Exception:  # pragma: no cover - shapely is a declared dependency
        return []
    try:
        shaped = shape(geom)
    except Exception as exc:  # an unbuildable geometry is itself invalid
        return [{"code": "invalid_geometry", "message": str(exc)}]
    if shaped.is_valid:
        return []
    return [{"code": "invalid_geometry", "message": str(explain_validity(shaped))}]


def _rings_for_validation(geom: dict[str, Any]) -> list[list]:
    coords = geom.get("coordinates") or []
    gtype = geom.get("type")
    if gtype == "Polygon":
        return [ring for ring in coords if isinstance(ring, list) and _is_xy(ring[0] if ring else None)]
    if gtype == "MultiPolygon":
        rings: list[list] = []
        for polygon in coords:
            if not isinstance(polygon, list):
                continue
            rings.extend(
                ring for ring in polygon
                if isinstance(ring, list) and _is_xy(ring[0] if ring else None)
            )
        return rings
    if isinstance(coords, list) and coords and _is_xy(coords[0]):
        return [coords]
    return []


class TopologyError(Exception):
    """Raised when a geometry operation violates topology invariants."""
    pass


class FeatureEditor:
    """Stateful, transactional layer-level map geometry editor."""

    def __init__(self) -> None:
        self.features: dict[str, dict[str, Any]] = {}
        self.selected_feature_id: str | None = None
        self.selected_vertex_index: int | None = None
        self._undo_stack: list[dict[str, dict[str, Any]]] = []
        self._redo_stack: list[dict[str, dict[str, Any]]] = []
        self._uncommitted_base: dict[str, dict[str, Any]] | None = None
        self._drag_targets: list[tuple[str, int]] | None = None
        # Features touched by moves since the last pointer release; scoped
        # for the deferred full validation on_pointer_up runs (#118).
        self._move_touched_features: set[str] = set()
        # Median nonzero segment length of the loaded layer; the scale-aware
        # default for pick/snap tolerances (see _default_tolerance).
        self._data_scale: float = 1.0

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    def load_layer(self, feature_collection: dict[str, Any] | list[dict[str, Any]]) -> None:
        """Load GeoJSON FeatureCollection or list of feature dicts."""
        self.features.clear()
        self.selected_feature_id = None
        self.selected_vertex_index = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._uncommitted_base = None
        self._drag_targets = None
        self._move_touched_features.clear()

        feat_list = []
        if isinstance(feature_collection, dict):
            feat_list = feature_collection.get("features", [])
        elif isinstance(feature_collection, list):
            feat_list = feature_collection

        for i, feat in enumerate(feat_list):
            feat_copy = copy.deepcopy(feat)
            feat_id = str(feat_copy.get("id") or f"feature_{i}")
            feat_copy["id"] = feat_id
            self.features[feat_id] = feat_copy

        self._uncommitted_base = copy.deepcopy(self.features)
        self._data_scale = self._compute_data_scale(feat_list)

    @staticmethod
    def _compute_data_scale(feat_list: list[dict[str, Any]]) -> float:
        """Median nonzero segment length of the loaded geometry.

        Informs the scale-aware default pick/snap tolerance. Hard-coded
        absolute-unit defaults were wrong in both CRS families: a 5.0-unit
        snap radius is ~555 km on degree-coordinate layers yet coarse on
        meter layers, and a 1e-4 coincident radius ≈ 11 m on degree layers
        silently merged distinct vertices (#844).
        """
        lengths: list[float] = []
        for feat in feat_list:
            pts = [_vertex_xy(s) for s in _vertex_slots(feat.get("geometry", {}))]
            for a, b in zip(pts, pts[1:]):
                d = math.hypot(b[0] - a[0], b[1] - a[1])
                if d > 0:
                    lengths.append(d)
        if not lengths:
            return 1.0
        lengths.sort()
        return float(lengths[len(lengths) // 2])

    def _default_tolerance(self) -> float:
        """Scale-aware pick/snap radius: 1% of the layer's median segment
        length, so editing behavior tracks the layer's own units instead of
        a fixed absolute radius (#844)."""
        return 0.01 * self._data_scale

    def commit(self) -> None:
        """Commit current transaction changes into Undo history stack."""
        if self._uncommitted_base is not None:
            self._undo_stack.append(self._uncommitted_base)
            self._redo_stack.clear()
            self._uncommitted_base = copy.deepcopy(self.features)

    def rollback(self) -> None:
        """Rollback current uncommitted changes to last committed transaction state."""
        if self._uncommitted_base is not None:
            self.features = copy.deepcopy(self._uncommitted_base)

    def undo(self) -> bool:
        """Undo last committed transaction."""
        if not self.can_undo:
            return False

        self._redo_stack.append(copy.deepcopy(self.features))
        self.features = self._undo_stack.pop()
        self._uncommitted_base = copy.deepcopy(self.features)
        return True

    def redo(self) -> bool:
        """Redo last undone transaction."""
        if not self.can_redo:
            return False

        self._undo_stack.append(copy.deepcopy(self.features))
        self.features = self._redo_stack.pop()
        self._uncommitted_base = copy.deepcopy(self.features)
        return True

    def select_at(self, x: float, y: float, tolerance: float | None = None) -> dict[str, Any] | None:
        """Perform spatial hit testing to select nearest feature and vertex.

        ``tolerance`` default is scale-aware (1% of the layer's median segment
        length); a fixed absolute radius is wrong in both degree and meter
        CRS (#844).
        """
        if tolerance is None:
            tolerance = self._default_tolerance()
        best_selection: dict[str, Any] | None = None
        min_dist = float("inf")

        for feat_id, feat in self.features.items():
            slots = _vertex_slots(feat.get("geometry", {}))
            for idx, slot in enumerate(slots):
                px, py = _vertex_xy(slot)
                dist = math.hypot(px - x, py - y)
                if dist <= tolerance and dist < min_dist:
                    min_dist = dist
                    best_selection = {
                        "feature_id": feat_id,
                        "vertex_index": idx,
                        "distance": dist,
                        "point": (px, py),
                    }

        if best_selection is not None:
            self.selected_feature_id = best_selection["feature_id"]
            self.selected_vertex_index = best_selection["vertex_index"]
            self._drag_targets = self._find_coincident_vertices(list(best_selection["point"]))
        return best_selection

    def on_pointer_down(self, x: float, y: float, tolerance: float | None = None) -> dict[str, Any] | None:
        """Handle pointer press event: select vertex at (x, y) and start transaction."""
        return self.select_at(x, y, tolerance=tolerance)

    def on_pointer_move(
        self,
        x: float,
        y: float,
        snap: bool = True,
        snap_tolerance: float | None = None,
    ) -> bool:
        """Handle pointer move event: update selected vertex position with snapping and topology checks.

        Runs the INCREMENTAL adjacent-edge check only (O(V) per move): the
        full per-ring and whole-geometry validation is deferred to
        :meth:`on_pointer_up` (#118). A ring that was simple before the drag
        cannot become self-intersecting without one of the moved vertex's
        adjacent edges being involved, so intra-ring topology is still
        caught during the drag.
        """
        if self.selected_feature_id is None or self.selected_vertex_index is None:
            return False
        return self.move_selected_vertex(
            x, y, snap=snap, snap_tolerance=snap_tolerance, validation="local"
        )

    def on_pointer_up(self) -> bool:
        """Handle pointer release: full topology validation, then commit.

        Drag moves only ran the incremental adjacent-edge check, so the
        complete per-ring plus whole-geometry (shapely) validation runs
        here, BEFORE the transaction commits — ``TopologyError`` still
        intercepts invalid geometries at commit time. On failure the whole
        uncommitted transaction (the drag) is rolled back to the state of
        the last commit / layer load (#118).
        """
        if self.selected_feature_id is None or self.selected_vertex_index is None:
            return False
        if self._move_touched_features:
            for fid in sorted(self._move_touched_features):
                errors = self._validate_feature_full(fid)
                if errors:
                    self.rollback()
                    self._move_touched_features.clear()
                    err_msg = ", ".join(
                        e.get("message", e.get("code", "invalid")) for e in errors
                    )
                    raise TopologyError(
                        f"Invalid topology on feature '{fid}': {err_msg}"
                    )
        self.commit()
        self._move_touched_features.clear()
        return True

    @staticmethod
    def _extract_ring(feat: dict[str, Any]) -> list[list[float]] | None:
        """Extract a mutable list-of-positions ring from a Polygon or LineString."""
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords:
            return None
        gtype = geom.get("type")
        if gtype == "Polygon":
            ring = coords[0]
            return ring if isinstance(ring, list) and _is_xy(ring[0] if ring else None) else None
        if gtype in {"Point", "MultiPolygon", "MultiLineString", "GeometryCollection"}:
            return None
        if isinstance(coords[0], (int, float)):
            return None
        if _is_xy(coords[0]):
            return coords
        return None

    def _find_coincident_vertices(self, target_point: list[float], tol: float | None = None) -> list[tuple[str, int]]:
        """Find all (feature_id, vertex_index) tuples matching target_point.

        ``tol`` None means "same stored position": an epsilon scaled to the
        point's magnitude (ulp-level), never a fixed map-unit radius — the
        old absolute 1e-4 is ~11 m on degree layers and silently merged
        distinct-but-nearby vertices into shared ones (#844).
        """
        coincident = []
        tx, ty = target_point[0], target_point[1]
        if tol is None:
            tol = max(abs(tx), abs(ty), 1.0) * 1e-12
        for fid, feat in self.features.items():
            for idx, slot in enumerate(_vertex_slots(feat.get("geometry", {}))):
                px, py = _vertex_xy(slot)
                if math.hypot(px - tx, py - ty) <= tol:
                    coincident.append((fid, idx))
        return coincident

    def find_snap_target(
        self,
        x: float,
        y: float,
        exclude_targets: set[tuple[str, int]] | None = None,
        snap_tolerance: float | None = None,
    ) -> tuple[float, float]:
        """Find nearest vertex target for snapping within tolerance.

        Default ``snap_tolerance`` is scale-aware (1% of the layer's median
        segment length); the old fixed 5.0 map units is ~555 km on degree
        layers and coarse on meter layers (#844).
        """
        if snap_tolerance is None:
            snap_tolerance = self._default_tolerance()
        exclude = exclude_targets or set()
        best_pt = (x, y)
        min_dist = snap_tolerance

        for fid, feat in self.features.items():
            for idx, slot in enumerate(_vertex_slots(feat.get("geometry", {}))):
                if (fid, idx) in exclude:
                    continue
                px, py = _vertex_xy(slot)
                dist = math.hypot(px - x, py - y)
                if dist <= min_dist:
                    min_dist = dist
                    best_pt = (px, py)

        return best_pt

    def move_selected_vertex(
        self,
        x: float,
        y: float,
        snap: bool = True,
        snap_tolerance: float | None = None,
        validation: str = "full",
    ) -> bool:
        """Move selected vertex and coincident shared vertices with snapping, ring closure, and TopologyError auto-rollback.

        ``validation="local"`` (used by :meth:`on_pointer_move` during a
        drag) checks only the edges adjacent to each moved vertex — O(V)
        per mouse-move instead of the full O(V^2) ring re-validation — and
        defers the whole-geometry (shapely) check to pointer release
        (#118). ``validation="full"`` keeps the complete per-move check for
        direct callers.
        """
        if validation not in {"full", "local"}:
            raise ValueError("validation must be 'full' or 'local'")
        if self.selected_feature_id is None or self.selected_vertex_index is None:
            raise ValueError("No vertex currently selected")

        feat = self.features[self.selected_feature_id]
        slots = _vertex_slots(feat.get("geometry", {}))
        if not slots or self.selected_vertex_index >= len(slots):
            return False

        orig_x, orig_y = _vertex_xy(slots[self.selected_vertex_index])

        coincident_targets = list(self._drag_targets) if self._drag_targets else []
        if not coincident_targets:
            coincident_targets = self._find_coincident_vertices([orig_x, orig_y])
        if not coincident_targets:
            coincident_targets = [(self.selected_feature_id, self.selected_vertex_index)]

        coincident_set = set(coincident_targets)
        backup: list[tuple[str, int, float, float]] = []
        for fid, v_idx in coincident_targets:
            f_slots = _vertex_slots(self.features[fid].get("geometry", {}))
            if 0 <= v_idx < len(f_slots):
                bx, by = _vertex_xy(f_slots[v_idx])
                backup.append((fid, v_idx, bx, by))

        target_x, target_y = x, y
        if snap:
            target_x, target_y = self.find_snap_target(
                x, y, exclude_targets=coincident_set, snap_tolerance=snap_tolerance
            )

        touched_feature_ids = set()
        for fid, v_idx in coincident_targets:
            touched_feature_ids.add(fid)
            f_slots = _vertex_slots(self.features[fid].get("geometry", {}))
            if 0 <= v_idx < len(f_slots):
                _set_vertex(f_slots[v_idx], target_x, target_y)

        def _rollback() -> None:
            for bfid, bv_idx, bx, by in backup:
                b_slots = _vertex_slots(self.features[bfid].get("geometry", {}))
                if 0 <= bv_idx < len(b_slots):
                    _set_vertex(b_slots[bv_idx], bx, by)

        self._move_touched_features.update(touched_feature_ids)

        if validation == "local":
            # Incremental path: each moved vertex only endangers its own
            # two adjacent edges (all other edge pairs were unchanged); the
            # full-ring and whole-geometry checks run on pointer release.
            for fid, v_idx in coincident_targets:
                errors = self._validate_feature_local(fid, v_idx)
                if errors:
                    _rollback()
                    err_msg = ", ".join(
                        e.get("message", e.get("code", "invalid")) for e in errors
                    )
                    raise TopologyError(f"Invalid topology on feature '{fid}': {err_msg}")
        else:
            for fid in touched_feature_ids:
                errors = self._validate_feature_full(fid)
                if errors:
                    _rollback()
                    err_msg = ", ".join(
                        e.get("message", e.get("code", "invalid")) for e in errors
                    )
                    raise TopologyError(f"Invalid topology on feature '{fid}': {err_msg}")

        return True

    def _validate_feature_full(self, feature_id: str) -> list[dict[str, Any]]:
        """Full validation of one feature: every ring, then the whole geometry."""
        geom = self.features[feature_id].get("geometry", {})
        for f_ring in _rings_for_validation(geom):
            if len(f_ring) < 4:
                continue
            errors = _validate_ring(f_ring)
            if errors:
                return errors
        # Ring-level checks cannot express inter-ring relationships (a hole
        # escaping its exterior) or coincident-vertex degeneracy, so the
        # assembled geometry is validated too (#880).
        return _validate_whole_geometry(geom)

    def _validate_feature_local(
        self, feature_id: str, vertex_index: int
    ) -> list[dict[str, Any]]:
        """Incremental validation for one moved vertex slot (#118).

        Validates only the ring containing the slot, and within it only the
        two edges adjacent to the moved vertex. Falls back to the full
        feature check when the flat slot index cannot be mapped to a ring
        (malformed nesting).
        """
        feat = self.features.get(feature_id)
        if feat is None:
            return []
        geom = feat.get("geometry", {})
        located = self._locate_ring_slot(geom, vertex_index)
        if located is None:
            return self._validate_feature_full(feature_id)
        ring, local_index = located
        return _validate_ring_local(ring, [local_index])

    def _locate_ring_slot(
        self, geom: dict[str, Any], slot_index: int
    ) -> tuple[list, int] | None:
        """Map a flat ``_vertex_slots`` index to ``(ring, local_index)``.

        ``_vertex_slots`` enumerates ring positions in the same nested
        order ``_rings_for_validation`` extracts rings for well-formed
        geometries; a count mismatch (malformed nesting) yields ``None`` so
        callers can fall back to the full check.
        """
        rings = _rings_for_validation(geom)
        total = sum(len(r) for r in rings)
        if len(_vertex_slots(geom)) != total:
            return None
        offset = 0
        for ring in rings:
            if offset <= slot_index < offset + len(ring):
                return ring, slot_index - offset
            offset += len(ring)
        return None

    def _validate_ring_topology_or_rollback(
        self,
        feature_id: str,
        backup_features: dict[str, dict[str, Any]],
        action_context: str = "operation",
    ) -> None:
        """Validate feature ring topology and perform automatic rollback on error."""
        geom = self.features[feature_id].get("geometry", {})
        for ring in _rings_for_validation(geom):
            if len(ring) < 4:
                continue
            errors = _validate_ring(ring)
            if errors:
                self.features = backup_features
                err_msg = ", ".join(e.get("message", e.get("code", "invalid")) for e in errors)
                raise TopologyError(f"Invalid topology after {action_context} on '{feature_id}': {err_msg}")

    def add_vertex(self, feature_id: str, x: float, y: float, insert_index: int | None = None) -> bool:
        """Insert a new vertex into polygon ring."""
        if feature_id not in self.features:
            raise KeyError(f"Feature '{feature_id}' not found")

        feat = self.features[feature_id]
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords:
            return False

        ring = coords[0] if geom.get("type") == "Polygon" else coords
        backup_features = copy.deepcopy(self.features)

        idx = insert_index if insert_index is not None else len(ring) - 1
        ring.insert(idx, [float(x), float(y)])

        self._validate_ring_topology_or_rollback(feature_id, backup_features, "vertex insert")
        return True

    def delete_vertex(self, feature_id: str, vertex_index: int) -> bool:
        """Delete vertex with >= 3 unique vertex protection and topology validation."""
        if feature_id not in self.features:
            raise KeyError(f"Feature '{feature_id}' not found")

        feat = self.features[feature_id]
        geom = feat.get("geometry", {})
        coords = geom.get("coordinates", [])
        if not coords:
            return False

        ring = coords[0] if geom.get("type") == "Polygon" else coords
        unique_pts = len(ring) - 1 if ring[0] == ring[-1] else len(ring)

        if unique_pts <= 3:
            raise TopologyError("Polygon must have at least 3 unique vertices")

        backup_features = copy.deepcopy(self.features)
        ring.pop(vertex_index)

        # Maintain closure
        if ring[0] != ring[-1]:
            ring[-1] = list(ring[0])

        self._validate_ring_topology_or_rollback(feature_id, backup_features, "vertex deletion")
        return True


__all__ = ["TopologyError", "FeatureEditor"]
