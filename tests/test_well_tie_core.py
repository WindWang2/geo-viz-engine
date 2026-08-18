"""Unit tests for geoviz_well_tie core domain engine."""
import numpy as np
import pytest

from geoviz_well_tie.wavelet_engine import generate_ricker_wavelet, generate_ormsby_wavelet, extract_statistical_wavelet
from geoviz_well_tie.synthetic_generator import compute_impedance, compute_reflectivity, generate_synthetic_seismogram
from geoviz_well_tie.tie_evaluator import evaluate_tie_quality, compute_cross_correlation

def test_ricker_wavelet_generation():
    t, w = generate_ricker_wavelet(freq=30.0, dt=0.002, length=0.1)
    assert len(t) == len(w)
    assert len(w) % 2 == 1  # Odd length centered at zero
    assert pytest.approx(w[len(w) // 2], abs=1e-3) == 1.0  # Normalized peak

def test_ormsby_wavelet_generation():
    t, w = generate_ormsby_wavelet(f1=5, f2=10, f3=40, f4=50, dt=0.002, length=0.1)
    assert len(t) == len(w)
    assert np.max(np.abs(w)) > 0.0

def test_statistical_wavelet_extraction():
    seismic_data = np.random.randn(500)
    t, w = extract_statistical_wavelet(seismic_data, dt=0.002, length=0.1)
    assert len(t) == len(w)
    assert np.max(np.abs(w)) > 0.0

def test_impedance_and_reflectivity():
    sonic = np.array([300.0, 300.0, 200.0, 200.0])  # us/m
    density = np.array([2.2, 2.2, 2.5, 2.5])        # g/cm3

    ai = compute_impedance(sonic, density)
    assert len(ai) == 4
    assert ai[0] < ai[2]  # Higher velocity and density -> higher impedance

    rc = compute_reflectivity(ai)
    assert len(rc) == 3
    assert rc[1] > 0.0  # Positive reflection at interface

def test_synthetic_seismogram_generation():
    sonic = np.linspace(300, 200, 100)
    density = np.linspace(2.0, 2.5, 100)
    t, w = generate_ricker_wavelet(freq=30.0, dt=0.002, length=0.1)

    syn = generate_synthetic_seismogram(sonic, density, w)
    assert len(syn) == 99

def test_tie_evaluator():
    s1 = np.sin(np.linspace(0, 10, 100))
    s2 = np.sin(np.linspace(0, 10, 100))

    r, lag, residual = evaluate_tie_quality(s1, s2)
    assert pytest.approx(r, abs=1e-2) == 1.0
    assert lag == 0


def _reference_ormsby(t: np.ndarray, f1: float, f2: float, f3: float, f4: float) -> np.ndarray:
    """Independent standard-Ormsby reference (Ryan 1994), peak-normalized."""
    def sinc_sq(f):
        return np.sinc(f * t) ** 2

    high = (f4**2 * sinc_sq(f4) - f3**2 * sinc_sq(f3)) / (f4 - f3)
    low = (f2**2 * sinc_sq(f2) - f1**2 * sinc_sq(f1)) / (f2 - f1)
    w = np.pi * (high - low)
    peak = np.max(np.abs(w))
    return w / peak if peak > 0 else w


def test_ormsby_wavelet_matches_standard_formula():
    """wavelet.ormsby_wavelet must match the standard Ormsby shape (#540)."""
    from geoviz_well_tie.wavelet import ormsby_wavelet

    f1, f2, f3, f4 = 5.0, 10.0, 40.0, 50.0
    dt = 0.002
    n = 201
    t = (np.arange(n, dtype=np.float64) * dt) - (n // 2) * dt
    expected = _reference_ormsby(t, f1, f2, f3, f4)

    got = ormsby_wavelet(n, dt, f1, f2, f3, f4)
    np.testing.assert_allclose(got, expected, atol=1e-4)
    # The old implementation's f4/f2 contribution ratio at t=0 was ~26 vs
    # the true 12.5 — the shape, not just the scale, must agree.
    assert np.abs(np.max(np.abs(got)) - 1.0) < 1e-6


def test_generate_ormsby_wavelet_matches_standard_formula():
    """wavelet_engine.generate_ormsby_wavelet must not divide by the product
    of both bandwidths (#540)."""
    f1, f2, f3, f4 = 5.0, 10.0, 40.0, 50.0
    dt = 0.002
    length = 0.1
    n = int(length / dt)
    if n % 2 == 0:
        n += 1
    t = np.linspace(-length / 2, length / 2, n)
    expected = _reference_ormsby(t, f1, f2, f3, f4)

    t_got, got = generate_ormsby_wavelet(f1, f2, f3, f4, dt=dt, length=length)
    np.testing.assert_allclose(t_got, t)
    np.testing.assert_allclose(got, expected, atol=1e-4)


def test_ormsby_band_weights_ratio_at_zero():
    """At t=0 the two band groups contribute pi*(f4+f3) - pi*(f2+f1); the
    ratio of the high to low group is (f4+f3)/(f2+f1) = 6.0 for the defaults —
    the old product-denominator code made it 2x weaker (#540)."""
    f1, f2, f3, f4 = 5.0, 10.0, 40.0, 50.0
    dt = 0.002
    n = 201
    t = (np.arange(n, dtype=np.float64) * dt) - (n // 2) * dt

    def sinc_sq(f):
        return np.sinc(f * t) ** 2

    high = (f4**2 * sinc_sq(f4) - f3**2 * sinc_sq(f3)) / (f4 - f3)
    low = (f2**2 * sinc_sq(f2) - f1**2 * sinc_sq(f1)) / (f2 - f1)
    assert high[0] / low[0] == pytest.approx((f4 + f3) / (f2 + f1), rel=1e-6)


def test_tie_evaluator_lag_sign_matches_canonical_auto_tie():
    """#845: the legacy cross-correlation reported the OPPOSITE lag sign of
    the canonical auto_tie for identical input (+5 vs −5). Positive lag =
    the synthetic moves later in time to align with the seismic trace."""
    from geoviz_well_tie.auto_tie import correlate_synthetic_to_trace

    rng = np.random.default_rng(3)
    syn = rng.standard_normal(60)
    # Field trace = synthetic delayed by 5 samples (plus leading noise).
    seis = np.concatenate([rng.standard_normal(5), syn[:55]])

    r, lag = compute_cross_correlation(syn, seis)
    shift, _ = correlate_synthetic_to_trace(syn, seis)
    assert lag == shift, (
        f"legacy lag {lag} must match the canonical shift {shift} for the "
        f"same (synthetic, seismic) input"
    )
    assert lag == 5, "synthetic must move later (down) by 5 samples"
    assert r > 0.0


def test_tie_evaluator_lag_zero_for_aligned_traces():
    """#845: perfectly aligned traces must keep lag == 0."""
    rng = np.random.default_rng(9)
    syn = rng.standard_normal(80)
    r, lag, residual = evaluate_tie_quality(syn, syn.copy())
    assert lag == 0
    assert np.allclose(residual, 0.0)
