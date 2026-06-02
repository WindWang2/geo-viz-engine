import pytest
from PySide6.QtWidgets import QApplication, QFrame, QSlider, QComboBox
from src.pages.seismic.page import SeismicPage

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def page(app):
    return SeismicPage()

def test_seismic_page_fidelity_layout(page):
    # Verify right sidebar exists with width 226px
    assert hasattr(page, "right_sidebar")
    assert isinstance(page.right_sidebar, QFrame)
    assert page.right_sidebar.width() == 226 or page.right_sidebar.maximumWidth() == 226
    
    # Verify sliders are in the right sidebar now (reparented)
    assert page._tb_il_slider.parent() == page.right_sidebar
    assert page._tb_xl_slider.parent() == page.right_sidebar
    assert page._tb_t_slider.parent() == page.right_sidebar
    
    # Verify colormap dropdown is also in the sidebar
    assert page._cmap_combo.parent() == page.right_sidebar
