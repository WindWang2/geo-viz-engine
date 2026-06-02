import pytest
from PySide6.QtWidgets import QApplication, QFrame, QPushButton, QLabel, QAbstractButton
from src.pages.paleo_map.page import PaleoMapPage, ToggleSwitch

@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])

@pytest.fixture
def page(app):
    return PaleoMapPage()

def test_paleo_map_page_split_layout(page):
    # Check that PaleoMapPage now has a right sidebar frame of 230px width
    assert hasattr(page, "right_sidebar")
    assert isinstance(page.right_sidebar, QFrame)
    assert page.right_sidebar.width() == 230 or page.right_sidebar.maximumWidth() == 230
    
    # Check for title / legend / layer control elements in the sidebar
    assert hasattr(page, "legend_title")
    assert isinstance(page.legend_title, QLabel)
    
    # Check toggle switches (Azurite ToggleSwitch for layers)
    assert hasattr(page, "toggle_wells")
    assert hasattr(page, "toggle_labels")
    assert isinstance(page.toggle_wells, ToggleSwitch)
    assert isinstance(page.toggle_labels, ToggleSwitch)
    assert isinstance(page.toggle_wells, QAbstractButton)

    # Check for "导出图件" button at the bottom of the right sidebar
    assert hasattr(page, "export_map_btn")
    assert isinstance(page.export_map_btn, QPushButton)

def test_paleo_map_page_overlays(page):
    # Verify floating toolbar (zoomIn, zoomOut, fit) on the map canvas area
    assert hasattr(page, "float_tb")
    assert isinstance(page.float_tb, QFrame)

def test_paleo_map_page_legend_update(page):
    # Populate map view with a feature and verify _update_facies_legend is safe and functions correctly
    sample_features = [
        {
            "type": "Feature",
            "properties": {"name": "砂岩相区", "facies": "砂岩"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[0,0], [1,0], [1,1], [0,1], [0,0]]]
            }
        }
    ]
    page.map_view.load_features(sample_features, period_name="K1")
    page._update_facies_legend()
    
    # Legend layout should have elements populated (including the stretch at the end)
    # The count should be > 1 (e.g., 2: 1 frame for "砂岩" + 1 stretch)
    assert page.legend_layout.count() > 1
    
    # Verify first item is a QFrame containing the label "砂岩"
    first_item = page.legend_layout.itemAt(0)
    assert first_item is not None
    row_frame = first_item.widget()
    assert isinstance(row_frame, QFrame)
    
    # Ensure the layout inside the row has a QLabel with text "砂岩"
    child_labels = row_frame.findChildren(QLabel)
    assert len(child_labels) > 0
    assert any(label.text() == "砂岩" for label in child_labels)

def test_paleo_map_page_zoom_buttons(page):
    initial_zoom = page.map_view.zoom
    
    # 1. Click zoom in button
    page.btn_zoom_in.click()
    assert page.map_view.zoom > initial_zoom
    
    # 2. Click zoom out button
    current_zoom = page.map_view.zoom
    page.btn_zoom_out.click()
    assert page.map_view.zoom < current_zoom
    
    # 3. Click fit button (fits to data or defaults to zoom ~2 for empty canvas)
    page.btn_fit.click()
    assert page.map_view.zoom > 0
