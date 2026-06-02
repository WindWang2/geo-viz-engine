import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QLabel, QComboBox
from src.pages.well_log.page import WellLogPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def page(app):
    return WellLogPage()

def test_well_log_page_fidelity_controls(page):
    # Verify depth range label in the toolbar
    assert hasattr(page, "_depth_lbl")
    assert isinstance(page._depth_lbl, QLabel)
    
    # Verify segmented column toggle buttons
    assert hasattr(page, "_cols_btn")
    assert hasattr(page, "_overlay_btn")
    assert isinstance(page._cols_btn, QPushButton)
    assert isinstance(page._overlay_btn, QPushButton)
    assert page._cols_btn.isCheckable()
    assert page._overlay_btn.isCheckable()
    
    # Verify "轨道" action button
    assert hasattr(page, "_tracks_btn")
    assert isinstance(page._tracks_btn, QPushButton)
