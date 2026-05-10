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
