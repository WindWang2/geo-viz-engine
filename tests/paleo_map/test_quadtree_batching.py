import pytest
from PySide6.QtCore import QPointF
from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer, QuadtreeNode, _Item
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_quadtree_subdivision_and_query():
    # Construct a root node covering 0 to 100 on both axes
    root = QuadtreeNode((0.0, 0.0, 100.0, 100.0), depth=0, max_depth=3)

    # Insert items
    from PySide6.QtGui import QPainterPath
    dummy_path = QPainterPath()

    # Southwest quadrant (10, 10)
    item_sw = _Item(facies_name="砂岩", feature_id="SW", path=dummy_path, bbox=(5.0, 5.0, 15.0, 15.0), boundary_kind="confirmed")
    # Northeast quadrant (80, 80)
    item_ne = _Item(facies_name="泥岩", feature_id="NE", path=dummy_path, bbox=(75.0, 75.0, 85.0, 85.0), boundary_kind="inferred")
    # Central item overlapping grid lines (45 to 55) - should stay in parent
    item_center = _Item(facies_name="灰岩", feature_id="Center", path=dummy_path, bbox=(45.0, 45.0, 55.0, 55.0), boundary_kind="confirmed")

    root.insert(item_sw)
    root.insert(item_ne)
    root.insert(item_center)

    # Trigger a manual split to verify children distribution
    root.subdivide()

    assert root.children is not None
    # Sw quadrant child should contain item_sw
    sw_child = root.children[0]
    assert any(x.feature_id == "SW" for x in sw_child.items)

    # Ne quadrant child should contain item_ne
    ne_child = root.children[3]
    assert any(x.feature_id == "NE" for x in ne_child.items)

    # Center item should remain in parent root since it spans across subdivisions
    assert any(x.feature_id == "Center" for x in root.items)

    # Test query for SW quadrant only
    out = []
    root.query((0.0, 0.0, 30.0, 30.0), out)
    assert any(x.feature_id == "SW" for x in out)
    assert not any(x.feature_id == "NE" for x in out)


def test_style_batching_groups():
    # Test that multiple items of the same facies and boundary type are correctly grouped during paint
    engine = PatternEngine()
    resolver = FaciesStyleResolver(engine)

    features = [
        {
            "type": "Feature",
            "properties": {"name": "A", "facies": "砂岩", "boundary_type": "confirmed"},
            "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]]]}
        },
        {
            "type": "Feature",
            "properties": {"name": "B", "facies": "砂岩", "boundary_type": "confirmed"},
            "geometry": {"type": "Polygon", "coordinates": [[[20, 20], [22, 20], [22, 22], [20, 22], [20, 20]]]}
        },
        {
            "type": "Feature",
            "properties": {"name": "C", "facies": "泥岩", "boundary_type": "inferred"},
            "geometry": {"type": "Polygon", "coordinates": [[[30, 30], [32, 30], [32, 32], [30, 32], [30, 30]]]}
        }
    ]

    layer = FaciesPolygonsLayer(features, resolver)
    assert layer._quadtree_root is not None

    # Query with a large bbox covering everything (0 to 100)
    full_bbox = (0.0, 0.0, 100.0, 100.0)
    visible_items = []
    layer._quadtree_root.query(full_bbox, visible_items)
    assert len(visible_items) == 3

    # Check grouping logic
    groups = {}
    for item in visible_items:
        key = (item.facies_name, item.boundary_kind)
        groups.setdefault(key, []).append(item)

    # Group 1: 砂岩 + confirmed (should contain 2 items)
    assert len(groups[("砂岩", "confirmed")]) == 2
    # Group 2: 泥岩 + inferred (should contain 1 item)
    assert len(groups[("泥岩", "inferred")]) == 1
