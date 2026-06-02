import pytest
from PySide6.QtWidgets import QApplication, QWidget, QComboBox, QSlider
from src.pages.plots.page import PlotsPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def page(app):
    return PlotsPage()

def test_plots_page_fidelity_layout(page):
    # Verify page has the right control panel container
    assert hasattr(page, "control_panel")
    assert isinstance(page.control_panel, QWidget)
    assert page.control_panel.width() == 200 or page.control_panel.maximumWidth() == 200
    
    # Verify interpolation sliders & drop-downs
    assert hasattr(page, "method_combo")
    assert isinstance(page.method_combo, QComboBox)
    assert hasattr(page, "power_slider")
    assert isinstance(page.power_slider, QSlider)
    
    # Verify standard color map dropdown
    assert hasattr(page, "cmap_combo")
    assert isinstance(page.cmap_combo, QComboBox)
