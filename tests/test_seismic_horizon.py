import numpy as np
import pytest

from geoviz_seismic.horizon import HorizonParser


def _make_axes():
    return {
        "ilines": np.arange(100, 110, dtype=np.int32),
        "xlines": np.arange(200, 220, dtype=np.int32),
        "nI": 10,
        "nX": 20,
    }


def test_parse_dense_horizon(dense_horizon_path):
    parser = HorizonParser(dense_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    assert grid.shape == (10, 20)
    assert not np.any(np.isnan(grid))


def test_parse_sparse_has_gaps(sparse_horizon_path):
    parser = HorizonParser(sparse_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    assert grid.shape == (10, 20)
    assert np.any(np.isnan(grid))


def test_nearest_fill(sparse_horizon_path):
    parser = HorizonParser(sparse_horizon_path, unit="ms")
    axes = _make_axes()
    grid = parser.parse(axes)
    filled = parser.fill_nearest(grid, max_dist=0)
    assert not np.any(np.isnan(filled))


def test_sample_unit_conversion(dense_horizon_path):
    parser_ms = HorizonParser(dense_horizon_path, unit="ms")
    parser_samp = HorizonParser(dense_horizon_path, unit="sample", scale=0.5)
    axes = _make_axes()
    axes["dt_ms"] = 4.0
    grid_ms = parser_ms.parse(axes)
    grid_samp = parser_samp.parse(axes)
    assert not np.allclose(grid_ms, grid_samp)


def test_fill_rbf_respects_max_dist():
    """Gap pixels farther than max_dist from the nearest valid pick must
    stay NaN.

    Regression: the EDT was computed on the *valid* mask, so the distance
    at gap pixels was always 0 and ``(~mask) & (dist > max_dist)`` could
    never trigger — max_dist clipping was a no-op.
    """
    from scipy.ndimage import distance_transform_edt

    grid = np.full((30, 30), np.nan)
    grid[2:6, 2:6] = 100.0  # valid cluster in one corner, big gap elsewhere
    parser = HorizonParser("/dev/null")
    filled = parser.fill_rbf(grid, max_dist=2.0, neighbors=8)

    mask = np.isfinite(grid)
    dist = distance_transform_edt(~mask)
    # Valid picks are never turned into NaN.
    assert np.all(np.isfinite(filled[mask]))
    # Gap pixels beyond max_dist remain unfilled.
    far = (~mask) & (dist > 2.0)
    assert far.any()
    assert np.all(np.isnan(filled[far]))
    # Gap pixels within max_dist are filled.
    near = (~mask) & (dist <= 2.0)
    assert near.any()
    assert np.all(np.isfinite(filled[near]))


def test_fill_rbf_max_dist_zero_unlimited():
    """max_dist=0 keeps the unlimited-fill behaviour."""
    grid = np.full((10, 10), np.nan)
    grid[0, 0] = 1.0
    grid[0, 9] = 2.0
    grid[9, 0] = 3.0
    grid[9, 9] = 4.0
    parser = HorizonParser("/dev/null")
    filled = parser.fill_rbf(grid, max_dist=0, neighbors=4)
    assert not np.any(np.isnan(filled))
