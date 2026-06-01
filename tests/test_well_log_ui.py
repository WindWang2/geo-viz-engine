import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QComboBox
from src.pages.well_log.page import WellLogPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_well_log_page_azurite_icons(app):
    page = WellLogPage()
    
    # Check for icons on export and predict buttons
    from PySide6.QtWidgets import QPushButton
    btns = page.findChildren(QPushButton)
    
    # We'll check specific buttons after implementing icons
    icon_btns = [b for b in btns if not b.icon().isNull()]
    # Initially might be 0 or small number
    assert len(icon_btns) >= 4, f"Expected at least 4 buttons with icons in WellLogPage, found {len(icon_btns)}"

def test_well_log_page_styling(app):
    page = WellLogPage()
    # Check toolbar background
    toolbar = page._toolbar
    assert "#faf9f5" in toolbar.styleSheet().lower()
