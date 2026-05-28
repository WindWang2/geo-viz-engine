# Paleo Map Editing with Topology Preservation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add full polygon editing to the paleogeographic map with shared-vertex topology constraints, hierarchy-aware parent recomputation, undo/redo, and save/export.

**Architecture:** A `TopologyModel` stores shared vertices referenced by multiple polygon rings. Moving one vertex propagates to all polygons sharing it. Parent boundaries auto-recompute via Shapely `unary_union`. An `EditOverlayLayer` renders vertex handles on top of the existing layer stack. All editing operations are encapsulated as reversible `EditCommand` objects.

**Tech Stack:** PySide6 (QPainter, QWidget, Signals), Shapely (parent union, split, merge), pytest + pytest-qt

---

## File Map

### New Files (in `packages/geoviz_paleo_map/geoviz_paleo_map/`)

| File | Responsibility |
|------|---------------|
| `topology.py` | TopologyVertex, TopologyEdge, RingRef, FeatureRef, TopologyModel — shared-vertex graph + spatial dedup builder + GeoJSON serialization |
| `edit_commands.py` | EditCommand ABC, all command subclasses, CompositeCommand, UndoManager |
| `edit_engine.py` | EditEngine — selection state, drag logic, hit-testing for handles/edges, operation dispatch |
| `edit_overlay.py` | EditOverlayLayer (PaleoLayer) — vertex handles, edge highlight, shared-vertex indicator |
| `save_export.py` | TopologyModel → GeoJSON save, hierarchy-aware multi-file save, SVG/PDF/PNG export |

### Modified Files

| File | Changes |
|------|---------|
| `canvas.py` | `edit_mode` property/signal, EditEngine instance, EditOverlayLayer in layer stack, keyboard shortcuts, topology lifecycle |
| `facies_polygons.py` | `selected_id` field, selection highlight rendering, `rebuild_dirty_paths()`, path building from topology coords |
| `zoom_pan.py` | `enabled` flag to disable drag-pan in edit mode |
| `hierarchy.py` | `get_children(parent_id)` method |
| `__init__.py` | Export new public APIs |

### Test Files (in `tests/`)

| File | Responsibility |
|------|---------------|
| `test_topology.py` | TopologyModel building, vertex dedup, edge sharing, serialization |
| `test_edit_commands.py` | All command execute/undo, UndoManager, CompositeCommand |
| `test_edit_engine.py` | Selection, vertex hit-test, drag dispatch |

---

## Phase 1: Topology Data Model

### Task 1: Topology Data Types and Model

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/topology.py`
- Test: `tests/test_topology.py`

- [ ] **Step 1: Write tests for TopologyVertex, RingRef, FeatureRef**

```python
# tests/test_topology.py
"""Tests for topology data model and builder."""
from __future__ import annotations

import pytest
from geoviz_paleo_map.topology import (
    TopologyVertex, RingRef, FeatureRef, TopologyModel,
)


def test_topology_vertex_creation():
    v = TopologyVertex(x=110.5, y=25.3, id=0)
    assert v.x == 110.5
    assert v.y == 25.3
    assert v.id == 0


def test_ring_ref_vertex_ids():
    ring = RingRef(vertex_ids=[0, 1, 2, 0])
    assert len(ring.vertex_ids) == 4


def test_feature_ref_fields():
    ref = FeatureRef(
        feature_id="f1",
        rings=[RingRef(vertex_ids=[0, 1, 2, 0])],
        level="facies",
        parent_id=None,
        source_file=None,
        properties={"facies": "砂岩", "name": "测试"},
    )
    assert ref.feature_id == "f1"
    assert ref.level == "facies"
    assert ref.parent_id is None
    assert len(ref.rings) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_topology.py -v`
Expected: FAIL — module `geoviz_paleo_map.topology` does not exist

- [ ] **Step 3: Implement TopologyVertex, RingRef, FeatureRef dataclasses**

```python
# packages/geoviz_paleo_map/geoviz_paleo_map/topology.py
"""Topology model for shared-vertex polygon editing."""
from __future__ import annotations

from dataclasses import dataclass, field


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_topology.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/topology.py tests/test_topology.py
git commit -m "feat(paleo): add topology data types (TopologyVertex, RingRef, FeatureRef)"
```

---

### Task 2: TopologyModel Core

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/topology.py`
- Modify: `tests/test_topology.py`

- [ ] **Step 1: Write tests for TopologyModel basic operations**

Append to `tests/test_topology.py`:

```python
def test_model_add_vertex():
    model = TopologyModel()
    v = model.add_vertex(110.0, 25.0)
    assert v.id == 0
    assert v.x == 110.0
    assert model.get_vertex(v.id) is v


def test_model_add_feature():
    model = TopologyModel()
    v0 = model.add_vertex(110.0, 20.0)
    v1 = model.add_vertex(120.0, 20.0)
    v2 = model.add_vertex(120.0, 30.0)
    v3 = model.add_vertex(110.0, 30.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v3.id, v0.id])
    ref = model.add_feature("f1", [ring], "facies", None, None, {"facies": "砂岩"})
    assert ref.feature_id == "f1"
    assert model.get_feature("f1") is ref


def test_model_move_vertex():
    model = TopologyModel()
    v = model.add_vertex(110.0, 25.0)
    model.move_vertex(v.id, 111.0, 26.0)
    assert v.x == 111.0
    assert v.y == 26.0


def test_model_features_sharing_vertex():
    """Two features share a vertex; moving it affects both."""
    model = TopologyModel()
    v0 = model.add_vertex(110.0, 20.0)
    v1 = model.add_vertex(120.0, 20.0)
    v2 = model.add_vertex(115.0, 30.0)
    v3 = model.add_vertex(110.0, 30.0)
    shared = model.add_vertex(120.0, 30.0)

    # Feature A: triangle v0-v1-shared
    ring_a = RingRef(vertex_ids=[v0.id, v1.id, shared.id, v0.id])
    model.add_feature("A", [ring_a], "facies", None, None, {})

    # Feature B: triangle v0-shared-v3
    ring_b = RingRef(vertex_ids=[v0.id, shared.id, v3.id, v0.id])
    model.add_feature("B", [ring_b], "facies", None, None, {})

    affected = model.move_vertex(shared.id, 121.0, 31.0)
    assert "A" in affected
    assert "B" in affected


def test_model_edge_index():
    model = TopologyModel()
    v0 = model.add_vertex(0.0, 0.0)
    v1 = model.add_vertex(1.0, 0.0)
    v2 = model.add_vertex(1.0, 1.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v0.id])
    model.add_feature("f1", [ring], "facies", None, None, {})

    edge = (min(v0.id, v1.id), max(v0.id, v1.id))
    assert "f1" in model.get_features_for_edge(edge)


def test_model_is_dirty():
    model = TopologyModel()
    assert not model.is_dirty
    v = model.add_vertex(0.0, 0.0)
    model.mark_dirty()
    assert model.is_dirty
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_topology.py -v`
Expected: FAIL — TopologyModel not defined

