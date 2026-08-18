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


def test_dangling_parent_id_is_promoted_to_root():
    """#680: a missing parent_id must not drop the feature from the tree."""
    poly = {"type": "Polygon", "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}
    features = [
        FaciesFeature(
            id="root", facies_name="三角洲", display_name="三角洲",
            level="facies", period="C1", parent_id=None, geometry=poly,
        ),
        FaciesFeature(
            id="orphan", facies_name="孤立亚相", display_name="孤立亚相",
            level="sub_facies", period="C1", parent_id="missing", geometry=poly,
        ),
    ]
    with pytest.warns(UserWarning, match="parent_id"):
        hier = FaciesHierarchy._build_tree(features)
    root_ids = [node.feature.id for node in hier.roots]
    assert "root" in root_ids
    assert "orphan" in root_ids
    assert hier.get_node("orphan") is not None

    from geoviz_paleo_map.topology import TopologyBuilder

    model = TopologyBuilder.from_hierarchy(hier)
    assert model.get_feature("orphan") is not None


def test_get_ancestors_terminates_on_cycle():
    """#853: a cyclic parent_id chain (hand-edited GeoJSON) previously
    infinite-looped inside get_ancestors and froze the UI; the walk must
    terminate with a bounded ancestor list."""
    hier = FaciesHierarchy.from_features([
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "A", "name": "A",
                           "level": "facies", "parent_id": "B"},
            "geometry": {"type": "Polygon", "coordinates": []},
        },
        {
            "type": "Feature",
            "properties": {"id": "B", "facies": "B", "name": "B",
                           "level": "facies", "parent_id": "A"},
            "geometry": {"type": "Polygon", "coordinates": []},
        },
    ])
    # Must return rather than hang.
    ancestors = hier.get_ancestors("A")
    assert 1 <= len(ancestors) <= 2
    # The display-label path (used by hover/context menus) must also finish.
    label = hier.get_hierarchy_label("A")
    assert label  # non-empty, built without freezing


def test_get_ancestors_self_loop_terminates():
    """#853: a feature whose parent_id is its own id must terminate too."""
    hier = FaciesHierarchy.from_features([
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "A", "name": "A",
                           "level": "facies", "parent_id": "A"},
            "geometry": {"type": "Polygon", "coordinates": []},
        },
    ])
    assert hier.get_ancestors("A") == []
