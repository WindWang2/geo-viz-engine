"""Tests for 3D Surface & Contour synchronization and GLItem heightmap updates."""
import pytest
import numpy as np
from geoviz_seismic.interactive_horizon import InteractiveHorizonGLItem

def test_interactive_horizon_heightmap_update():
    grid_z0 = np.zeros((10, 10), dtype=np.float32)
    item = InteractiveHorizonGLItem(grid_z0, (0.0, 10.0), (0.0, 10.0))
    assert item._verts.shape == (100, 3)

    # Update with new grid
    grid_x = np.linspace(0, 20, 15)
    grid_y = np.linspace(0, 30, 20)
    grid_z1 = np.ones((20, 15), dtype=np.float32) * 50.0

    item.update_heightmap(grid_x, grid_y, grid_z1)
    assert item._nI == 20
    assert item._nX == 15
    assert item._verts.shape == (300, 3)
    assert item._x_range == (0.0, 20.0)
    assert item._y_range == (0.0, 30.0)
    assert np.allclose(item._verts[:, 2], 50.0)
