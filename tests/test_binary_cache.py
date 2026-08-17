import tempfile
from pathlib import Path
import math
from src.data.loaders import load_well_log_from_excel

def test_json_cache_flow(monkeypatch):
    import pandas as pd
    from unittest.mock import MagicMock

    mock_excel_file = MagicMock()
    mock_excel_file.sheet_names = ["测井曲线", "岩性道"]
    monkeypatch.setattr("pandas.ExcelFile", lambda path, engine=None: mock_excel_file)

    read_count = {"count": 0}

    def mock_read_excel(path, sheet_name):
        read_count["count"] += 1
        if sheet_name == "测井曲线":
            return pd.DataFrame({"深度": [100, 110], "GR": [45, float("nan")], "CAL": [20, 22]})
        elif sheet_name == "岩性道":
            return pd.DataFrame({"顶深": [100], "底深": [110], "岩性": ["砂岩"]})
        return pd.DataFrame()

    monkeypatch.setattr("pandas.read_excel", mock_read_excel)

    with tempfile.TemporaryDirectory() as tmpdir:
        fake_excel_path = Path(tmpdir) / "fake.xlsx"
        fake_excel_path.touch()

        well_data_1 = load_well_log_from_excel(fake_excel_path, "Well_Test")
        assert well_data_1.well_name == "Well_Test"
        assert len(well_data_1.curves) == 2
        gr_curve_1 = next(c for c in well_data_1.curves if c.name == "GR")
        assert gr_curve_1.values[0] == 45
        assert math.isnan(gr_curve_1.values[1])

        cache_dir = fake_excel_path.parent / ".cache"
        assert cache_dir.exists()
        json_files = list(cache_dir.glob("Well_Test_*.json"))
        assert len(json_files) == 1

        read_count["count"] = 0

        well_data_2 = load_well_log_from_excel(fake_excel_path, "Well_Test")
        assert read_count["count"] == 0
        assert well_data_2.well_name == "Well_Test"
        assert len(well_data_2.curves) == 2
        gr_curve_2 = next(c for c in well_data_2.curves if c.name == "GR")
        assert gr_curve_2.values[0] == 45
        assert math.isnan(gr_curve_2.values[1])
        assert well_data_2.top_depth == well_data_1.top_depth
        assert well_data_2.bottom_depth == well_data_1.bottom_depth


def test_excel_load_survives_readonly_cache_mkdir(monkeypatch, tmp_path):
    """#700: mkdir failure on .cache must not abort a readable Excel load."""
    import pandas as pd
    from unittest.mock import MagicMock

    mock_excel_file = MagicMock()
    mock_excel_file.sheet_names = ["测井曲线", "岩性道"]
    monkeypatch.setattr("pandas.ExcelFile", lambda path, engine=None: mock_excel_file)

    def mock_read_excel(path, sheet_name):
        if sheet_name == "测井曲线":
            return pd.DataFrame({"深度": [100, 110], "GR": [45, 55]})
        if sheet_name == "岩性道":
            return pd.DataFrame({"顶深": [100], "底深": [110], "岩性": ["砂岩"]})
        return pd.DataFrame()

    monkeypatch.setattr("pandas.read_excel", mock_read_excel)

    fake_excel_path = tmp_path / "ro_well.xlsx"
    fake_excel_path.touch()

    original_mkdir = Path.mkdir

    def guarded_mkdir(self, *args, **kwargs):
        if self.name == ".cache":
            raise PermissionError("read-only data directory")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", guarded_mkdir)

    well_data = load_well_log_from_excel(fake_excel_path, "Well_RO")
    assert well_data.well_name == "Well_RO"
    assert len(well_data.curves) == 1
    assert not (fake_excel_path.parent / ".cache").exists()