from geoviz_well_log.models import WellLogData
import pandas as pd
import pytest
from pathlib import Path
from src.data.loaders import load_well_log_converted

def test_well_log_data_has_datum_elevation():
    data = WellLogData(well_name="Test Well", top_depth=0.0, bottom_depth=100.0)
    assert hasattr(data, 'datum_elevation')
    assert data.datum_elevation == 0.0

def test_loader_extracts_datum_elevation(tmp_path):
    # Create a mock Excel file
    excel_path = tmp_path / "test_well.xlsx"
    df = pd.DataFrame({
        "深度": [100.0, 101.0, 102.0],
        "TVDSS": [90.0, 91.0, 92.0],
        "GR": [10.0, 20.0, 30.0]
    })
    
    with pd.ExcelWriter(excel_path) as writer:
        df.to_excel(writer, sheet_name="测井曲线", index=False)
    
    # Load the data
    data = load_well_log_converted(excel_path)
    
    # MD = 100.0, TVDSS = 90.0 => datum_elevation = 100.0 - 90.0 = 10.0
    assert data.datum_elevation == 10.0
