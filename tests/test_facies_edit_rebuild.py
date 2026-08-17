"""Regression tests for #544/#549: edit rebuilds must refresh rendered geometry."""
import numpy as np

from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.topology import TopologyBuilder


def _single_feature():
    return [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩", "name": "砂岩A"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0, 0], [5, 0], [5, 10], [0, 10], [0, 0]]],
            },
        },
        {
            "type": "Feature",
            "properties": {"id": "B", "facies": "泥岩", "name": "泥岩B"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[5, 0], [10, 0], [10, 10], [5, 10], [5, 0]]],
            },
        },
    ]


def test_rebuild_dirty_paths_refreshes_polygon_rings():
    """#544: rebuild_dirty_paths must refresh item.polygons (the raw rings the
    screen-path LOD builder reads), not just item.path."""
    features = _single_feature()
    model = TopologyBuilder.from_features(features)
    layer = FaciesPolygonsLayer(features, FaciesStyleResolver())
    layer.set_topology_model(model)

    item = next(i for i in layer._items if i.feature_id == "A")
    old_polys = [r.copy() for r in item.polygons]
    old_first = np.min(old_polys[0], axis=0).copy() if old_polys else None

    # Move the first vertex of ring 0 to (50, 50).
    ring = model._features["A"].rings[0]
    vid = ring.vertex_ids[0]
    model.move_vertex(vid, 50.0, 50.0)
    layer.rebuild_dirty_paths({"A"})

    assert item.polygons, "polygons must remain populated after rebuild"
    all_pts = np.concatenate(item.polygons)
    assert np.any(np.all(np.isclose(all_pts, (50.0, 50.0)), axis=1)), (
        "the moved vertex must appear in the refreshed rings"
    )


def test_rebuild_dirty_paths_refreshes_style_keys_from_model():
    """#549: attribute edits must propagate to the rendered facies/pen keys."""
    features = _single_feature()
    model = TopologyBuilder.from_features(features)
    layer = FaciesPolygonsLayer(features, FaciesStyleResolver())
    layer.set_topology_model(model)

    item = next(i for i in layer._items if i.feature_id == "A")
    assert item.facies_name == "砂岩"

    ref = model.get_feature("A")
    ref.properties["facies"] = "石灰岩"
    ref.properties["boundary_type"] = "fault"
    model.mark_feature_dirty("A")
    layer.rebuild_dirty_paths({"A"})

    assert item.facies_name == "石灰岩"
    assert item.boundary_kind == "fault"


def test_rebuild_dirty_paths_updates_hierarchy_border_items():
    """#544: hierarchy level-quadtree border items must follow edits too."""
    features = _single_feature()
    model = TopologyBuilder.from_features(features)
    layer = FaciesPolygonsLayer(features, FaciesStyleResolver())
    layer.set_topology_model(model)
    # Synthetic hierarchy quadtree referencing the same feature ids.
    item_a = next(i for i in layer._items if i.feature_id == "A")
    from geoviz_paleo_map.layers.facies_polygons import QuadtreeNode

    tree = QuadtreeNode((0.0, 0.0, 100.0, 100.0))
    tree.insert(item_a)
    layer._level_quadtrees = {"facies": tree}

    ring = model._features["A"].rings[0]
    model.move_vertex(ring.vertex_ids[1], 60.0, 0.0)
    layer.rebuild_dirty_paths({"A"})

    walked = list(FaciesPolygonsLayer._walk_items(tree))
    assert len(walked) == 1
    assert walked[0].polygons, "hierarchy border item must carry refreshed rings"
    all_pts = np.concatenate(walked[0].polygons)
    assert np.any(np.all(np.isclose(all_pts, (60.0, 0.0)), axis=1))
