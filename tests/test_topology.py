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
