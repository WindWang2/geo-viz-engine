"""Unit tests for point-in-polygon filtering and SciPy Convex Hull calculation."""
import numpy as np
import pytest
from geoviz_plots.chart.convex_hull import point_in_polygon_mask, compute_convex_hull

def test_point_in_polygon_mask():
    x = np.array([1.0, 5.0, 10.0, 2.0])
    y = np.array([1.0, 5.0, 10.0, 8.0])

    # Polygon square (0,0) to (6,6)
    poly_vertices = [(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)]
    mask = point_in_polygon_mask(x, y, poly_vertices)

    assert bool(mask[0]) is True   # (1,1) inside
    assert bool(mask[1]) is True   # (5,5) inside
    assert bool(mask[2]) is False  # (10,10) outside
    assert bool(mask[3]) is False  # (2,8) outside


def test_compute_convex_hull():
    # Square points plus inside points
    x = np.array([0.0, 10.0, 10.0, 0.0, 5.0, 3.0])
    y = np.array([0.0, 0.0, 10.0, 10.0, 5.0, 3.0])

    hull_pts = compute_convex_hull(x, y)
    assert len(hull_pts) >= 4
    # Coordinates should bound the dataset
    assert np.min(hull_pts[:, 0]) == 0.0
    assert np.max(hull_pts[:, 0]) == 10.0
