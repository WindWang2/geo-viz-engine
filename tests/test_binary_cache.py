import tempfile
from pathlib import Path
import math
from src.data.loaders import load_well_log_from_excel

def test_binary_cache_flow(monkeypatch):
    import pandas as pd
    from unittest.mock import MagicMock
    
    # 1. Setup mock ExcelFile and read_excel
    mock_excel_file = MagicMock()
    mock_excel_file.sheet_names = ["测井曲线", "岩性道"]
    monkeypatch.setattr("pandas.ExcelFile", lambda path, engine=None: mock_excel_file)
    
    # We use a mutable container to count actual reads (to verify caching)
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
        # Create a dummy empty file to satisfy path.exists() / getmtime()
        fake_excel_path.touch()
        
        # First load (cold path): should read excel sheets
        well_data_1 = load_well_log_from_excel(fake_excel_path, "Well_Test")
        assert well_data_1.well_name == "Well_Test"
        assert len(well_data_1.curves) == 2
        # Check NaN value is preserved
        gr_curve_1 = next(c for c in well_data_1.curves if c.name == "GR")
        assert gr_curve_1.values[0] == 45
        assert math.isnan(gr_curve_1.values[1])
        
        # Verify cache file exists and has .pkl suffix
        cache_dir = fake_excel_path.parent / ".cache"
        assert cache_dir.exists()
        pkl_files = list(cache_dir.glob("Well_Test_*.pkl"))
        assert len(pkl_files) == 1
        
        # Reset read count
        read_count["count"] = 0
        
        # Second load (hot path): should load from cache, not read excel
        well_data_2 = load_well_log_from_excel(fake_excel_path, "Well_Test")
        assert read_count["count"] == 0  # 0 sheets loaded!
        assert well_data_2.well_name == "Well_Test"
        assert len(well_data_2.curves) == 2
        gr_curve_2 = next(c for c in well_data_2.curves if c.name == "GR")
        assert gr_curve_2.values[0] == 45
        assert math.isnan(gr_curve_2.values[1])
        
        # Verify identical structure
        assert well_data_2.top_depth == well_data_1.top_depth
        assert well_data_2.bottom_depth == well_data_1.bottom_depth
