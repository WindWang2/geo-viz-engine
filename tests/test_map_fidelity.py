import pytest
from PySide6.QtWidgets import QApplication, QFrame, QLineEdit, QPushButton, QScrollArea, QListWidget
from src.pages.map.page import MapPage
from src.data.cache import DataCache

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def map_page(app):
    cache = DataCache()
    return MapPage(cache=cache)

def test_map_page_layout_and_sidebar(map_page):
    # MapPage has a left sidebar frame and a right panel/canvas
    assert hasattr(map_page, "left_sidebar")
    assert isinstance(map_page.left_sidebar, QFrame)
    
    # 1. Left sidebar width should be constrained to 260px
    assert map_page.left_sidebar.width() == 260 or map_page.left_sidebar.maximumWidth() == 260
    
    # 2. Sidebar contains search bar
    assert hasattr(map_page, "search_box")
    assert isinstance(map_page.search_box, QLineEdit)
    assert map_page.search_box.placeholderText() != ""
    
    # 3. Sidebar contains three chips
    assert hasattr(map_page, "chip_all")
    assert hasattr(map_page, "chip_interpreted")
    assert hasattr(map_page, "chip_gas")
    assert isinstance(map_page.chip_all, QPushButton)
    assert isinstance(map_page.chip_interpreted, QPushButton)
    assert isinstance(map_page.chip_gas, QPushButton)
    assert "46" in map_page.chip_all.text()
    
    # 4. Sidebar contains scroll area / list for wells
    assert hasattr(map_page, "well_list")
    assert isinstance(map_page.well_list, (QScrollArea, QListWidget))

def test_map_page_right_overlays(map_page):
    # Right side has the MapCanvas and various floating control panels
    assert hasattr(map_page, "map_canvas")
    
    # Float toolbar (zoomIn, zoomOut, fit, ruler)
    assert hasattr(map_page, "float_tb")
    assert isinstance(map_page.float_tb, QFrame)
    
    # Layer manager floating card
    assert hasattr(map_page, "layer_manager")
    assert isinstance(map_page.layer_manager, QFrame)
    
    # Well Callout Card
    assert hasattr(map_page, "well_callout")
    assert isinstance(map_page.well_callout, QFrame)
    assert map_page.well_callout.isHidden()  # Starts hidden

def test_map_page_zoom_buttons(map_page):
    # Verify the initial zoom level
    initial_zoom = map_page.map_canvas.zoom
    assert initial_zoom == 7.5
    
    # 1. Click zoom in button
    map_page.btn_zoom_in.click()
    assert map_page.map_canvas.zoom > initial_zoom
    
    # 2. Click zoom out button
    current_zoom = map_page.map_canvas.zoom
    map_page.btn_zoom_out.click()
    assert map_page.map_canvas.zoom < current_zoom
    
    # 3. Click fit button (restores to 7.5)
    map_page.btn_fit.click()
    assert map_page.map_canvas.zoom == 7.5
