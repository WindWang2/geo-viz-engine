import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QLabel
from src.pages.cross_well.page import CrossWellPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def page(app):
    return CrossWellPage()

def test_cross_well_page_fidelity_controls(page):
    # Verify well properties label
    assert hasattr(page, "_well_props_lbl")
    assert isinstance(page._well_props_lbl, QLabel)
    
    # Verify segment buttons
    assert hasattr(page, "_pick_seg")
    assert hasattr(page, "_link_seg")
    assert hasattr(page, "_browse_seg")
    assert isinstance(page._pick_seg, QPushButton)
    assert isinstance(page._link_seg, QPushButton)
    assert isinstance(page._browse_seg, QPushButton)
    
    # Verify "DTW 自动对比" button
    assert hasattr(page, "_dtw_auto_btn")
    assert isinstance(page._dtw_auto_btn, QPushButton)
    
    # Verify "超宽 SVG" button
    assert hasattr(page, "_svg_wide_btn")
    assert isinstance(page._svg_wide_btn, QPushButton)
