"""Tests for save_export — GeoJSON save and hierarchy save."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder, RingRef
from geoviz_paleo_map.save_export import save_geojson, save_hierarchy_geojson


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_model_two_levels() -> TopologyModel:
    """Model with two features at different levels."""
    features = [
        {
            "type": "Feature",
            "properties": {"id": "A", "facies": "砂岩", "level": "facies", "name": "砂岩A"},
            "geometry": {"type": "Polygon", "coordinates": [[[0, 0], [5, 0], [5, 10], [0, 10], [0, 0]]]},
        },
        {
            "type": "Feature",
            "properties": {"id": "B", "facies": "泥岩", "level": "sub_facies", "name": "泥岩B"},
            "geometry": {"type": "Polygon", "coordinates": [[[5, 0], [10, 0], [10, 10], [5, 10], [5, 0]]]},
        },
    ]
    return TopologyBuilder.from_features(features)


def _make_single_feature_model() -> TopologyModel:
    """Model with one feature."""
    model = TopologyModel()
    v0 = model.add_vertex(100.0, 20.0)
    v1 = model.add_vertex(110.0, 20.0)
    v2 = model.add_vertex(110.0, 30.0)
    v3 = model.add_vertex(100.0, 30.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v3.id, v0.id])
    model.add_feature("sq", [ring], "facies", None, None,
                      {"facies": "砂岩", "name": "方形"})
    return model


# ---------------------------------------------------------------------------
# save_geojson
# ---------------------------------------------------------------------------

def test_save_geojson_writes_valid_json(tmp_path):
    model = _make_single_feature_model()
    out = tmp_path / "test.geojson"
    save_geojson(model, out)
    assert out.exists()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"


def test_save_geojson_feature_count(tmp_path):
    model = _make_model_two_levels()
    out = tmp_path / "test.geojson"
    save_geojson(model, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["features"]) == 2


def test_save_geojson_feature_properties(tmp_path):
    model = _make_single_feature_model()
    out = tmp_path / "test.geojson"
    save_geojson(model, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    feat = data["features"][0]
    assert feat["properties"]["id"] == "sq"
    assert feat["properties"]["facies"] == "砂岩"


def test_save_geojson_geometry_type(tmp_path):
    model = _make_single_feature_model()
    out = tmp_path / "test.geojson"
    save_geojson(model, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    feat = data["features"][0]
    assert feat["geometry"]["type"] == "Polygon"
    coords = feat["geometry"]["coordinates"][0]
    assert len(coords) == 5  # closed ring


def test_save_geojson_clears_dirty(tmp_path):
    model = _make_single_feature_model()
    model.mark_dirty()
    assert model.is_dirty
    out = tmp_path / "test.geojson"
    save_geojson(model, out)
    assert not model.is_dirty


def test_save_geojson_unicode_content(tmp_path):
    model = TopologyModel()
    v0 = model.add_vertex(100.0, 20.0)
    v1 = model.add_vertex(110.0, 20.0)
    v2 = model.add_vertex(105.0, 30.0)
    ring = RingRef(vertex_ids=[v0.id, v1.id, v2.id, v0.id])
    model.add_feature("cn", [ring], "facies", None, None,
                      {"facies": "三角洲前缘", "name": "河口坝"})
    out = tmp_path / "cn.geojson"
    save_geojson(model, out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["features"][0]["properties"]["facies"] == "三角洲前缘"


# ---------------------------------------------------------------------------
# save_hierarchy_geojson
# ---------------------------------------------------------------------------

def test_save_hierarchy_geojson_splits_by_level(tmp_path):
    model = _make_model_two_levels()
    facies_path = str(tmp_path / "facies.geojson")
    sub_path = str(tmp_path / "sub_facies.geojson")
    source_files = {"facies": facies_path, "sub_facies": sub_path}

    save_hierarchy_geojson(model, source_files)

    facies_data = json.loads(Path(facies_path).read_text(encoding="utf-8"))
    sub_data = json.loads(Path(sub_path).read_text(encoding="utf-8"))

    assert len(facies_data["features"]) == 1
    assert facies_data["features"][0]["properties"]["id"] == "A"
    assert len(sub_data["features"]) == 1
    assert sub_data["features"][0]["properties"]["id"] == "B"


def test_save_hierarchy_geojson_valid_structure(tmp_path):
    model = _make_model_two_levels()
    facies_path = str(tmp_path / "facies.geojson")
    sub_path = str(tmp_path / "sub_facies.geojson")
    source_files = {"facies": facies_path, "sub_facies": sub_path}

    save_hierarchy_geojson(model, source_files)

    for fp in [facies_path, sub_path]:
        data = json.loads(Path(fp).read_text(encoding="utf-8"))
        assert data["type"] == "FeatureCollection"
        for feat in data["features"]:
            assert feat["type"] == "Feature"
            assert feat["geometry"]["type"] == "Polygon"


def test_save_hierarchy_geojson_clears_dirty(tmp_path):
    model = _make_model_two_levels()
    model.mark_dirty()
    facies_path = str(tmp_path / "facies.geojson")
    sub_path = str(tmp_path / "sub_facies.geojson")
    source_files = {"facies": facies_path, "sub_facies": sub_path}

    save_hierarchy_geojson(model, source_files)
    assert not model.is_dirty


def test_save_hierarchy_geojson_skips_unmapped_level(tmp_path):
    """Features with a level not in source_files are not written."""
    model = _make_model_two_levels()
    # Only provide mapping for facies, not sub_facies
    facies_path = str(tmp_path / "facies.geojson")
    source_files = {"facies": facies_path}

    save_hierarchy_geojson(model, source_files)

    facies_data = json.loads(Path(facies_path).read_text(encoding="utf-8"))
    assert len(facies_data["features"]) == 1
    # sub_facies file should NOT exist
    assert not (tmp_path / "sub_facies.geojson").exists()
