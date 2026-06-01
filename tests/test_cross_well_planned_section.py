import pytest
from unittest.mock import patch
from PySide6.QtCore import QPointF, Qt, QEvent
from PySide6.QtGui import QMouseEvent
from geoviz_map import MapCanvas, WellMarker
from src.pages.cross_well.page import CrossWellPage
from src.data.cache import DataCache
from src.data.models import WellCoordinates

def test_map_shift_drag_box_selection(qtbot):
    """Verify that Shift+drag on MapCanvas triggers box selection and emits section_selected signal."""
    wells = [
        WellMarker(name="W1", lng=14.99, lat=14.99, color="#6b7280", has_data=True),
        WellMarker(name="W2", lng=15.01, lat=15.01, color="#6b7280", has_data=True),
        WellMarker(name="W3", lng=15.02, lat=15.02, color="#6b7280", has_data=False),  # No data, should be skipped
    ]
    
    # Create map canvas
    canvas = MapCanvas(
        wells=wells,
        world_geojson={"type": "FeatureCollection", "features": []},
        china_geojson={"type": "FeatureCollection", "features": []},
        initial_center=(15.0, 15.0),
        initial_zoom=7.5
    )
    qtbot.addWidget(canvas)
    canvas.resize(400, 300)
    canvas.show()
    qtbot.waitExposed(canvas)
    
    # Track signal emission
    emitted_sections = []
    canvas.section_selected.connect(emitted_sections.append)
    
    # Simulate Shift + Drag
    # 1. Mouse Press with Shift
    press_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(0.0, 0.0),
        QPointF(0.0, 0.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier
    )
    canvas.mousePressEvent(press_event)
    assert canvas._box_selecting is True
    
    # 2. Mouse Move
    move_event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(400.0, 300.0),
        QPointF(400.0, 300.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.ShiftModifier
    )
    canvas.mouseMoveEvent(move_event)
    assert canvas._box_current == QPointF(400.0, 300.0)
    
    # 3. Mouse Release
    release_event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(400.0, 300.0),
        QPointF(400.0, 300.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.ShiftModifier
    )
    canvas.mouseReleaseEvent(release_event)
    
    assert canvas._box_selecting is False
    assert len(emitted_sections) == 1
    # Should select W1 and W2 because W3 does not have data
    assert set(emitted_sections[0]) == {"W1", "W2"}

def test_load_planned_section_sorting(qtbot):
    """Verify that load_planned_section sorts the selected wells using PCA and triggers loading."""
    page = CrossWellPage()
    qtbot.addWidget(page)
    
    # Selected wells out of order
    well_names = ["W3", "W1", "W2"]
    
    # Mock data cache coordinates returning collinear points: W1(10,30), W2(20,30), W3(15,30)
    # So PCA sorting should result in: W1 -> W3 -> W2 (or reverse)
    mock_coords = [
        WellCoordinates(name="W1", longitude=10.0, latitude=30.0),
        WellCoordinates(name="W2", longitude=20.0, latitude=30.0),
        WellCoordinates(name="W3", longitude=15.0, latitude=30.0),
    ]
    
    with patch.object(DataCache, "get_well_coordinates", return_value=mock_coords):
        with patch.object(page, "_load_wells") as mock_load:
            page.load_planned_section(well_names)
            
    mock_load.assert_called_once()
    sorted_args = mock_load.call_args[0][0]
    
    # Sorted either direction
    assert sorted_args == ["W1", "W3", "W2"] or sorted_args == ["W2", "W3", "W1"]
