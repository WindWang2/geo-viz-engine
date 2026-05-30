import numpy as np
import pytest

from geoviz_seismic.horizon import extract_along_horizon


def _make_volume(nI=5, nX=6, nS=20, constant=1.0):
    """Simple constant-volume helper."""
    return np.full((nI, nX, nS), constant, dtype=np.float32)


def test_extract_single_sample():
    vol = _make_volume(constant=3.0)
    grid = np.full((5, 6), 10.0)  # TWT = 10 ms → sample 10 with dt=1, t0=0
    result = extract_along_horizon(vol, grid, dt_ms=1.0)
    assert result.shape == (5, 6)
    np.testing.assert_allclose(result, 3.0)


def test_extract_with_nan_grid():
    vol = _make_volume(constant=2.0)
    grid = np.full((5, 6), 5.0)
    grid[2, 3] = np.nan
    result = extract_along_horizon(vol, grid, dt_ms=1.0)
    assert result.shape == (5, 6)
    assert np.isnan(result[2, 3])
    np.testing.assert_allclose(result[0, 0], 2.0)


def test_extract_all_nan_grid():
    vol = _make_volume()
    grid = np.full((5, 6), np.nan)
    result = extract_along_horizon(vol, grid, dt_ms=1.0)
    assert np.all(np.isnan(result))


def test_extract_window_rms():
    """With window > 0, result is RMS over the window around the horizon."""
    nS = 30
    vol = np.ones((3, 4, nS), dtype=np.float32) * 4.0  # amplitude=4 everywhere
    grid = np.full((3, 4), 15.0)  # sample 15
    result = extract_along_horizon(vol, grid, dt_ms=1.0, window=2)
    assert result.shape == (3, 4)
    # RMS of [4,4,4,4,4] = 4.0
    np.testing.assert_allclose(result, 4.0, atol=1e-5)


def test_extract_window_partial_oob():
    """Window extends past volume edge — NaN for out-of-bounds samples."""
    nS = 10
    vol = np.ones((2, 2, nS), dtype=np.float32)
    grid = np.full((2, 2), 1.0)  # sample 1, window=3 needs samples -2..4
    result = extract_along_horizon(vol, grid, dt_ms=1.0, window=3)
    # Sample 1 ± 3 → -2..4, samples -2,-1 are OOB, should still compute RMS
    assert result.shape == (2, 2)
    assert not np.all(np.isnan(result))


def test_extract_with_t0_offset():
    vol = _make_volume(nS=20, constant=5.0)
    grid = np.full((5, 6), 20.0)  # TWT=20, t0=5, dt=1 → sample index 15
    result = extract_along_horizon(vol, grid, dt_ms=1.0, t0_ms=5.0)
    np.testing.assert_allclose(result, 5.0)


def test_extract_ramp_volume():
    """Volume with sample-index ramp: value at sample k = k."""
    nS = 50
    vol = np.zeros((1, 1, nS), dtype=np.float32)
    vol[0, 0, :] = np.arange(nS, dtype=np.float32)
    grid = np.array([[25.0]])  # sample 25 → value should be 25
    result = extract_along_horizon(vol, grid, dt_ms=1.0)
    np.testing.assert_allclose(result[0, 0], 25.0)
