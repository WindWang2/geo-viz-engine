"""Tests for stratal / proportional slicing (pure-numpy engine core)."""

from __future__ import annotations

import numpy as np
import pytest

from geoviz_seismic.stratal import (
    build_proportional_surfaces,
    extract_stratal_slice,
    stratal_slice_volume,
    validate_horizon_pair,
)


# ---------------------------------------------------------------------------
# validate_horizon_pair
# ---------------------------------------------------------------------------

def test_validate_horizon_pair_masks_inverted_and_nan():
    top = np.array([[1.0, np.nan], [3.0, 5.0]])
    bot = np.array([[2.0, 4.0], [2.0, 6.0]])  # (1,0) inverted (2 < 3)
    mask = validate_horizon_pair(top, bot)
    assert mask.tolist() == [[True, False], [False, True]]


def test_validate_horizon_pair_respects_volume_bounds():
    top = np.array([[1.0, 1.0]])
    bot = np.array([[2.0, 2.0]])
    # nS = 3 -> valid sample range [0, 2]; top/bot both in range
    assert validate_horizon_pair(top, bot, volume_shape=(1, 2, 3)).tolist() == [[True, True]]
    # nS = 2 -> valid range [0, 1]; both at index 2 are out of range
    assert validate_horizon_pair(top, bot, volume_shape=(1, 2, 2)).tolist() == [[False, False]]


def test_validate_horizon_pair_rejects_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        validate_horizon_pair(np.zeros((2, 2)), np.zeros((2, 3)))


# ---------------------------------------------------------------------------
# build_proportional_surfaces
# ---------------------------------------------------------------------------

def test_build_surfaces_endpoints_reproduce_horizons():
    top = np.array([[0.0, 0.0]])
    bot = np.array([[10.0, 20.0]])
    surfs = build_proportional_surfaces(top, bot, [0.0, 0.5, 1.0])
    assert surfs.shape == (3, 1, 2)
    assert np.allclose(surfs[0], top)
    assert np.allclose(surfs[2], bot)
    assert np.allclose(surfs[1], [[5.0, 10.0]])


def test_build_surfaces_scalar_returns_2d():
    top = np.zeros((3, 3))
    bot = np.full((3, 3), 9.0)
    s = build_proportional_surfaces(top, bot, 0.25)
    assert s.shape == (3, 3)
    assert np.allclose(s, 2.25)


def test_build_surfaces_propagates_nan():
    top = np.array([[0.0, np.nan]])
    bot = np.array([[10.0, 10.0]])
    s = build_proportional_surfaces(top, bot, 0.5)
    assert np.isfinite(s[0, 0])
    assert np.isnan(s[0, 1])


def test_build_surfaces_inverted_pair_keeps_nan():
    # validate_horizon_pair is the canonical masker, but build itself must not
    # invent NaN either; an inverted pair should still interpolate linearly.
    # We assert it returns finite values (masking is the caller's job).
    top = np.array([[5.0]])
    bot = np.array([[1.0]])
    s = build_proportional_surfaces(top, bot, 0.5)
    assert np.isfinite(s).all()
    assert np.allclose(s, 3.0)  # (5+1)/2


# ---------------------------------------------------------------------------
# extract_stratal_slice
# ---------------------------------------------------------------------------

def test_extract_single_sample_linear_interp_hits_reflector():
    vol = np.zeros((4, 4, 20), np.float32)
    vol[:, :, 10] = 1.0
    surf = np.full((4, 4), 10.0)
    amp = extract_stratal_slice(vol, surf)
    assert amp.shape == (4, 4)
    assert np.allclose(amp, 1.0)


def test_extract_linear_interp_between_samples():
    # Two unit spikes at samples 9 and 11; index 10 is exactly between them,
    # but the volume is zero AT sample 10, so linear interp gives 0.
    vol = np.zeros((1, 1, 20), np.float32)
    vol[0, 0, 9] = 1.0
    vol[0, 0, 11] = 1.0
    amp = extract_stratal_slice(vol, np.array([[10.0]]))
    assert np.allclose(amp, 0.0)
    # at 9.5, halfway between sample 9 (1.0) and sample 10 (0.0) -> 0.5
    amp2 = extract_stratal_slice(vol, np.array([[9.5]]))
    assert np.allclose(amp2, 0.5)
    # at 10.5, halfway between sample 10 (0.0) and sample 11 (1.0) -> 0.5
    amp3 = extract_stratal_slice(vol, np.array([[10.5]]))
    assert np.allclose(amp3, 0.5)


