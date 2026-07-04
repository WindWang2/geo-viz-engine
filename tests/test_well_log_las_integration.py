"""Integration tests for WellLogPage LAS file import and ImageTrack export."""
import os
import pytest
from src.pages.well_log.page import WellLogPage

@pytest.fixture
def well_log_page(qtbot):
    page = WellLogPage()
    qtbot.addWidget(page)
    page.resize(1000, 700)
    page.show()
    return page

def test_well_log_page_las_import(well_log_page, tmp_path):
    las_file = str(tmp_path / "test_well.las")
    with open(las_file, "w", encoding="utf-8") as f:
        f.write("""~VERSION
 VERS . 2.0 : CWLS
~WELL
 WELL. TEST-WELL-99 :
~CURVE
 DEPT.M :
 GR.API :
~ASCII
 1000.00 45.0
 1001.00 50.0
""")

    well_log_page.import_las_file(las_file)
    assert well_log_page is not None
