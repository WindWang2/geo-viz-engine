import pytest
from PySide6.QtWidgets import QApplication, QPushButton, QGroupBox
from src.pages.plots.page import PlotsPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

def test_plots_page_azurite_styling(app):
    page = PlotsPage()
    # Check for Azurite background color in status bar or control panel
    assert "#faf9f5" in page.status_bar.styleSheet().lower()

def test_plots_page_group_boxes(app):
    page = PlotsPage()
    # Check if QGroupBoxes have the new Azurite linear icons/text
    # (Since icons in titles are just text padding + icons in QGroupBox are hard,
    # we'll check if hardcoded styles are removed and global ones apply)
    groups = page.findChildren(QGroupBox)
    for g in groups:
        # Global QSS should handle it, so we check if local overrides are gone or updated
        assert "border: 1px solid #cbd5e0" not in g.styleSheet().lower()
