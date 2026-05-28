"""Tests for FaciesHierarchy.get_children."""
from __future__ import annotations

import pytest
from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesFeature


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_hierarchy() -> FaciesHierarchy:
    """A 3-level hierarchy: root -> child1, child2 -> grandchild."""
    features = [
        FaciesFeature(
            id="root", facies_name="三角洲", display_name="三角洲",
            level="facies", period="C1", parent_id=None,
            geometry={"type": "Polygon", "coordinates": [[[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]]},
        ),
        FaciesFeature(
            id="child1", facies_name="三角洲前缘", display_name="三角洲前缘",
            level="sub_facies", period="C1", parent_id="root",
            geometry={"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 10], [0, 10], [0, 0]]]},
        ),
        FaciesFeature(
            id="child2", facies_name="三角洲平原", display_name="三角洲平原",
            level="sub_facies", period="C1", parent_id="root",
            geometry={"type": "Polygon", "coordinates": [[[5, 0], [10, 0], [10, 10], [5, 10], [5, 0]]]},
        ),
        FaciesFeature(
            id="grandchild", facies_name="河口坝", display_name="河口坝",
            level="micro_facies", period="C1", parent_id="child1",
            geometry={"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 5], [0, 5], [0, 0]]]},
        ),
    ]
    return FaciesHierarchy._build_tree(features)


# ---------------------------------------------------------------------------
# get_children
# ---------------------------------------------------------------------------

def test_get_children_returns_direct_children():
    hier = _make_hierarchy()
    children = hier.get_children("root")
    ids = [c.id for c in children]
    assert "child1" in ids
    assert "child2" in ids
    assert len(children) == 2


def test_get_children_returns_nested_children():
    hier = _make_hierarchy()
    children = hier.get_children("child1")
    assert len(children) == 1
    assert children[0].id == "grandchild"
    assert children[0].facies_name == "河口坝"


def test_get_children_leaf_returns_empty():
    hier = _make_hierarchy()
    children = hier.get_children("grandchild")
    assert children == []


def test_get_children_unknown_id_returns_empty():
    hier = _make_hierarchy()
    children = hier.get_children("nonexistent")
    assert children == []


def test_get_children_returns_facies_feature_objects():
    hier = _make_hierarchy()
    children = hier.get_children("root")
    for child in children:
        assert isinstance(child, FaciesFeature)
        assert child.period == "C1"
