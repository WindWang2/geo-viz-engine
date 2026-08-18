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


def test_rebuild_dirty_paths_preserves_ring_structure():
    """#837: rebuild_dirty_paths extracted rings via toFillPolygons(), which
    merges the outer ring and hole subpaths into a single polygon joined by
    straight connector edges — the rebuilt LOD rings drew fake diagonal
    borders across any edited feature with a hole, and MultiPolygon parts
    collapsed into one. Ring count and per-ring vertex counts must survive
    a rebuild unchanged (no connector-edge vertices)."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩", "name": "砂岩A"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]],          # outer
                    [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]],          # hole
                ],
            },
        },
    ]
    model = TopologyBuilder.from_features(features)
    layer = FaciesPolygonsLayer(features, FaciesStyleResolver())
    layer.set_topology_model(model)

    item = next(i for i in layer._items if i.feature_id == "A")
    assert len(item.polygons) == 2, "precondition: outer ring + hole"
    expected_counts = [len(r) for r in item.polygons]

    # Move one outer-ring vertex, then rebuild (the post-edit path).
    ring = model._features["A"].rings[0]
    model.move_vertex(ring.vertex_ids[1], 6.0, 0.0)
    layer.rebuild_dirty_paths({"A"})

    assert len(item.polygons) == len(expected_counts), (
        "ring structure must survive a rebuild — toFillPolygons would merge "
        "outer + hole into one connector-edge polygon"
    )
    for ring_pts, expected in zip(item.polygons, expected_counts):
        assert len(ring_pts) == expected, (
            "per-ring vertex count unchanged — no connector-edge vertices"
        )
    # The moved vertex must appear in the outer ring, and the hole ring must
    # still be a standalone ring (a hole-only point, not a connector).
    outer_pts = np.concatenate(item.polygons)
    assert np.any(np.all(np.isclose(outer_pts, (6.0, 0.0)), axis=1))


def test_rebuild_dirty_paths_preserves_multipolygon_parts():
    """#837: MultiPolygon ring structure must survive a rebuild. The old
    toFillPolygons() extraction merged a part's hole subpath into its outer
    ring with connector edges (11 points for 5+5), so part structure was lost.
    Rebuild must keep every ring standalone (outer + hole + second part)."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩", "name": "砂岩A"},
            "geometry": {
                "type": "MultiPolygon",
                "coordinates": [
                    [  # part 1: square with a hole
                        [[0, 0], [5, 0], [5, 5], [0, 5], [0, 0]],
                        [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]],
                    ],
                    [  # part 2: plain square
                        [[10, 10], [15, 10], [15, 15], [10, 15], [10, 10]],
                    ],
                ],
            },
        },
    ]
    model = TopologyBuilder.from_features(features)
    layer = FaciesPolygonsLayer(features, FaciesStyleResolver())
    layer.set_topology_model(model)

    # Precondition: rebuilt polygons must contain the standalone rings
    # (outer 5 + hole 5 + part2 5), not a merged connector-edge polygon.
    expected_counts = [5, 5, 5]

    model.move_vertex(model._features["A"].rings[0].vertex_ids[1], 6.0, 0.0)
    layer.rebuild_dirty_paths({"A"})

    item = next(i for i in layer._items if i.feature_id == "A")
    assert [len(r) for r in item.polygons] == expected_counts, (
        "every ring (outer, hole, second part) must stay standalone — "
        "toFillPolygons would merge part 1's hole into an 11-point "
        "connector-edge ring"
    )
    all_pts = np.concatenate(item.polygons)
    assert np.any(np.all(np.isclose(all_pts, (6.0, 0.0)), axis=1))


def test_rebuild_dirty_paths_rebuilds_level_quadtrees():
    """#853: the level-border quadtrees kept their pre-edit spatial
    partitioning after an edit — only the fill quadtree was rebuilt — so a
    moved feature's border stayed in the old tree node and the border
    vanished under pan/zoom culling. After a rebuild the level tree must
    answer queries at the feature's NEW location and not the old one."""
    from geoviz_paleo_map.layers.facies_polygons import QuadtreeNode

    features = _single_feature()  # A: (0,0)-(5,10), B: (5,0)-(10,10)
    model = TopologyBuilder.from_features(features)
    layer = FaciesPolygonsLayer(features, FaciesStyleResolver())
    layer.set_topology_model(model)

    # Realistic subdivided tree: item A lives inside the SW child cell.
    root = QuadtreeNode((0.0, 0.0, 100.0, 100.0), max_depth=1)
    root.subdivide()
    item_a = next(i for i in layer._items if i.feature_id == "A")
    root.insert(item_a)
    assert any(item_a in child.items for child in root.children), (
        "precondition: item must sit in a child cell so stale partitioning "
        "can be observed"
    )
    layer._level_quadtrees = {"facies": root}

    ring = model._features["A"].rings[0]
    for i, vid in enumerate(ring.vertex_ids):
        model.move_vertex(vid, 55.0 + i, 55.0 + i)
    layer.rebuild_dirty_paths({"A"})

    found_new = []
    rebuilt = layer._level_quadtrees["facies"]
    rebuilt.query((55.0, 55.0, 65.0, 65.0), found_new)
    assert item_a in found_new, (
        "rebuilt level tree must find the moved border at its new location"
    )
    found_old = []
    rebuilt.query((-5.0, -5.0, 15.0, 15.0), found_old)
    assert item_a not in found_old, (
        "moved border must be culled from its old location"
    )
