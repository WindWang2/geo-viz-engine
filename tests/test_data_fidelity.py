import pytest
from PySide6.QtWidgets import QApplication, QFrame, QTableWidget, QLabel, QPushButton
from src.pages.data.page import DataPage
from src.data.cache import DataCache

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def page(app):
    cache = DataCache()
    return DataPage(cache=cache)

def test_data_page_fidelity_layout(page):
    # Verify top header frame exists
    assert hasattr(page, "_top_hdr")
    assert isinstance(page._top_hdr, QFrame)
    
    # Verify Quick Import buttons are there
    assert hasattr(page, "_import_data_btn")
    assert hasattr(page, "_import_excel_btn")
    assert hasattr(page, "_import_las_btn")
    assert hasattr(page, "_import_segy_btn")
    assert isinstance(page._import_data_btn, QPushButton)
    
    # Verify 4 KPI cards exist
    assert hasattr(page, "_kpi_container")
    assert isinstance(page._kpi_container, QFrame)
    kpis = page._kpi_container.findChildren(QFrame)
    assert len(kpis) >= 4
    
    # Verify table exists
    assert hasattr(page, "table")
    assert isinstance(page.table, QTableWidget)
