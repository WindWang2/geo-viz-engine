import pytest
from PySide6.QtCore import Qt, QPointF
from geoviz_paleo_map import PaleoMapCanvas, FaciesHierarchy, LockedObjectsPanel


def test_locking_behavior(qtbot):
    # Setup hierarchy structure: Facies A -> SubFacies B
    features = [
        {
            "type": "Feature",
            "properties": {"id": "facies_a", "name": "相A", "facies": "砂岩", "level": "facies"},
            "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]]]}
        },
        {
            "type": "Feature",
            "properties": {"id": "sub_b", "name": "亚相B", "facies": "砂岩", "level": "sub_facies", "parent_id": "facies_a"},
            "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]}
        }
    ]

    canvas = PaleoMapCanvas()
    canvas.resize(1200, 800)
    qtbot.addWidget(canvas)

    hier = FaciesHierarchy.from_features(features)
    canvas.load_hierarchy(hier, "测试时期")

    # 1. By default, zoom to sub_facies (set zoom=9.0, larger than transition thresholds)
    canvas._viewport.zoom = 9.0
    active_lvl = canvas._resolve_level_name()
    assert active_lvl in ("sub_facies", "micro_facies")

    # Verify B is shown when A is NOT locked
    canvas._update_active_layers()
    from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
    visible_ids = {item.feature_id for layer in canvas._layers if isinstance(layer, FaciesPolygonsLayer) for item in layer._items}
    assert "sub_b" in visible_ids
    assert "facies_a" not in visible_ids

    # 2. Lock parent "facies_a"
    canvas.toggle_lock("facies_a")
    assert "facies_a" in canvas._locked_ids

    # Verify parent "facies_a" is now shown, and child "sub_b" is hidden!
    canvas._update_active_layers()
    visible_ids_locked = {item.feature_id for layer in canvas._layers if isinstance(layer, FaciesPolygonsLayer) for item in layer._items}
    assert "facies_a" in visible_ids_locked
    assert "sub_b" not in visible_ids_locked

    # 3. Unlock parent "facies_a"
    canvas.toggle_lock("facies_a")
    assert "facies_a" not in canvas._locked_ids

    # Verify B is shown again
    canvas._update_active_layers()
    visible_ids_unlocked = {item.feature_id for layer in canvas._layers if isinstance(layer, FaciesPolygonsLayer) for item in layer._items}
    assert "sub_b" in visible_ids_unlocked
    assert "facies_a" not in visible_ids_unlocked


def test_combobox_lock_level_and_distinct_labels(qtbot):
    from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
    from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer

    # Setup hierarchy structure: Facies A -> SubFacies B
    features = [
        {
            "type": "Feature",
            "properties": {"id": "facies_a", "name": "相A", "facies": "砂岩", "level": "facies"},
            "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [12, 10], [12, 12], [10, 12], [10, 10]]]}
        },
        {
            "type": "Feature",
            "properties": {"id": "sub_b", "name": "亚相B", "facies": "砂岩", "level": "sub_facies", "parent_id": "facies_a"},
            "geometry": {"type": "Polygon", "coordinates": [[[10, 10], [11, 10], [11, 11], [10, 11], [10, 10]]]}
        }
    ]

    canvas = PaleoMapCanvas()
    canvas.resize(1200, 800)
    qtbot.addWidget(canvas)

    hier = FaciesHierarchy.from_features(features)
    canvas.load_hierarchy(hier, "测试时期")

    # Lock facies_a
    canvas.toggle_lock("facies_a")
    assert canvas._locked_ids["facies_a"] == "facies"

    # Verify labels layer contains a locked label with is_locked=True and the lock icon text
    canvas._update_active_layers()
    labels_layer = next(layer for layer in canvas._layers if isinstance(layer, RegionLabelsLayer))
    assert any(item.is_locked and item.feature_id == "facies_a" for item in labels_layer._items)

    # Change lock level to sub_facies
    canvas.update_lock_level("facies_a", "sub_facies")
    assert canvas._locked_ids["facies_a"] == "sub_facies"

    # Verify that sub_b is now shown and is_locked is True for it
    canvas._update_active_layers()
    visible_ids_locked = {item.feature_id for layer in canvas._layers if isinstance(layer, FaciesPolygonsLayer) for item in layer._items}
    assert "sub_b" in visible_ids_locked
    assert "facies_a" not in visible_ids_locked

    labels_layer2 = next(layer for layer in canvas._layers if isinstance(layer, RegionLabelsLayer))
    assert any(item.is_locked and item.feature_id == "sub_b" and item.level == "sub_facies" for item in labels_layer2._items)


