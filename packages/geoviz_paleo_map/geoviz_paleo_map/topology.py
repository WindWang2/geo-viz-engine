"""Topology model for shared-vertex polygon editing."""
from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath


@dataclass
class TopologyVertex:
    """A shared point referenced by multiple polygon rings."""
    x: float  # longitude (world coord)
    y: float  # latitude (world coord)
    id: int   # unique vertex ID


@dataclass
class RingRef:
    """An ordered list of vertex IDs forming a closed polygon ring."""
    vertex_ids: list[int]


@dataclass
class FeatureRef:
    """A feature's geometry as references into the topology graph."""
    feature_id: str
    rings: list[RingRef]       # outer ring + holes
    level: str                 # "facies" | "sub_facies" | "micro_facies"
    parent_id: str | None
    source_file: str | None    # for hierarchy-aware save
    properties: dict           # original GeoJSON properties
    geometry_type: str = "Polygon"
    polygon_ring_counts: list[int] | None = None


class TopologyModel:
    """Shared-vertex topology graph for polygon editing."""

    def __init__(self) -> None:
        self._vertices: dict[int, TopologyVertex] = {}
        self._features: dict[str, FeatureRef] = {}
        self._edge_index: dict[tuple[int, int], set[str]] = {}
        self._vertex_to_features: dict[int, set[str]] = {}
        self._path_cache: dict[str, QPainterPath] = {}
        self._dirty_ids: set[str] = set()
        self._next_vertex_id: int = 0
        self.is_dirty: bool = False

    def add_vertex(self, x: float, y: float) -> TopologyVertex:
        vid = self._next_vertex_id
        self._next_vertex_id += 1
        v = TopologyVertex(x=x, y=y, id=vid)
        self._vertices[vid] = v
        return v

    def get_vertex(self, vid: int) -> TopologyVertex | None:
        return self._vertices.get(vid)

    def all_vertices(self) -> dict[int, TopologyVertex]:
        return dict(self._vertices)

    def add_feature(self, feature_id: str, rings: list[RingRef],
                    level: str, parent_id: str | None,
                    source_file: str | None, properties: dict,
                    geometry_type: str = "Polygon",
                    polygon_ring_counts: list[int] | None = None) -> FeatureRef:
        for ring in rings:
            if ring.vertex_ids and ring.vertex_ids[0] != ring.vertex_ids[-1]:
                ring.vertex_ids.append(ring.vertex_ids[0])
        counts = list(polygon_ring_counts or [len(rings)])
        if sum(counts) != len(rings) or any(count <= 0 for count in counts):
            counts = [len(rings)]
            geometry_type = "Polygon"
        ref = FeatureRef(
            feature_id=feature_id, rings=rings, level=level,
            parent_id=parent_id, source_file=source_file,
            properties=dict(properties),
            geometry_type=geometry_type,
            polygon_ring_counts=counts,
        )
        self._features[feature_id] = ref
        # Register vertex reverse index and edges
        for ring in rings:
            for vid in ring.vertex_ids:
                self._vertex_to_features.setdefault(vid, set()).add(feature_id)
        for ring in rings:
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                edge = (min(ids[i], ids[i + 1]), max(ids[i], ids[i + 1]))
                self._edge_index.setdefault(edge, set()).add(feature_id)
        self._mark_feature_dirty(feature_id)
        return ref

    def _rebuild_indexes(self) -> None:
        """Rebuild reverse vertex/edge indexes after a ring identity mutation."""
        self._edge_index.clear()
        self._vertex_to_features.clear()
        for feature_id, ref in self._features.items():
            for ring in ref.rings:
                for vertex_id in ring.vertex_ids:
                    self._vertex_to_features.setdefault(vertex_id, set()).add(feature_id)
                for first, second in zip(ring.vertex_ids, ring.vertex_ids[1:]):
                    edge = (min(first, second), max(first, second))
                    self._edge_index.setdefault(edge, set()).add(feature_id)

    def get_feature(self, feature_id: str) -> FeatureRef | None:
        return self._features.get(feature_id)

    def all_features(self) -> dict[str, FeatureRef]:
        return dict(self._features)

    def move_vertex(self, vid: int, new_x: float, new_y: float) -> list[str]:
        """Move a vertex and return list of affected feature IDs."""
        v = self._vertices.get(vid)
        if v is None:
            return []
        v.x = new_x
        v.y = new_y
        affected = self._vertex_to_features.get(vid, set())
        for fid in affected:
            self._mark_feature_dirty(fid)
        self.is_dirty = True
        return list(affected)

    def get_features_for_edge(self, edge: tuple[int, int]) -> set[str]:
        canonical = (min(edge[0], edge[1]), max(edge[0], edge[1]))
        return self._edge_index.get(canonical, set())

    def _mark_feature_dirty(self, feature_id: str) -> None:
        self._dirty_ids.add(feature_id)
        self._path_cache.pop(feature_id, None)

    def mark_dirty(self) -> None:
        self.is_dirty = True

    def mark_feature_dirty(self, feature_id: str) -> None:
        """Flag one feature for a display rebuild (attribute/style edits).

        Attribute-only commands change neither geometry nor edges, so they
        must poke the dirty set directly — the canvas refreshes affected
        layer items/labels from it (#549).
        """
        self._dirty_ids.add(feature_id)
        self._path_cache.pop(feature_id, None)

    def get_dirty_ids(self) -> set[str]:
        return set(self._dirty_ids)

    def clear_dirty(self) -> None:
        self._dirty_ids.clear()

    def build_path(self, feature_id: str) -> QPainterPath | None:
        """Build QPainterPath from topology coordinates for a feature."""
        ref = self._features.get(feature_id)
        if ref is None:
            return None
        path = QPainterPath()
        for ring in ref.rings:
            if len(ring.vertex_ids) < 3:
                continue
            first = self._vertices.get(ring.vertex_ids[0])
            if first is None:
                continue
            path.moveTo(QPointF(first.x, first.y))
            for vid in ring.vertex_ids[1:]:
                v = self._vertices.get(vid)
                if v is None:
                    continue
                path.lineTo(QPointF(v.x, v.y))
            path.closeSubpath()
        if path.isEmpty():
            return None
        path.setFillRule(Qt.FillRule.OddEvenFill)
        self._path_cache[feature_id] = path
        self._dirty_ids.discard(feature_id)
        return path

    def get_cached_path(self, feature_id: str) -> QPainterPath | None:
        if feature_id in self._dirty_ids:
            return self.build_path(feature_id)
        return self._path_cache.get(feature_id)

    def to_geojson(self) -> dict:
        """Serialize the topology model back to a GeoJSON FeatureCollection."""
        features = []
        for fid, ref in self._features.items():
            coords = []
            for ring in ref.rings:
                ring_coords = []
                for vid in ring.vertex_ids:
                    v = self._vertices.get(vid)
                    if v is not None:
                        ring_coords.append([v.x, v.y])
                if ring_coords:
                    coords.append(ring_coords)
            if not coords:
                continue
            if ref.geometry_type == "MultiPolygon":
                polygons = []
                offset = 0
                for count in ref.polygon_ring_counts or []:
                    polygons.append(coords[offset:offset + count])
                    offset += count
                geometry = {"type": "MultiPolygon", "coordinates": polygons}
            else:
                geometry = {"type": "Polygon", "coordinates": coords}
            feat = {
                "type": "Feature",
                "properties": dict(ref.properties),
                "geometry": geometry,
            }
            if ref.feature_id:
                feat.setdefault("properties", {})["id"] = ref.feature_id
            if ref.level:
                feat.setdefault("properties", {})["level"] = ref.level
            if ref.parent_id:
                feat.setdefault("properties", {})["parent_id"] = ref.parent_id
            features.append(feat)
        return {"type": "FeatureCollection", "features": features}


