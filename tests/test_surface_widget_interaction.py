"""Tests for 2D SurfaceWidget control point interaction and signals."""
import pytest
import numpy as np
from PySide6.QtCore import Qt, QPointF
from geoviz_plots.surface.surface_widget import SurfaceWidget

@pytest.fixture
def surface_widget(qtbot):
    widget = SurfaceWidget()
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget

def test_surface_widget_control_points(surface_widget, qtbot):
    pts = [
        {"id": "cp1", "x": 2.0, "y": 2.0, "z": 15.0},
        {"id": "cp2", "x": 8.0, "y": 8.0, "z": 45.0},
    ]
    surface_widget.set_control_points(pts)
    assert len(surface_widget.control_points) == 2

    # Verify add control point
    surface_widget.add_control_point(5.0, 5.0, 30.0)
    assert len(surface_widget.control_points) == 3

def test_surface_widget_fault_polylines(surface_widget):
    faults = [[(5.0, 0.0), (5.0, 10.0)]]
    surface_widget.set_fault_polylines(faults)
    assert len(surface_widget.fault_polylines) == 1

def test_contour_selection_signal(surface_widget, qtbot):
    grid_x = np.linspace(0, 10, 10)
    grid_y = np.linspace(0, 10, 10)
    grid_z = np.outer(grid_x, grid_y)
    levels = [10.0, 20.0, 30.0, 40.0]
    surface_widget.set_grid_data(grid_x, grid_y, grid_z, levels)

    selected_levels = []
    surface_widget.contour_selected.connect(lambda l: selected_levels.append(l))

    surface_widget.select_contour_level(20.0)
    assert len(selected_levels) == 1
    assert selected_levels[0] == 20.0
