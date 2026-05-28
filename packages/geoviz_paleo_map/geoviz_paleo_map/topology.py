"""Topology model for shared-vertex polygon editing."""
from __future__ import annotations

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


class TopologyModel:
    """Shared-vertex topology graph for polygon editing."""

    def __init__(self) -> None:
        self._vertices: dict[int, TopologyVertex] = {}
        self._features: dict[str, FeatureRef] = {}
        self._edge_index: dict[tuple[int, int], set[str]] = {}
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
        return self._vertices

    def add_feature(self, feature_id: str, rings: list[RingRef],
                    level: str, parent_id: str | None,
                    source_file: str | None, properties: dict) -> FeatureRef:
        ref = FeatureRef(
            feature_id=feature_id, rings=rings, level=level,
            parent_id=parent_id, source_file=source_file,
            properties=dict(properties),
        )
        self._features[feature_id] = ref
        # Register edges
        for ring in rings:
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                edge = (min(ids[i], ids[i + 1]), max(ids[i], ids[i + 1]))
                self._edge_index.setdefault(edge, set()).add(feature_id)
        self._mark_feature_dirty(feature_id)
        return ref

    def get_feature(self, feature_id: str) -> FeatureRef | None:
        return self._features.get(feature_id)

    def all_features(self) -> dict[str, FeatureRef]:
        return self._features

    def move_vertex(self, vid: int, new_x: float, new_y: float) -> list[str]:
        """Move a vertex and return list of affected feature IDs."""
        v = self._vertices.get(vid)
        if v is None:
            return []
        v.x = new_x
        v.y = new_y
        affected = set()
        # Find features whose rings contain this vertex
        for fid, ref in self._features.items():
            for ring in ref.rings:
                if vid in ring.vertex_ids:
                    affected.add(fid)
                    break
        # Find features sharing edges with this vertex
        for edge, fids in self._edge_index.items():
            if vid in edge:
                affected.update(fids)
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
            if len(coords) == 1:
                geometry = {"type": "Polygon", "coordinates": coords}
            else:
                geometry = {"type": "MultiPolygon", "coordinates": [coords]}
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