- [ ] **Step 3: Implement TopologyModel**

Append to `packages/geoviz_paleo_map/geoviz_paleo_map/topology.py`:

```python
from PySide6.QtGui import QPainterPath
from PySide6.QtCore import Qt


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
```

Also add the missing import at the top of `topology.py`:

```python
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_topology.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/topology.py tests/test_topology.py
git commit -m "feat(paleo): add TopologyModel with vertex ops, edge index, and GeoJSON serialization"
```

---

### Task 3: TopologyBuilder — GeoJSON to TopologyModel

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/topology.py`
- Modify: `tests/test_topology.py`

- [ ] **Step 1: Write tests for TopologyBuilder**

Append to `tests/test_topology.py`:

```python
from geoviz_paleo_map.topology import TopologyBuilder


def test_builder_from_features_simple():
    """Build topology from two adjacent squares sharing an edge."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩", "level": "facies"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[110, 20], [115, 20], [115, 30], [110, 30], [110, 20]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"id": "B", "facies": "泥岩", "level": "facies"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[115, 20], [120, 20], [120, 30], [115, 30], [115, 20]]],
            },
        },
    ]
    model = TopologyBuilder.from_features(features)
    assert len(model.all_features()) == 2
    # Shared edge: (115,20)-(115,30) — vertices should be deduplicated
    f_a = model.get_feature("A")
    f_b = model.get_feature("B")
    assert f_a is not None
    assert f_b is not None
    # Find shared vertex IDs
    a_ids = set(f_a.rings[0].vertex_ids)
    b_ids = set(f_b.rings[0].vertex_ids)
    shared_ids = a_ids & b_ids
    assert len(shared_ids) >= 2, "At least 2 vertices should be shared"


def test_builder_vertex_dedup_tolerance():
    """Vertices within 1e-6 degrees should be deduplicated."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "B", "facies": "泥岩"},
            # Offset by 5e-7 (within tolerance)
            "geometry": {"type": "Polygon", "coordinates": [[[1 + 5e-7, 0], [2, 0], [2, 1], [1, 1], [1 + 5e-7, 0]]]},
        },
    ]
    model = TopologyBuilder.from_features(features)
    total_vertices = len(model.all_vertices())
    # Should have 6 unique vertices (not 10) due to dedup
    assert total_vertices == 6


