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


def test_load_well_log_converted(monkeypatch):
    import pandas as pd
    from unittest.mock import MagicMock
    from src.data.loaders import load_well_log_from_excel
    
    mock_excel_file = MagicMock()
    mock_excel_file.sheet_names = ["测井曲线", "岩性道"]
    monkeypatch.setattr("pandas.ExcelFile", lambda path: mock_excel_file)
    
    def mock_read_excel(path, sheet_name):
        if sheet_name == "测井曲线":
            return pd.DataFrame({"深度": [100, 110], "GR": [45, 55], "CAL": [20, 22]})
        elif sheet_name == "岩性道":
            return pd.DataFrame({"顶深": [100], "底深": [110], "岩性": ["砂岩"]})
        return pd.DataFrame()
        
    monkeypatch.setattr("pandas.read_excel", mock_read_excel)
    
    res = load_well_log_from_excel(Path("fake.xlsx"), "Well_X")
    assert res.well_name == "Well_X"
    assert len(res.curves) == 2
    assert res.intervals.lithology[0].name == "砂岩"


