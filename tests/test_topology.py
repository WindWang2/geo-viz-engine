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


def test_model_build_path():
    model = TopologyModel()
    v0 = model.add_vertex(0.0, 0.0)
    v1 = model.add_vertex(1.0, 0.0)
    v2 = model.add_vertex(0.5, 1.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v0.id])
    model.add_feature("tri", [ring], "facies", None, None, {})
    path = model.build_path("tri")
    assert path is not None
    assert not path.isEmpty()


def test_model_to_geojson_roundtrip():
    model = TopologyModel()
    v0 = model.add_vertex(10.0, 20.0)
    v1 = model.add_vertex(30.0, 20.0)
    v2 = model.add_vertex(30.0, 40.0)
    v3 = model.add_vertex(10.0, 40.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v3.id, v0.id])
    model.add_feature("sq", [ring], "facies", "parent1", "src.geojson", {"name": "square"})
    geo = model.to_geojson()
    assert geo["type"] == "FeatureCollection"
    assert len(geo["features"]) == 1
    feat = geo["features"][0]
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Polygon"
    assert feat["properties"]["id"] == "sq"
    assert feat["properties"]["level"] == "facies"
    assert feat["properties"]["parent_id"] == "parent1"
    coords = feat["geometry"]["coordinates"][0]
    assert len(coords) == 5  # closed ring


def test_model_dirty_tracking():
    model = TopologyModel()
    v0 = model.add_vertex(0.0, 0.0)
    v1 = model.add_vertex(1.0, 0.0)
    v2 = model.add_vertex(0.5, 1.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v0.id])
    model.add_feature("f1", [ring], "facies", None, None, {})
    assert "f1" in model.get_dirty_ids()
    model.clear_dirty()
    assert len(model.get_dirty_ids()) == 0


# --- TopologyBuilder tests ---

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