def test_extract_nearest_order_matches_integer_sample():
    vol = np.zeros((2, 2, 10), np.float32)
    vol[:, :, 4] = 7.0
    surf = np.full((2, 2), 4.7)  # fractional -> nearest index 5 (value 0)
    amp_lin = extract_stratal_slice(vol, surf, order=1)
    amp_near = extract_stratal_slice(vol, surf, order=0)
    # nearest of 4.7 is index 5 -> 0.0
    assert np.allclose(amp_near, 0.0)
    # linear: 0.3 * sample[4]=7 + 0.7 * sample[5]=0 = 2.1
    assert np.allclose(amp_lin, 7.0 * 0.3)


def test_extract_nan_surface_propagates():
    vol = np.ones((2, 2, 5), np.float32)
    surf = np.array([[0.0, np.nan], [2.0, 4.0]])
    amp = extract_stratal_slice(vol, surf)
    assert np.isfinite(amp[0, 0])
    assert np.isnan(amp[0, 1])
    assert np.isfinite(amp[1, 0]) and np.isfinite(amp[1, 1])


def test_extract_window_rms_aggregates():
    vol = np.zeros((1, 1, 11), np.float32)
    vol[0, 0, 4:7] = 3.0  # window of ±1 around index 5 -> [4,5,6] = 3
    surf = np.array([[5.0]])
    rms = extract_stratal_slice(vol, surf, window=1, mode="rms")
    assert np.allclose(rms, 3.0)
    mean = extract_stratal_slice(vol, surf, window=1, mode="mean")
    assert np.allclose(mean, 3.0)
    mx = extract_stratal_slice(vol, surf, window=1, mode="max")
    assert np.allclose(mx, 3.0)


def test_extract_window_clips_to_volume_edge():
    # surface at index 0, window ±2: only indices [0,1,2] are valid.
    vol = np.zeros((1, 1, 5), np.float32)
    vol[0, 0, :3] = 4.0
    surf = np.array([[0.0]])
    rms = extract_stratal_slice(vol, surf, window=2, mode="rms")
    assert np.allclose(rms, 4.0)
    assert np.isfinite(rms).all()


def test_extract_shape_mismatch_raises():
    vol = np.zeros((3, 3, 5), np.float32)
    with pytest.raises(ValueError, match="surface shape"):
        extract_stratal_slice(vol, np.zeros((2, 2)))


# ---------------------------------------------------------------------------
# stratal_slice_volume (end-to-end)
# ---------------------------------------------------------------------------

def test_stratal_slice_volume_returns_stack_for_multiple_fractions():
    vol = np.zeros((6, 6, 20), np.float32)
    vol[:, :, 10] = 1.0
    top = np.full((6, 6), 5.0)
    bot = np.full((6, 6), 15.0)
    maps = stratal_slice_volume(vol, top, bot, fractions=[0.25, 0.5, 0.75])
    assert maps.shape == (3, 6, 6)
    # 0.5 surface = sample 10 -> hits the reflector everywhere
    assert np.allclose(maps[1], 1.0)
    # 0.25 surface = sample 7.5 -> away from reflector
    assert np.allclose(maps[0], 0.0)


def test_stratal_slice_volume_scalar_fraction_returns_2d():
    vol = np.zeros((4, 4, 12), np.float32)
    top = np.full((4, 4), 2.0)
    bot = np.full((4, 4), 10.0)
    amp = stratal_slice_volume(vol, top, bot, fractions=0.5)
    assert amp.shape == (4, 4)


def test_stratal_slice_volume_masks_inverted_pair():
    vol = np.ones((2, 2, 20), np.float32)
    top = np.array([[5.0, 15.0], [5.0, 5.0]])   # (0,1) inverted vs bottom=10
    bot = np.full((2, 2), 10.0)
    maps = stratal_slice_volume(vol, top, bot, fractions=0.5)
    assert np.isfinite(maps).sum() == 3  # the (0,1) cell masked out
    assert np.isnan(maps[0, 1])


def test_stratal_slice_volume_return_surfaces():
    vol = np.zeros((3, 3, 20), np.float32)
    top = np.full((3, 3), 4.0)
    bot = np.full((3, 3), 16.0)
    maps, surfs = stratal_slice_volume(
        vol, top, bot, fractions=[0.25, 0.75], return_surfaces=True
    )
    assert surfs.shape == (2, 3, 3)
    assert np.allclose(surfs[0], 7.0)
    assert np.allclose(surfs[1], 13.0)


def test_stratal_slice_volume_propagates_nan_horizon():
    vol = np.ones((4, 4, 20), np.float32)
    top = np.full((4, 4), 5.0)
    top[2, 2] = np.nan
    bot = np.full((4, 4), 15.0)
    maps = stratal_slice_volume(vol, top, bot, fractions=0.5)
    assert np.isnan(maps[2, 2])
    assert np.isfinite(maps).sum() == 15
