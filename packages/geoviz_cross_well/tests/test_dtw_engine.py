"""Tests for DTWEngine."""
import numpy as np
import pytest

from geoviz_cross_well.dtw_engine import DTWEngine, DTWResult


def test_identical_curves_zero_cost():
    engine = DTWEngine()
    curve = np.sin(np.linspace(0, 4 * np.pi, 100))
    depths = np.linspace(0, 1000, 100)

    result = engine.correlate(curve, depths, curve.copy(), depths)
    assert result.cost < 0.01
    assert result.confidence > 0.99


def test_shifted_curve_correct_offset():
    engine = DTWEngine()
    n = 100
    ref_curve = np.random.randn(n).cumsum()
    ref_depths = np.linspace(0, 1000, n)

    # Target curve is shifted by 10 samples
    shift = 10
    target_curve = np.roll(ref_curve, shift)
    target_depths = np.linspace(0, 1000, n)

    result = engine.correlate(ref_curve, ref_depths, target_curve, target_depths)
    assert result.suggested_depth > 0
    assert result.cost < 1.0


def test_band_radius_constraint():
    engine = DTWEngine()
    n = 50
    ref = np.random.randn(n)
    tgt = np.random.randn(n)
    ref_d = np.linspace(0, 500, n)
    tgt_d = np.linspace(0, 500, n)

    # With very tight band, should still complete without error
    result = engine.correlate(ref, ref_d, tgt, tgt_d, band_radius=5)
    assert isinstance(result, DTWResult)
    assert 0.0 <= result.cost <= 1.0


def test_short_curves():
    engine = DTWEngine()
    ref = np.array([1.0])
    tgt = np.array([2.0])
    ref_d = np.array([100.0])
    tgt_d = np.array([200.0])

    result = engine.correlate(ref, ref_d, tgt, tgt_d)
    assert result.cost == 1.0
    assert result.confidence == 0.0


def test_empty_curves():
    engine = DTWEngine()
    ref = np.array([])
    tgt = np.array([])
    result = engine.correlate(ref, np.array([]), tgt, np.array([]))
    assert result.confidence == 0.0


def test_ref_depth_propagates_correctly():
    """11.6-F regression: suggested_depth must follow ref_depth, not n//2."""
    engine = DTWEngine()
    n = 200
    rng = np.random.default_rng(0)
    ref_curve = rng.standard_normal(n).cumsum()
    ref_depths = np.linspace(1000.0, 3000.0, n)

    shift = 25
    target_curve = np.roll(ref_curve, shift)
    target_depths = ref_depths.copy()
    depth_per_sample = (ref_depths[-1] - ref_depths[0]) / (n - 1)
    expected_offset = shift * depth_per_sample

    # Three different ref_depths should yield three different suggested depths
    for ref_depth in (1300.0, 2000.0, 2700.0):
        result = engine.correlate(
            ref_curve, ref_depths, target_curve, target_depths,
            ref_depth=ref_depth,
        )
        # DTW on shifted curves should suggest a depth offset by ~shift samples
        err = abs((result.suggested_depth - ref_depth) - expected_offset)
        assert err < depth_per_sample * 3, (
            f"ref_depth={ref_depth} suggested={result.suggested_depth} "
            f"expected_offset={expected_offset} err={err}"
        )


def test_ref_depth_default_is_midpoint():
    """Backward compat: omitting ref_depth keeps legacy n//2 behavior."""
    engine = DTWEngine()
    n = 100
    rng = np.random.default_rng(1)
    curve = rng.standard_normal(n).cumsum()
    depths = np.linspace(0, 1000, n)

    res_default = engine.correlate(curve, depths, curve.copy(), depths)
    res_midpoint = engine.correlate(
        curve, depths, curve.copy(), depths, ref_depth=float(depths[n // 2]),
    )
    assert abs(res_default.suggested_depth - res_midpoint.suggested_depth) < 1e-6