def test_builder_multipolygon():
    """MultiPolygon features produce multiple rings."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": "MP", "facies": "砂岩"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                    [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]],
                ],
            },
        },
    ]
    model = TopologyBuilder.from_features(features)
    ref = model.get_feature("MP")
    assert ref is not None
    assert len(ref.rings) == 2


def test_builder_from_hierarchy():
    """Build topology from FaciesHierarchy."""
    from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature, FaciesNode

    features = [
        FaciesFeature(id="root", facies_name="砂岩", display_name="砂岩",
                       level="facies", period="C1", parent_id=None,
                       geometry={"type": "Polygon", "coordinates": [[[0,0],[10,0],[10,10],[0,10],[0,0]]]}),
        FaciesFeature(id="child1", facies_name="细砂岩", display_name="细砂岩",
                       level="sub_facies", period="C1", parent_id="root",
                       geometry={"type": "Polygon", "coordinates": [[[0,0],[5,0],[5,10],[0,10],[0,0]]]}),
        FaciesFeature(id="child2", facies_name="粗砂岩", display_name="粗砂岩",
                       level="sub_facies", period="C1", parent_id="root",
                       geometry={"type": "Polygon", "coordinates": [[[5,0],[10,0],[10,10],[5,10],[5,0]]]}),
    ]
    hierarchy = FaciesHierarchy._build_tree(features)
    model = TopologyBuilder.from_hierarchy(hierarchy)
    assert len(model.all_features()) == 3
    assert model.get_feature("root") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_topology.py::test_builder_from_features_simple -v`
Expected: FAIL — TopologyBuilder not defined

- [ ] **Step 3: Implement TopologyBuilder**

Append to `packages/geoviz_paleo_map/geoviz_paleo_map/topology.py`:

```python
import math


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
                all_rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                all_rings = geom["coordinates"]
            else:
                continue

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
                    rings.append(RingRef(vertex_ids=vid_list))

            if rings:
                model.add_feature(
                    feature_id=feature_id,
                    rings=rings,
                    level=props.get("level", "facies"),
                    parent_id=props.get("parent_id"),
                    source_file=source_file,
                    properties=props,
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
                all_rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                all_rings = geom["coordinates"]
            else:
                continue

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
                    rings.append(RingRef(vertex_ids=vid_list))

            if rings:
                sf = (source_files or {}).get(ff.level)
                props = {
                    "facies": ff.facies_name,
                    "name": ff.display_name,
                    "id": ff.id,
                    "level": ff.level,
                    "period": ff.period,
                }
                if ff.parent_id:
                    props["parent_id"] = ff.parent_id
                model.add_feature(
                    feature_id=ff.id,
                    rings=rings,
                    level=ff.level,
                    parent_id=ff.parent_id,
                    source_file=sf,
                    properties=props,
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


def _walk_hierarchy(roots):
    """Yield all FaciesNode objects in a tree via DFS."""
    stack = list(roots)
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.children)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_topology.py -v`
Expected: PASS (13 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/topology.py tests/test_topology.py
git commit -m "feat(paleo): add TopologyBuilder with spatial vertex dedup and hierarchy support"
```

---

### Task 4: Export TopologyModel from __init__.py

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`

- [ ] **Step 1: Add topology exports to __init__.py**

```python
"""geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6."""
from geoviz_paleo_map.canvas import PaleoMapCanvas
from geoviz_paleo_map.hierarchy import FaciesHierarchy
from geoviz_paleo_map.floating_slider import FloatingScaleSlider
from geoviz_paleo_map.locked_panel import LockedObjectsPanel
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder

__all__ = [
    "PaleoMapCanvas", "FaciesHierarchy", "FloatingScaleSlider",
    "LockedObjectsPanel", "TopologyModel", "TopologyBuilder",
]
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from geoviz_paleo_map import TopologyModel, TopologyBuilder; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py
git commit -m "feat(paleo): export TopologyModel and TopologyBuilder from package"
```

---

## Phase 2: Undo/Redo System

### Task 5: EditCommand Base and UndoManager

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/edit_commands.py`
- Create: `tests/test_edit_commands.py`

- [ ] **Step 1: Write tests for EditCommand ABC and UndoManager**

```python
# tests/test_edit_commands.py
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
    # Insert between first and second vertex
    edge = (ids[0], ids[1])
    cmd = InsertVertexCmd(2.5, 0.0, edge, "A", 0, 1)
    cmd.execute(model)
    new_ids = ref.rings[0].vertex_ids
    assert len(new_ids) == len(ids) + 1
    # New vertex should be between the two original vertices
    new_vid = new_ids[1]
    new_v = model.get_vertex(new_vid)
    assert abs(new_v.x - 2.5) < 1e-9

    cmd.undo(model)
    assert len(ref.rings[0].vertex_ids) == len(ids)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_edit_commands.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement EditCommand, UndoManager, and all command subclasses**

```python
# packages/geoviz_paleo_map/geoviz_paleo_map/edit_commands.py
"""Edit commands with execute/undo for topology-preserving polygon editing."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

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
        v = model.add_vertex(self.x, self.y)
        self._new_vertex_id = v.id
        ref.rings[self.ring_index].vertex_ids.insert(self.insert_index, v.id)
        # Register new edges
        ids = ref.rings[self.ring_index].vertex_ids
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
        if self._new_vertex_id in ring.vertex_ids:
            ring.vertex_ids.remove(self._new_vertex_id)
        # Remove vertex from model
        model._vertices.pop(self._new_vertex_id, None)
        # Clean edge index
        edges_to_clean = []
        for edge, fids in model._edge_index.items():
            if self._new_vertex_id in edge:
                edges_to_clean.append(edge)
        for edge in edges_to_clean:
            del model._edge_index[edge]
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
        if self.vertex_id in ring.vertex_ids:
            ring.vertex_ids.remove(self.vertex_id)
        model.mark_dirty()

    def undo(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None or self.ring_index >= len(ref.rings):
            return
        ring = ref.rings[self.ring_index]
        ring.vertex_ids.insert(self.remove_index, self.vertex_id)
        # Restore vertex if removed
        if self.vertex_id not in model._vertices:
            from geoviz_paleo_map.topology import TopologyVertex
            model._vertices[self.vertex_id] = TopologyVertex(
                x=self.x, y=self.y, id=self.vertex_id)
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
        # Remove vertices
        for vid in self._created_vertex_ids:
            model._vertices.pop(vid, None)
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
        self.old_props = old_props
        self.new_props = new_props

    def execute(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None:
            return
        ref.properties.update(self.new_props)
        model.mark_dirty()

    def undo(self, model: TopologyModel) -> None:
        ref = model.get_feature(self.feature_id)
        if ref is None:
            return
        ref.properties.update(self.old_props)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_edit_commands.py -v`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/edit_commands.py tests/test_edit_commands.py
git commit -m "feat(paleo): add EditCommand hierarchy with UndoManager and all command types"
```

---

## Phase 3: Edit Overlay and Engine

### Task 6: EditOverlayLayer

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/edit_overlay.py`

- [ ] **Step 1: Implement EditOverlayLayer**

```python
# packages/geoviz_paleo_map/geoviz_paleo_map/edit_overlay.py
"""EditOverlayLayer — vertex handles, edge highlights, and shared-vertex indicators."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.topology import TopologyModel
from geoviz_paleo_map.viewport import PaleoMapViewport


class EditOverlayLayer(PaleoLayer):
    """Renders vertex handles and edge highlights for the selected polygon."""

    HANDLE_RADIUS = 4.0        # px (screen space)
    HANDLE_HOVER_RADIUS = 5.0
    EDGE_HIGHLIGHT_DIST = 8.0  # px threshold for edge hover

    def __init__(self) -> None:
        self._model: TopologyModel | None = None
        self._selected_id: str | None = None
        self._hovered_vertex_id: int | None = None
        self._hovered_edge: tuple[int, int] | None = None
        self._mouse_screen: QPointF | None = None

    def set_model(self, model: TopologyModel | None) -> None:
        self._model = model

    def set_selected(self, feature_id: str | None) -> None:
        self._selected_id = feature_id

    def set_mouse_position(self, screen_pt: QPointF | None) -> None:
        self._mouse_screen = screen_pt

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if self._model is None or self._selected_id is None:
            return

        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2
        oy = viewport.height / 2

        # Update hover state
        self._update_hover(viewport)

        # Draw edge highlight
        if self._hovered_edge is not None:
            self._draw_edge_highlight(painter, viewport, s, cx, cy, ox, oy)

        # Draw vertex handles
        for ring in ref.rings:
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v is None:
                    continue
                sx = (v.x - cx) * s + ox
                sy = (cy - v.y) * s + oy
                is_hovered = vid == self._hovered_vertex_id
                is_shared = self._is_vertex_shared(vid)
                self._draw_handle(painter, sx, sy, is_hovered, is_shared)

        painter.restore()

    def _draw_handle(self, painter: QPainter, sx: float, sy: float,
                     is_hovered: bool, is_shared: bool) -> None:
        radius = self.HANDLE_HOVER_RADIUS if is_hovered else self.HANDLE_RADIUS

        if is_hovered:
            painter.setPen(QPen(QColor("#1a56db"), 2.0))
            painter.setBrush(QBrush(QColor("#3182ce")))
        else:
            painter.setPen(QPen(QColor("#2d3748"), 1.5))
            painter.setBrush(QBrush(QColor("#ffffff")))

        painter.drawEllipse(QPointF(sx, sy), radius, radius)

        # Shared indicator: outer ring
        if is_shared and not is_hovered:
            painter.setPen(QPen(QColor("#e53e3e"), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(sx, sy), radius + 2, radius + 2)

    def _draw_edge_highlight(self, painter: QPainter, viewport: PaleoMapViewport,
                             s: float, cx: float, cy: float, ox: float, oy: float) -> None:
        if self._hovered_edge is None or self._model is None:
            return
        v1 = self._model.get_vertex(self._hovered_edge[0])
        v2 = self._model.get_vertex(self._hovered_edge[1])
        if v1 is None or v2 is None:
            return

        sx1 = (v1.x - cx) * s + ox
        sy1 = (cy - v1.y) * s + oy
        sx2 = (v2.x - cx) * s + ox
        sy2 = (cy - v2.y) * s + oy

        pen = QPen(QColor("#3182ce"), 2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

    def _update_hover(self, viewport: PaleoMapViewport) -> None:
        self._hovered_vertex_id = None
        self._hovered_edge = None

        if self._model is None or self._selected_id is None or self._mouse_screen is None:
            return

        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return

        mx = self._mouse_screen.x()
        my = self._mouse_screen.y()

        # Check vertex handles first (priority over edges)
        for ring in ref.rings:
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v is None:
                    continue
                sx, sy = viewport.world_to_screen(v.x, v.y)
                dist = ((sx - mx) ** 2 + (sy - my) ** 2) ** 0.5
                if dist < self.HANDLE_HOVER_RADIUS + 4:
                    self._hovered_vertex_id = vid
                    return

        # Check edges
        best_dist = self.EDGE_HIGHLIGHT_DIST
        for ring in ref.rings:
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                v1 = self._model.get_vertex(ids[i])
                v2 = self._model.get_vertex(ids[i + 1])
                if v1 is None or v2 is None:
                    continue
                dist = self._point_to_segment_dist(
                    mx, my,
                    *viewport.world_to_screen(v1.x, v1.y),
                    *viewport.world_to_screen(v2.x, v2.y),
                )
                if dist < best_dist:
                    best_dist = dist
                    self._hovered_edge = (ids[i], ids[i + 1])

    def _is_vertex_shared(self, vid: int) -> bool:
        if self._model is None:
            return False
        for edge, fids in self._model._edge_index.items():
            if vid in edge and len(fids) > 1:
                return True
        return False

    def hit_test_vertex(self, screen_pt: QPointF,
                        viewport: PaleoMapViewport) -> int | None:
        """Return the vertex ID under the cursor, or None."""
        if self._model is None or self._selected_id is None:
            return None
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        mx, my = screen_pt.x(), screen_pt.y()
        for ring in ref.rings:
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v is None:
                    continue
                sx, sy = viewport.world_to_screen(v.x, v.y)
                dist = ((sx - mx) ** 2 + (sy - my) ** 2) ** 0.5
                if dist < self.HANDLE_HOVER_RADIUS + 4:
                    return vid
        return None

    def hit_test_edge(self, screen_pt: QPointF,
                      viewport: PaleoMapViewport) -> tuple[int, int] | None:
        """Return the edge (v1_id, v2_id) nearest to cursor, or None."""
        if self._model is None or self._selected_id is None:
            return None
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        mx, my = screen_pt.x(), screen_pt.y()
        best_dist = self.EDGE_HIGHLIGHT_DIST
        best_edge = None
        for ring in ref.rings:
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                v1 = self._model.get_vertex(ids[i])
                v2 = self._model.get_vertex(ids[i + 1])
                if v1 is None or v2 is None:
                    continue
                dist = self._point_to_segment_dist(
                    mx, my,
                    *viewport.world_to_screen(v1.x, v1.y),
                    *viewport.world_to_screen(v2.x, v2.y),
                )
                if dist < best_dist:
                    best_dist = dist
                    best_edge = (ids[i], ids[i + 1])
        return best_edge

    @staticmethod
    def _point_to_segment_dist(px: float, py: float,
                               x1: float, y1: float,
                               x2: float, y2: float) -> float:
        dx = x2 - x1
        dy = y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / len_sq))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from geoviz_paleo_map.edit_overlay import EditOverlayLayer; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/edit_overlay.py
git commit -m "feat(paleo): add EditOverlayLayer with vertex handles and edge highlights"
```

---

### Task 7: FaciesPolygonsLayer Modifications

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py`

- [ ] **Step 1: Add selected_id field and selection highlight rendering**

Add to the `FaciesPolygonsLayer.__init__` method, after `self._locked_ids = locked_ids or {}`:

```python
        self._selected_id: str | None = None
        self._topology_model = None  # set externally when edit mode is active
```

Add setter methods after `__init__`:

```python
    def set_selected(self, feature_id: str | None) -> None:
        self._selected_id = feature_id

    def set_topology_model(self, model) -> None:
        self._topology_model = model

    def rebuild_dirty_paths(self, feature_ids: set[str]) -> None:
        """Rebuild QPainterPaths for features whose topology has changed."""
        if self._topology_model is None:
            return
        for fid in feature_ids:
            new_path = self._topology_model.build_path(fid)
            if new_path is None:
                continue
            for item in self._items:
                if item.feature_id == fid:
                    item.path = new_path
                    # Recompute bbox
                    br = new_path.boundingRect()
                    item.bbox = (br.left(), br.top(), br.right(), br.bottom())
        # Rebuild quadtree if any paths changed
        if feature_ids and self._items:
            min_x = min(item.bbox[0] for item in self._items)
            min_y = min(item.bbox[1] for item in self._items)
            max_x = max(item.bbox[2] for item in self._items)
            max_y = max(item.bbox[3] for item in self._items)
            self._quadtree_root = QuadtreeNode((min_x, min_y, max_x, max_y))
            for item in self._items:
                self._quadtree_root.insert(item)
```

- [ ] **Step 2: Modify paint() for selection highlight**

In the `paint()` method, after the fill pass (step 3), add a selection highlight pass. Modify the fill loop to reduce opacity for non-selected items when a selection exists:

Replace the fill pass section:

```python
        # 3. Draw visible polygons FILLS ONLY
        for (facies_name, boundary_kind), items in groups.items():
            style = self._resolver.resolve(facies_name)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.setBrush(style.brush)
            for item in items:
                painter.drawPath(item.path)
```

With:

```python
        # 3. Draw visible polygons FILLS ONLY
        has_selection = self._selected_id is not None
        for (facies_name, boundary_kind), items in groups.items():
            style = self._resolver.resolve(facies_name)
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            for item in items:
                if has_selection and item.feature_id != self._selected_id:
                    # Dim non-selected polygons
                    dim_brush = style.brush
                    painter.setOpacity(0.6)
                    painter.setBrush(dim_brush)
                    painter.drawPath(item.path)
                    painter.setOpacity(1.0)
                else:
                    painter.setBrush(style.brush)
                    painter.drawPath(item.path)

        # 3b. Draw selection glow
        if has_selection:
            for item in visible_items:
                if item.feature_id == self._selected_id:
                    glow_pen = QPen(QColor("#3182ce"), 3.0)
                    glow_pen.setCosmetic(True)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(item.path)
                    break
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/layers/facies_polygons.py
git commit -m "feat(paleo): add selection highlight and dirty path rebuild to FaciesPolygonsLayer"
```

---

### Task 8: ZoomPanHandler — Disable in Edit Mode

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/zoom_pan.py`

- [ ] **Step 1: Add enabled flag**

Add an `enabled` property to `ZoomPanHandler.__init__`:

```python
        self.enabled: bool = True
```

Guard `start_drag` and `update_drag`:

```python
    def start_drag(self, pt: QPointF) -> None:
        if not self.enabled:
            return
        self._drag_anchor = QPointF(pt)

    def update_drag(self, pt: QPointF) -> None:
        if not self.enabled or self._drag_anchor is None:
            return
        dx = pt.x() - self._drag_anchor.x()
        dy = pt.y() - self._drag_anchor.y()
        self.viewport.pan_pixels(dx, dy)
        self._drag_anchor = QPointF(pt)
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/zoom_pan.py
git commit -m "feat(paleo): add enabled flag to ZoomPanHandler for edit mode"
```

---

### Task 9: EditEngine — Selection and Drag Logic

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/edit_engine.py`

- [ ] **Step 1: Implement EditEngine**

```python
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
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from geoviz_paleo_map.edit_engine import EditEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/edit_engine.py
git commit -m "feat(paleo): add EditEngine with selection, drag, vertex insert/delete, polygon CRUD"
```

---

## Phase 4: Canvas Integration

### Task 10: Wire Edit Mode into PaleoMapCanvas

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py`

- [ ] **Step 1: Add edit mode imports and fields to canvas.py**

Add imports at the top of `canvas.py`:

```python
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder
from geoviz_paleo_map.edit_commands import UndoManager
from geoviz_paleo_map.edit_engine import EditEngine
from geoviz_paleo_map.edit_overlay import EditOverlayLayer
```

Add signals to `PaleoMapCanvas` class:

```python
    edit_mode_changed = Signal(bool)
    selection_changed = Signal(str)  # feature_id or ""
```

Add to `__init__` (after the locked_panel section):

```python
        # Edit mode
        self._edit_mode = False
        self._topology_model: TopologyModel | None = None
        self._edit_overlay = EditOverlayLayer()
        self._undo_mgr = UndoManager()
        self._edit_engine = EditEngine(self._edit_overlay, self._undo_mgr)
```

Add the edit mode property:

```python
    @property
    def edit_mode(self) -> bool:
        return self._edit_mode

    @edit_mode.setter
    def edit_mode(self, value: bool) -> None:
        if value == self._edit_mode:
            return
        self._edit_mode = value
        self._zoom_pan.enabled = not value
        if not value:
            self._edit_engine.select(None)
        if value and self._edit_overlay not in self._layers:
            self._layers.append(self._edit_overlay)
        elif not value and self._edit_overlay in self._layers:
            self._layers.remove(self._edit_overlay)
        self.edit_mode_changed.emit(value)
        self.update()

    @property
    def topology_model(self) -> TopologyModel | None:
        return self._topology_model

    @property
    def undo_manager(self) -> UndoManager:
        return self._undo_mgr

    @property
    def edit_engine(self) -> EditEngine:
        return self._edit_engine
```

- [ ] **Step 2: Build topology on load**

Add to `load_features()`, after `self._wells_data = wells or []`:

```python
        # Build topology model for editing
        self._topology_model = TopologyBuilder.from_features(features)
        self._edit_engine.set_model(self._topology_model)
```

Add to `load_hierarchy()`, after `self._layers = self._level_groups.get(level, [])`:

```python
        # Build topology model for editing
        self._topology_model = TopologyBuilder.from_hierarchy(hierarchy)
        self._edit_engine.set_model(self._topology_model)
```

- [ ] **Step 3: Wire edit engine into mouse events**

Replace `mousePressEvent`:

```python
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._edit_mode:
                consumed = self._edit_engine.handle_mouse_press(
                    QPointF(event.position()), self._viewport, event.button())
                if consumed:
                    self.selection_changed.emit(self._edit_engine.selected_id or "")
                    self.update()
                    return
            self._zoom_pan.start_drag(QPointF(event.position()))
            self._press_pos = QPointF(event.position())
```

Replace `mouseMoveEvent`:

```python
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = QPointF(event.position())
        if self._edit_mode:
            consumed = self._edit_engine.handle_mouse_move(pos, self._viewport)
            if consumed:
                self.update()
                return
        if self._zoom_pan.is_dragging():
            self._zoom_pan.update_drag(pos)
            self.update()
            return
        # Hover hit-test
        if self._hierarchy is not None:
            label = self._hierarchy_hit_test(pos)
        else:
            label = self._facies_layer.hit_test_polygon(pos, self._viewport)
        if label != self._current_hover:
            self._current_hover = label
            self.polygon_hovered.emit(label or "")
        if label:
            QToolTip.showText(event.globalPosition().toPoint(), label, self)
        else:
            QToolTip.hideText()
```

Replace `mouseReleaseEvent`:

```python
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._edit_mode:
                cmd = self._edit_engine.handle_mouse_release(
                    QPointF(event.position()), self._viewport, event.button())
                if cmd is not None:
                    self._undo_mgr.execute(cmd, self._topology_model)
                    self._rebuild_topology_paths()
                    self.update()
                return
            self._zoom_pan.end_drag()
```

Add double-click handler:

```python
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._edit_mode and event.button() == Qt.MouseButton.LeftButton:
            cmd = self._edit_engine.handle_double_click(
                QPointF(event.position()), self._viewport)
            if cmd is not None:
                self._undo_mgr.execute(cmd, self._topology_model)
                self._rebuild_topology_paths()
                self.update()
```

- [ ] **Step 4: Add keyboard shortcuts**

Add a `keyPressEvent` method:

```python
    def keyPressEvent(self, event) -> None:
        from PySide6.QtGui import QKeySequence
        if event.matches(QKeySequence.StandardKey.Undo):
            if self._undo_mgr.undo(self._topology_model):
                self._rebuild_topology_paths()
                self.update()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            if self._redo():
                self._rebuild_topology_paths()
                self.update()
            return
        if event.key() == Qt.Key.Key_E and not event.modifiers():
            self.edit_mode = not self.edit_mode
            return
        if event.key() == Qt.Key.Key_Delete and self._edit_mode:
            cmd = self._edit_engine.delete_selected_vertex(
                self._edit_overlay._hovered_vertex_id) if self._edit_overlay._hovered_vertex_id else None
            if cmd:
                self._undo_mgr.execute(cmd, self._topology_model)
                self._rebuild_topology_paths()
                self.update()
            return
        super().keyPressEvent(event)

    def _redo(self) -> bool:
        return self._undo_mgr.redo(self._topology_model)
```

- [ ] **Step 5: Add topology path rebuild helper**

```python
    def _rebuild_topology_paths(self) -> None:
        if self._topology_model is None:
            return
        dirty = self._topology_model.get_dirty_ids()
        if not dirty:
            return
        for layer in self._layers:
            if isinstance(layer, FaciesPolygonsLayer):
                layer.set_topology_model(self._topology_model)
                layer.rebuild_dirty_paths(dirty)
        self._topology_model.clear_dirty()
```

- [ ] **Step 6: Update __init__.py exports**

```python
"""geoviz_paleo_map — QPainter-based paleogeographic map visualization for PySide6."""
from geoviz_paleo_map.canvas import PaleoMapCanvas
from geoviz_paleo_map.hierarchy import FaciesHierarchy
from geoviz_paleo_map.floating_slider import FloatingScaleSlider
from geoviz_paleo_map.locked_panel import LockedObjectsPanel
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder
from geoviz_paleo_map.edit_engine import EditEngine
from geoviz_paleo_map.edit_commands import UndoManager

__all__ = [
    "PaleoMapCanvas", "FaciesHierarchy", "FloatingScaleSlider",
    "LockedObjectsPanel", "TopologyModel", "TopologyBuilder",
    "EditEngine", "UndoManager",
]
```

- [ ] **Step 7: Verify existing tests still pass**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py packages/geoviz_paleo_map/geoviz_paleo_map/__init__.py
git commit -m "feat(paleo): wire edit mode into PaleoMapCanvas with keyboard shortcuts"
```

---

### Task 11: Context Menu for Edit Mode

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py`

- [ ] **Step 1: Extend contextMenuEvent for edit mode actions**

Replace the existing `contextMenuEvent` method. Add edit-mode actions when edit mode is active:

```python
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        pos = QPointF(event.pos())
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 11px;
                color: #334155;
            }
            QMenu::item:selected {
                background-color: #f1f5f9;
                color: #0f172a;
            }
        """)

        if self._edit_mode and self._topology_model is not None:
            # Edit mode context menu
            vid = self._edit_overlay.hit_test_vertex(pos, self._viewport)
            if vid is not None:
                act_del_v = QAction("删除节点", self)
                act_del_v.triggered.connect(lambda: self._context_delete_vertex(vid))
                menu.addAction(act_del_v)
                menu.addSeparator()

            selected = self._edit_engine.selected_id
            if selected:
                act_del_p = QAction("删除多边形", self)
                act_del_p.triggered.connect(self._context_delete_polygon)
                menu.addAction(act_del_p)

                act_edit_attr = QAction("编辑属性...", self)
                act_edit_attr.triggered.connect(lambda: self._context_edit_attributes(selected))
                menu.addAction(act_edit_attr)
        else:
            # View mode context menu (existing hierarchy lock behavior)
            if self._hierarchy is None:
                menu.exec(event.globalPos())
                return

            feature_id = self._hierarchy_hit_test_id(pos)
            level_labels = {"facies": "相", "sub_facies": "亚相", "micro_facies": "微相"}

            if feature_id:
                node = self._hierarchy.get_node(feature_id)
                if node is not None:
                    root_node = self._find_root_node(feature_id)
                    active_lock_res = self._find_active_lock_in_subtree(root_node) if root_node is not None else None

                    if active_lock_res is not None:
                        locked_fid, lock_lvl = active_lock_res
                        locked_node = self._hierarchy.get_node(locked_fid)
                        if locked_node is not None:
                            display_name = locked_node.feature.display_name
                            lvl_lbl = level_labels.get(locked_node.feature.level, locked_node.feature.level)
                            act_unlock = QAction(f"解除锁定: {display_name} ({lvl_lbl})", self)
                            act_unlock.triggered.connect(lambda: self.toggle_lock(locked_fid))
                            menu.addAction(act_unlock)
                    else:
                        display_name = node.feature.display_name
                        lvl_lbl = level_labels.get(node.feature.level, node.feature.level)
                        act_lock = QAction(f"锁定层级: {display_name} ({lvl_lbl})", self)
                        act_lock.triggered.connect(lambda: self.toggle_lock(feature_id))
                        menu.addAction(act_lock)
                    menu.addSeparator()

            panel_visible = self._locked_panel.isVisible()
            act_toggle = QAction("显示锁定层级面板" if not panel_visible else "隐藏锁定层级面板", self)
            act_toggle.triggered.connect(self._toggle_locked_panel)
            menu.addAction(act_toggle)

        menu.exec(event.globalPos())

    def _context_delete_vertex(self, vid: int) -> None:
        cmd = self._edit_engine.delete_selected_vertex(vid)
        if cmd:
            self._undo_mgr.execute(cmd, self._topology_model)
            self._rebuild_topology_paths()
            self.update()

    def _context_delete_polygon(self) -> None:
        cmd = self._edit_engine.delete_selected_polygon()
        if cmd:
            self._undo_mgr.execute(cmd, self._topology_model)
            self._rebuild_topology_paths()
            self.selection_changed.emit("")
            self.update()

    def _context_edit_attributes(self, feature_id: str) -> None:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
        ref = self._topology_model.get_feature(feature_id) if self._topology_model else None
        if ref is None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑属性")
        form = QFormLayout(dlg)
        facies_input = QLineEdit(ref.properties.get("facies", ""))
        name_input = QLineEdit(ref.properties.get("name", ""))
        boundary_combo = QComboBox()
        boundary_combo.addItems(["无", "实测界线", "推测界线", "断层"])
        bt = ref.properties.get("boundary_type")
        boundary_combo.setCurrentText({"confirmed": "实测界线", "inferred": "推测界线", "fault": "断层"}.get(bt, "无"))
        form.addRow("相名:", facies_input)
        form.addRow("显示名:", name_input)
        form.addRow("界线类型:", boundary_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        old_props = dict(ref.properties)
        new_props = dict(ref.properties)
        new_props["facies"] = facies_input.text()
        new_props["name"] = name_input.text()
        bt_map = {"实测界线": "confirmed", "推测界线": "inferred", "断层": "fault"}
        new_props["boundary_type"] = bt_map.get(boundary_combo.currentText())
        from geoviz_paleo_map.edit_commands import EditAttributesCmd
        cmd = EditAttributesCmd(feature_id, old_props, new_props)
        self._undo_mgr.execute(cmd, self._topology_model)
        self.update()
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/canvas.py
git commit -m "feat(paleo): add edit-mode context menu (delete vertex/polygon, edit attributes)"
```

---

## Phase 5: Save and Export

### Task 12: Save/Export Module

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py`

- [ ] **Step 1: Implement save and export functions**

```python
# packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py
"""Save topology to GeoJSON and export canvas as SVG/PDF/PNG."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap

from geoviz_paleo_map.topology import TopologyModel


def save_geojson(model: TopologyModel, file_path: str | Path) -> None:
    """Save the topology model to a GeoJSON file."""
    data = model.to_geojson()
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    model.is_dirty = False


def save_hierarchy_geojson(model: TopologyModel, source_files: dict[str, str]) -> None:
    """Save features back to their respective source files by level.

    Args:
        model: The topology model containing all features.
        source_files: Mapping of level name → file path.
    """
    features_by_file: dict[str, list[dict]] = {}
    data = model.to_geojson()

    for feat in data.get("features", []):
        props = feat.get("properties", {})
        level = props.get("level", "facies")
        file_path = source_files.get(level)
        if file_path:
            features_by_file.setdefault(file_path, []).append(feat)

    for file_path, features in features_by_file.items():
        collection = {"type": "FeatureCollection", "features": features}
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)

    model.is_dirty = False


def export_png(widget, file_path: str | Path) -> None:
    """Export the canvas widget as PNG."""
    pixmap = widget.grab()
    pixmap.save(str(file_path), "PNG")


def export_pdf(widget, file_path: str | Path) -> None:
    """Export the canvas widget as PDF."""
    from PySide6.QtGui import QPageSize, QPageLayout
    from PySide6.QtPrintSupport import QPrinter

    pixmap = widget.grab()
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFileName(str(file_path))
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    painter = QPainter(printer)
    page_rect = printer.pageRect(QPrinter.DevicePixel)
    scaled = pixmap.scaled(page_rect.size(), Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
    x = (page_rect.width() - scaled.width()) // 2
    y = (page_rect.height() - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()


def export_svg(widget, file_path: str | Path) -> None:
    """Export the canvas widget as SVG (raster embedded in SVG wrapper)."""
    import base64
    import io

    pixmap = widget.grab()
    buffer = io.BytesIO()
    pixmap.save(buffer, "PNG")
    b64 = base64.b64encode(buffer.getvalue()).decode()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{pixmap.width()}" height="{pixmap.height()}">'
        f'<image href="data:image/png;base64,{b64}" '
        f'width="{pixmap.width()}" height="{pixmap.height()}"/>'
        f'</svg>'
    )
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(svg)
```

- [ ] **Step 2: Verify import works**

Run: `python -c "from geoviz_paleo_map.save_export import save_geojson, export_png; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py
git commit -m "feat(paleo): add save_export module for GeoJSON save and SVG/PDF/PNG export"
```

---

## Phase 6: Page-Level Integration

### Task 13: Toolbar and Signal Wiring in PaleoMapPage

**Files:**
- Modify: `src/pages/paleo_map/page.py`

- [ ] **Step 1: Add edit mode toggle button and save/export buttons to toolbar**

After the existing `export_btn` setup in the toolbar section, add:

```python
        self._edit_btn = QPushButton("编辑模式")
        self._edit_btn.setCheckable(True)
        self._edit_btn.setToolTip("切换编辑模式 (E)")
        self._edit_btn.setStyleSheet(
            "QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;"
            "border-radius:4px;padding:6px 12px;}"
            "QPushButton:hover{background:#e2e8f0;}"
            "QPushButton:checked{background:#dbeafe;color:#1d4ed8;border-color:#93c5fd;}"
        )
        self._edit_btn.clicked.connect(self._toggle_edit_mode)

        self._save_btn = QPushButton("保存")
        self._save_btn.setToolTip("保存编辑 (Ctrl+S)")
        self._save_btn.setStyleSheet(
            "QPushButton{background:#059669;color:#fff;border:none;border-radius:4px;"
            "padding:6px 14px;font-weight:600;}"
            "QPushButton:hover{background:#047857;}"
        )
        self._save_btn.clicked.connect(self._on_save_clicked)
        self._save_btn.setVisible(False)

        tb_layout.addWidget(self._edit_btn)
        tb_layout.addWidget(self._save_btn)
```

- [ ] **Step 2: Add edit mode toggle and save logic**

Add methods to `PaleoMapPage`:

```python
    def _toggle_edit_mode(self, checked: bool) -> None:
        self.map_view.edit_mode = checked
        self._save_btn.setVisible(checked)

    def _on_save_clicked(self) -> None:
        model = self.map_view.topology_model
        if model is None:
            return
        from geoviz_paleo_map.save_export import save_geojson, save_hierarchy_geojson
        if self._hierarchies and self._current_period in self._hierarchies:
            # Hierarchy mode: save each level to its source file
            # For now, use Save As since we don't track source files in the page
            self._save_as(model)
        else:
            self._save_as(model)

    def _save_as(self, model) -> None:
        from geoviz_paleo_map.save_export import save_geojson
        path, _ = QFileDialog.getSaveFileName(
            self, "保存 GeoJSON", "paleo_edited.geojson", "GeoJSON (*.geojson *.json)")
        if path:
            save_geojson(model, path)
            QMessageBox.information(self, "保存成功", f"已保存到: {path}")
```

- [ ] **Step 3: Connect edit mode signals for status feedback**

Add after the canvas setup:

```python
        self.map_view.edit_mode_changed.connect(self._on_edit_mode_changed)
        self.map_view.selection_changed.connect(self._on_selection_changed)

    def _on_edit_mode_changed(self, active: bool) -> None:
        self._edit_btn.setChecked(active)

    def _on_selection_changed(self, feature_id: str) -> None:
        pass  # Future: update properties panel
```

- [ ] **Step 4: Verify the page loads and toolbar renders**

Run: `pytest tests/test_paleo_map_canvas.py -v`
Expected: PASS (existing tests unaffected)

- [ ] **Step 5: Commit**

```bash
git add src/pages/paleo_map/page.py
git commit -m "feat(paleo): add edit mode toggle and save button to PaleoMapPage toolbar"
```

---

### Task 14: Hierarchy — get_children Method

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/hierarchy.py`

- [ ] **Step 1: Add get_children method**

Add to `FaciesHierarchy` class, after `get_ancestors`:

```python
    def get_children(self, feature_id: str) -> list[FaciesFeature]:
        """Get direct children of a feature."""
        node = self._by_id.get(feature_id)
        if node is None:
            return []
        return [child.feature for child in node.children]
```

- [ ] **Step 2: Verify**

Run: `python -c "from geoviz_paleo_map.hierarchy import FaciesHierarchy; print(hasattr(FaciesHierarchy, 'get_children'))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_paleo_map/geoviz_paleo_map/hierarchy.py
git commit -m "feat(paleo): add get_children method to FaciesHierarchy"
```

---

## Final Verification

### Task 15: Run Full Test Suite

- [ ] **Step 1: Run all tests**

Run: `pytest tests/ -v`

Expected: All tests pass, including:
- `test_topology.py` (13 tests)
- `test_edit_commands.py` (12 tests)
- `test_paleo_map_canvas.py` (5 tests)
- `test_paleo_loader.py` (existing)
- `test_paleo_map_visual_parity.py` (existing)

- [ ] **Step 2: Run linting/type checking if configured**

Run: `python -m py_compile packages/geoviz_paleo_map/geoviz_paleo_map/topology.py && python -m py_compile packages/geoviz_paleo_map/geoviz_paleo_map/edit_commands.py && python -m py_compile packages/geoviz_paleo_map/geoviz_paleo_map/edit_engine.py && python -m py_compile packages/geoviz_paleo_map/geoviz_paleo_map/edit_overlay.py && python -m py_compile packages/geoviz_paleo_map/geoviz_paleo_map/save_export.py`
Expected: No errors

- [ ] **Step 3: Commit any fixes if needed**

---

## Summary

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | 1–4 | Topology data model, TopologyModel, TopologyBuilder |
| 2 | 5 | EditCommand hierarchy, UndoManager |
| 3 | 6–9 | EditOverlayLayer, FaciesPolygonsLayer mods, ZoomPanHandler, EditEngine |
| 4 | 10–11 | Canvas integration, keyboard shortcuts, context menu |
| 5 | 12 | Save/export module |
| 6 | 13–14 | Page-level toolbar, hierarchy get_children |
| Final | 15 | Full test suite verification |
