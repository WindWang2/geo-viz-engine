"""Tests for IDW interpolation with fault polyline barriers."""
import numpy as np
import pytest
from geoviz_plots.interpolation.idw import interpolate_idw, segments_intersect

def test_segments_intersect():
    # Cross intersection
    p1, p2 = (0.0, 0.0), (2.0, 2.0)
    q1, q2 = (0.0, 2.0), (2.0, 0.0)
    assert segments_intersect(p1, p2, q1, q2) is True

    # Parallel non-intersecting lines
    p1, p2 = (0.0, 0.0), (2.0, 0.0)
    q1, q2 = (0.0, 1.0), (2.0, 1.0)
    assert segments_intersect(p1, p2, q1, q2) is False

def test_idw_without_faults():
    x = np.array([0.0, 10.0, 0.0, 10.0])
    y = np.array([0.0, 0.0, 10.0, 10.0])
    z = np.array([10.0, 20.0, 30.0, 40.0])

    grid_x = np.linspace(0, 10, 5)
    grid_y = np.linspace(0, 10, 5)

    grid_z = interpolate_idw(x, y, z, grid_x, grid_y)
    assert grid_z.shape == (5, 5)
    assert not np.isnan(grid_z).any()
    assert pytest.approx(grid_z[0, 0], abs=1e-3) == 10.0

def test_idw_with_fault_barrier():
    # Points on left side (z=10) and right side (z=100)
    x = np.array([1.0, 1.0, 9.0, 9.0])
    y = np.array([1.0, 9.0, 1.0, 9.0])
    z = np.array([10.0, 10.0, 100.0, 100.0])

    grid_x = np.linspace(0, 10, 11)
    grid_y = np.linspace(0, 10, 11)

    # Vertical fault barrier along x=5.0 separating left and right
    fault_polylines = [[(5.0, -1.0), (5.0, 11.0)]]

    grid_z = interpolate_idw(x, y, z, grid_x, grid_y, fault_polylines=fault_polylines)
    
    # Left side (x < 5) should only be influenced by left points (z ~ 10)
    assert grid_z[5, 2] < 20.0
    # Right side (x > 5) should only be influenced by right points (z ~ 100)
    assert grid_z[5, 8] > 80.0
