import json
import tempfile
from pathlib import Path
from src.data.loaders import load_well_coordinates


def test_load_well_coordinates():
    coords = [
        {"name": "Well-A", "latitude": 38.5, "longitude": 117.8},
        {"name": "Well-B", "latitude": 39.0, "longitude": 118.0},
    ]
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(coords, f)
        f.flush()
        result = load_well_coordinates(Path(f.name))
    assert len(result) == 2
    assert result[0].name == "Well-A"


def test_load_well_coordinates_missing_file():
    result = load_well_coordinates(Path("/nonexistent/file.json"))
    assert result == []