class TopologyBuilder:
    """Builds a TopologyModel from GeoJSON features with spatial vertex deduplication."""

    _DEDUP_TOLERANCE = 1e-6  # ~0.1m in degrees

    @classmethod
    def from_features(cls, features: list[dict],
                      source_file: str | None = None) -> TopologyModel:
        model = TopologyModel()
        grid: dict[tuple[int, int], int] = {}  # quantized (x,y) -> vertex_id

        for feat in features:
            geom = feat.get("geometry") or {}
            props = feat.get("properties") or {}
            gtype = geom.get("type")
            feature_id = props.get("id", "")

            if gtype == "Polygon":
                # GeoJSON Polygon coords: list of rings
                all_rings = geom["coordinates"]
                polygon_ring_counts = [len(all_rings)]
            elif gtype == "MultiPolygon":
                # GeoJSON MultiPolygon coords: list of polygons, each a list of rings
                polygons = geom["coordinates"]
                polygon_ring_counts = [len(poly) for poly in polygons]
                all_rings = [ring for poly in polygons for ring in poly]
            else:
                continue

            rings = cls._build_rings(model, all_rings, grid)

            if rings:
                model.add_feature(
                    feature_id=feature_id,
                    rings=rings,
                    level=props.get("level", "facies"),
                    parent_id=props.get("parent_id"),
                    source_file=source_file,
                    properties=props,
                    geometry_type=gtype,
                    polygon_ring_counts=polygon_ring_counts,
                )
        return model

    @classmethod
    def from_hierarchy(cls, hierarchy,
                       source_files: dict[str, str] | None = None) -> TopologyModel:
        model = TopologyModel()
        grid: dict[tuple[int, int], int] = {}

        for node in _walk_hierarchy(hierarchy.roots):
            ff = node.feature
            geom = ff.geometry or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                all_rings = geom["coordinates"]
                polygon_ring_counts = [len(all_rings)]
            elif gtype == "MultiPolygon":
                polygons = geom["coordinates"]
                polygon_ring_counts = [len(poly) for poly in polygons]
                all_rings = [ring for poly in polygons for ring in poly]
            else:
                continue

            rings = cls._build_rings(model, all_rings, grid)

            if rings:
                sf = (source_files or {}).get(ff.level)
                props = {
                    "facies": ff.facies_name,
                    "name": ff.display_name,
                    "id": ff.id,
                    "level": ff.level,
                    "period": ff.period,
                }
                model.add_feature(
                    feature_id=ff.id,
                    rings=rings,
                    level=ff.level,
                    parent_id=ff.parent_id,
                    source_file=sf,
                    properties=props,
                    geometry_type=gtype,
                    polygon_ring_counts=polygon_ring_counts,
                )
        return model

    @classmethod
    def _find_or_create_vertex(cls, model: TopologyModel,
                               x: float, y: float,
                               grid: dict[tuple[int, int], int]) -> int:
        tol = cls._DEDUP_TOLERANCE
        # Check grid cell and neighbors
        gx = math.floor(x / tol)
        gy = math.floor(y / tol)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                key = (gx + dx, gy + dy)
                vid = grid.get(key)
                if vid is not None:
                    v = model.get_vertex(vid)
                    if v is not None and abs(v.x - x) < tol and abs(v.y - y) < tol:
                        return vid
        # Create new vertex
        v = model.add_vertex(x, y)
        grid[(gx, gy)] = v.id
        return v.id

    @classmethod
    def _build_rings(cls, model: TopologyModel, all_rings: list, grid: dict) -> list[RingRef]:
        rings: list[RingRef] = []
        for ring_coords in all_rings:
            if not ring_coords:
                continue
            vid_list: list[int] = []
            for coord in ring_coords:
                if len(coord) < 2:
                    continue
                x, y = float(coord[0]), float(coord[1])
                vid = cls._find_or_create_vertex(model, x, y, grid)
                vid_list.append(vid)
            if vid_list:
                if vid_list[0] != vid_list[-1]:
                    vid_list.append(vid_list[0])
                rings.append(RingRef(vertex_ids=vid_list))
        return rings


def _walk_hierarchy(roots):
    """Yield all FaciesNode objects in a tree via DFS."""
    stack = list(roots)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)


def validate_polygon_geometry(geometry_type: str, coordinates: list) -> list[dict[str, str]]:
    """Validate a complete Polygon/MultiPolygon Shape in the engine core.

    Ring-level diagnostics remain useful to editors, while this whole-geometry
    check catches hole containment, nested-shell and part interaction errors.
    """
    if geometry_type not in {"Polygon", "MultiPolygon"}:
        return [{"code": "unsupported_geometry", "message": "Expected Polygon or MultiPolygon"}]
    try:
        from shapely.geometry import shape
        from shapely.validation import explain_validity
    except ImportError:
        return []
    try:
        geometry = shape({"type": geometry_type, "coordinates": coordinates})
    except Exception as exc:
        return [{"code": "invalid_shape", "message": f"Shape parse failed: {exc}"}]
    if geometry.is_empty:
        return [{"code": "empty_geometry", "message": "Geometry is empty"}]
    if not geometry.is_valid:
        return [{"code": "invalid_shape", "message": str(explain_validity(geometry))}]
    return []
