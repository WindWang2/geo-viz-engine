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


def test_point_in_polygon_mask_rotated_geometry():
    """#506: the epsilon guard must preserve the edge denominator's sign.

    np.maximum(1e-12, yj - yi) flipped every descending edge to a tiny
    positive denominator, so the crossing x evaluated to +/-1e12 and any
    non-axis-aligned polygon selected inverted/wrong points (the old suite
    only used an axis-aligned square, which is immune to the bug).
    """
    # Diamond: every edge is slanted, half of them descending.
    diamond = [(2.0, 0.0), (4.0, 2.0), (2.0, 4.0), (0.0, 2.0)]
    pts = np.array([(2.0, 2.0), (3.6, 1.5), (3.5, 0.4), (2.9, 2.0), (1.0, 1.0)])
    mask = point_in_polygon_mask(pts[:, 0], pts[:, 1], diamond)
    expected = [True, False, False, True, True]
    assert [bool(m) for m in mask] == expected

    # 45-degree rotated square, checked against matplotlib.path as an
    # independent reference implementation.
    from matplotlib.path import Path

    theta = np.deg2rad(45.0)
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    square = np.array([(0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0)]) @ rot.T
    rng = np.random.default_rng(42)
    probe = rng.uniform(-2.0, 6.0, size=(400, 2))
    got = point_in_polygon_mask(probe[:, 0], probe[:, 1], [tuple(v) for v in square])
    want = Path(square).contains_points(probe)
    assert np.array_equal(got, want), (got ^ want).sum()


def test_compute_convex_hull_collinear_falls_back_without_raising():
    """#557: collinear selections must not raise QhullError out of the lasso
    path — return the degenerate selection itself instead."""
    x = np.array([0.0, 1.0, 2.0, 3.0, 1.5])
    y = np.array([0.0, 1.0, 2.0, 3.0, 1.5])  # all on the y=x line
    hull = compute_convex_hull(x, y)
    assert hull.shape == (5, 2)
    # lexsorted into a stable polyline along the line
    assert list(hull[:, 0]) == sorted(x)

    # two points: degenerate segment, not an exception
    hull2 = compute_convex_hull(np.array([1.0, 3.0]), np.array([2.0, 8.0]))
    assert hull2.shape == (2, 2)
