import json
import pytest
from src.data.paleo_loader import PaleoDataLoader


def test_load_csv_with_period_and_bbox(tmp_path):
    csv_content = "period,facies,boundary_type,lon_min,lon_max,lat_min,lat_max,name\n"
    csv_content += "寒武纪第二期,砂岩,confirmed,100,105,30,35,北部陆棚\n"
    csv_content += "寒武纪第二期,深水盆地,inferred,100,105,25,30,南部盆地\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    loader = PaleoDataLoader(str(csv_file))
    result = loader.load()

    assert "寒武纪第二期" in result
    assert len(result["寒武纪第二期"]) == 2

    feat1 = result["寒武纪第二期"][0]
    assert feat1["properties"]["facies"] == "砂岩"
    assert feat1["properties"]["boundary_type"] == "confirmed"
    assert feat1["properties"]["name"] == "北部陆棚"
    assert feat1["geometry"]["type"] == "Polygon"
    assert feat1["geometry"]["coordinates"][0] == [[100, 30], [105, 30], [105, 35], [100, 35], [100, 30]]


def test_load_csv_multi_period(tmp_path):
    csv_content = "period,facies,lon_min,lon_max,lat_min,lat_max\n"
    csv_content += "寒武纪第一期,砂岩,100,105,30,35\n"
    csv_content += "寒武纪第二期,灰岩,100,105,30,35\n"
    csv_file = tmp_path / "multi.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    loader = PaleoDataLoader(str(csv_file))
    result = loader.load()

    assert len(result) == 2
    assert "寒武纪第一期" in result
    assert "寒武纪第二期" in result


def test_load_geojson_with_period(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩", "period": "寒武纪第一期"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            },
            {
                "type": "Feature",
                "properties": {"facies": "灰岩", "period": "寒武纪第二期"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "test.geojson"
    geo_file.write_text(json.dumps(geojson), encoding="utf-8")

    loader = PaleoDataLoader(str(geo_file))
    result = loader.load()

    assert len(result) == 2
    assert result["寒武纪第一期"][0]["properties"]["facies"] == "砂岩"


def test_load_geojson_no_period_uses_filename(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "my_period.geojson"
    geo_file.write_text(json.dumps(geojson), encoding="utf-8")

    loader = PaleoDataLoader(str(geo_file))
    result = loader.load()

    assert len(result) == 1
    assert "my_period" in result


def test_detect_csv_format(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("period,facies,lon_min,lon_max,lat_min,lat_max\n", encoding="utf-8")
    assert PaleoDataLoader.detect_format(str(csv_file)) == "csv"


def test_detect_geojson_format(tmp_path):
    geo_file = tmp_path / "test.geojson"
    geo_file.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    assert PaleoDataLoader.detect_format(str(geo_file)) == "geojson"


def test_detect_unknown_format(tmp_path):
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("random text", encoding="utf-8")
    assert PaleoDataLoader.detect_format(str(bad_file)) is None
