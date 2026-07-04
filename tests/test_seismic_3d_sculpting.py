# tests/test_seismic_3d_sculpting.py
"""Unit tests for 3D seismic horizon raycasting, Gaussian sculpting, and ROI undo patch."""

import pytest
import numpy as np

from geoviz_seismic.horizon import (
    unproject_ray, intersect_ray_grid, apply_gaussian_sculpt, HorizonROIPatch
)

def test_unproject_ray():
    # Construct a simple identity view-projection matrix
    inv_mvp = np.eye(4, dtype=np.float32)
    viewport = (0.0, 0.0, 800.0, 600.0)
    
    # Center click (400, 300) -> NDC (0, 0)
    origin, direction = unproject_ray((400.0, 300.0), viewport, inv_mvp)
    assert origin.shape == (3,)
    assert direction.shape == (3,)
    assert np.allclose(direction, [0, 0, 1], atol=1e-3)

def test_intersect_ray_grid():
    # Grid 10x10, flat at Z = 50.0
    grid_z = np.full((10, 10), 50.0, dtype=np.float64)
    x_range = (0.0, 100.0)
    y_range = (0.0, 100.0)
    
    # Ray origin at (50, 50, 0), pointing straight along +Z (0, 0, 1)
    origin = np.array([50.0, 50.0, 0.0], dtype=np.float32)
    direction = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    
    hit = intersect_ray_grid(origin, direction, grid_z, x_range, y_range)
    assert hit is not None
    x, y, z = hit
    assert pytest.approx(x, abs=2.0) == 50.0
    assert pytest.approx(y, abs=2.0) == 50.0
    assert pytest.approx(z, abs=1.0) == 50.0

def test_gaussian_sculpting_math():
    grid_z = np.zeros((20, 20), dtype=np.float64)
    x_range = (0.0, 190.0)
    y_range = (0.0, 190.0)
    
    center_xy = (100.0, 100.0)
    radius = 30.0
    strength = 10.0
    
    updated_grid, (min_i, max_i, min_j, max_j) = apply_gaussian_sculpt(
        grid_z, center_xy, radius, strength, x_range, y_range
    )
    
    # Center (node 10) should increase by ~ strength (10.0)
    center_i, center_j = 10, 10
    assert updated_grid[center_i, center_j] == pytest.approx(10.0, abs=0.5)
    
    # Border outside 3*radius should remain ~0.0
    assert updated_grid[0, 0] == 0.0
    
    # ROI bounds check
    assert 0 <= min_i < max_i <= 20
    assert 0 <= min_j < max_j <= 20

def test_roi_patch_undo_redo():
    grid_z = np.zeros((10, 10), dtype=np.float64)
    patch = HorizonROIPatch(grid_z, (2, 5, 2, 5))
    
    # Modify grid in ROI
    grid_z[2:5, 2:5] += 15.0
    assert np.all(grid_z[2:5, 2:5] == 15.0)
    patch.capture_after(grid_z)
    
    # Apply undo
    patch.undo(grid_z)
    assert np.all(grid_z[2:5, 2:5] == 0.0)
    
    # Apply redo
    patch.redo(grid_z)
    assert np.all(grid_z[2:5, 2:5] == 15.0)

def test_interactive_horizon_gl_item():
    from geoviz_seismic.interactive_horizon import InteractiveHorizonGLItem
    grid_z = np.zeros((10, 10), dtype=np.float64)
    item = InteractiveHorizonGLItem(
        grid_z, x_range=(0.0, 100.0), y_range=(0.0, 100.0)
    )
    
    assert item.brush_enabled is False
    item.brush_enabled = True
    assert item.brush_enabled is True
    
    item.brush_radius = 25.0
    assert item.brush_radius == 25.0
    
    item.attribute_mode = 1
    assert item.attribute_mode == 1
    
    item.set_brush_center((50.0, 50.0, 10.0))
    assert item._brush_center == (50.0, 50.0, 10.0)


