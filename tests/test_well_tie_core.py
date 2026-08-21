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


# ---------------------------------------------------------------------------
# #117: well-tie numerical batch
# ---------------------------------------------------------------------------


def test_generate_synthetic_twt_impulse_stays_at_impulse_position():
    """#117: an even n_wavelet shifted the 'same'-mode synthetic by one sample.
    The wavelet length must be odd (n_ref | 1) so an impulse reflectivity
    produces a synthetic whose peak is exactly at the impulse index."""
    from geoviz_well_tie.synthetic import generate_synthetic_twt

    for n_ref in (39, 40, 41, 60, 100):
        k = n_ref // 2
        reflectivity = np.zeros(n_ref)
        reflectivity[k] = 1.0
        synthetic = generate_synthetic_twt(reflectivity, "ricker", dt_ms=4.0, peak_freq=25.0)
        peak = int(np.argmax(np.abs(synthetic)))
        assert peak == k, f"n_ref={n_ref}: impulse@{k} leaked to {peak}"


def test_synthetic_from_logs_zero_phase_for_odd_raw_aperture():
    """#117: half_length_s=0.063 s / dt 2 ms yields a raw even aperture (64)
    that must be forced odd, otherwise the single-interface synthetic peaks
    one sample below the interface."""
    from geoviz_well_tie.synthetic import synthetic_from_logs

    n = 200
    sonic = np.full(n, 150.0)
    density = np.full(n, 2.0)
    density[n // 2:] = 2.5  # single impedance interface at reflectivity index 99
    interface = n // 2 - 1

    for half_length_s in (0.064, 0.063):  # raw apertures 65 (odd) and 64 (even)
        out = synthetic_from_logs(
            sonic, density, wavelet_freq=30.0, dt_s=0.002, half_length_s=half_length_s
        )
        peak = int(np.argmax(np.abs(out)))
        assert peak == interface, (
            f"half_length_s={half_length_s}: interface spike@{interface} peaked@{peak}"
        )


def test_evaluate_tie_quality_residual_uses_estimated_lag():
    """#117: residual was differenced at zero lag, so a perfectly matching
    rolled copy scored a signal-level residual. After applying the estimated
    lag the overlap residual must vanish."""
    rng = np.random.default_rng(11)
    syn = rng.standard_normal(100)
    seis = np.roll(syn, 10)

    r, lag, residual = evaluate_tie_quality(syn, seis)
    assert lag == 10
    assert np.allclose(residual, 0.0)
    # Overlap for lag=10 on equal-length inputs: samples 0..89.
    assert len(residual) == 100 - 10


def test_correlate_synthetic_to_trace_unequal_length_perfect_match():
    """#117: normalization by max(len) scored a perfect 100-sample synthetic
    against a 1000-sample trace at ~0.1. The per-lag overlap (Pearson)
    normalization must report the true ~1.0 with the correct zero shift."""
    from geoviz_well_tie.auto_tie import correlate_synthetic_to_trace

    rng = np.random.default_rng(0)
    trace = rng.standard_normal(1000)
    synthetic = trace[:100]

    shift, r = correlate_synthetic_to_trace(synthetic, trace)
    assert shift == 0
    assert r > 0.95


def test_correlate_synthetic_to_trace_equal_length_semantics_unchanged():
    """#117 guard: equal-length identical traces keep shift 0 / r == 1, and
    the small-overlap extreme lags must not win the argmax."""
    from geoviz_well_tie.auto_tie import correlate_synthetic_to_trace

    rng = np.random.default_rng(7)
    trace = rng.standard_normal(200)
    shift, r = correlate_synthetic_to_trace(trace, trace.copy())
    assert shift == 0
    assert r == pytest.approx(1.0, abs=1e-9)

    # Delayed copy: synthetic must move later by exactly 5 samples.
    delayed = np.concatenate([rng.standard_normal(5), trace])[:200]
    shift, r = correlate_synthetic_to_trace(trace, delayed)
    assert shift == 5
    assert r > 0.9


def test_extract_statistical_wavelet_short_trace_fallback():
    """#117: a 10-sample trace's autocorrelation (19 samples) cannot supply a
    51-sample window; the old negative-stop slice wrapped around and returned
    16 garbage samples. The explicit Ricker fallback keeps the requested
    length."""
    from geoviz_well_tie.wavelet_engine import extract_statistical_wavelet

    rng = np.random.default_rng(5)
    data = rng.standard_normal(10)
    t, w = extract_statistical_wavelet(data, dt=0.002, length=0.1)
    assert len(w) == 51  # requested n_samples = int(0.1/0.002)+1
    assert len(t) == len(w)
    assert np.all(np.isfinite(w))
    # Exactly the boundary length (26 samples -> autocorr 51) still takes the
    # statistical path, also producing the full 51 samples.
    t2, w2 = extract_statistical_wavelet(rng.standard_normal(26), dt=0.002, length=0.1)
    assert len(w2) == 51


def test_well_tie_calibration_descending_depths_are_reversed():
    """#117: np.interp requires increasing xp; a descending depth log produced
    garbage conversions (depth_to_twt(1990) == -8.7 via negative integrated
    TWT). Descending inputs are now reversed internally."""
    from geoviz_well_tie.calibration import WellTieCalibration

    depths = np.array([2000.0, 1990.0, 1980.0, 1970.0])
    twt = np.array([1000.0, 995.0, 990.0, 985.0])

    cal = WellTieCalibration(depths, twt)
    assert cal.depths[0] < cal.depths[-1]  # stored ascending
    assert cal.depth_to_twt(1990.0) == pytest.approx(995.0)
    assert cal.twt_to_depth(995.0) == pytest.approx(1990.0)
    # Round trip on the sample points.
    for d, t in zip(depths, twt):
        assert cal.twt_to_depth(cal.depth_to_twt(d)) == pytest.approx(d)


def test_from_sonic_descending_depths_positive_monotonic_twt():
    """#117: descending depths integrated to negative TWT; must come out
    positive and increasing from the wellhead."""
    from geoviz_well_tie.calibration import WellTieCalibration

    depths = np.array([2000.0, 1990.0, 1980.0, 1970.0])  # merged-LAS order
    sonic = np.full(4, 145.0)  # µs/m -> 10 m interval = 2.9 ms TWT

    cal = WellTieCalibration.from_sonic(depths, sonic)
    assert np.all(np.diff(cal.twt) > 0)
    assert np.all(cal.twt >= 0.0)
    assert cal.twt[0] == 0.0
    assert cal.twt[-1] == pytest.approx(3 * 2.9, abs=1e-9)
    # After reversal the store is ascending [1970,1980,1990,2000] with
    # TWT zero at the wellhead (1970 m); 1990 m is two intervals (20 m)
    # above the head -> 5.8 ms. The pre-fix code left TWT negative.
    assert cal.depth_to_twt(1990.0) == pytest.approx(5.8, abs=1e-9)
    assert cal.twt_to_depth(cal.depth_to_twt(1985.0)) == pytest.approx(1985.0)


def test_from_sonic_masks_nan_sonic_samples():
    """#117: a NaN sonic interval poisoned the cumulative TWT of every deeper
    sample; non-finite samples are masked before integration."""
    from geoviz_well_tie.calibration import WellTieCalibration

    depths = np.arange(1000.0, 1100.0, 10.0)
    sonic = np.full(len(depths), 145.0)
    sonic[3] = np.nan
    sonic[7] = np.inf

    cal = WellTieCalibration.from_sonic(depths, sonic)
    assert np.all(np.isfinite(cal.twt))
    # Must equal the calibration built from the finite subset only.
    mask = np.isfinite(sonic)
    ref = WellTieCalibration.from_sonic(depths[mask], sonic[mask])
    np.testing.assert_allclose(cal.twt, ref.twt)
    assert np.all(np.diff(cal.twt) > 0)


def test_from_sonic_too_few_finite_samples_raises():
    """#117: fewer than two finite depth/sonic samples cannot form a
    calibration — raise instead of silently producing nonsense."""
    from geoviz_well_tie.calibration import WellTieCalibration

    with pytest.raises(ValueError):
        WellTieCalibration.from_sonic(
            np.array([1000.0, 1010.0]), np.array([np.nan, 150.0])
        )


def test_synthetic_from_logs_interpolates_single_nan():
    """#117: one NaN sonic sample poisoned ~2/3 of the output through the
    convolution; linear interpolation over the sample index now keeps the
    synthetic finite and equal to the clean-input result."""
    from geoviz_well_tie.synthetic import synthetic_from_logs

    n = 100
    sonic = np.full(n, 150.0)
    density = np.full(n, 2.5)
    clean = synthetic_from_logs(sonic, density, wavelet_freq=30.0, dt_s=0.002)

    sonic_nan = sonic.copy()
    sonic_nan[50] = np.nan
    out = synthetic_from_logs(sonic_nan, density, wavelet_freq=30.0, dt_s=0.002)

    assert not np.isnan(out).any()
    np.testing.assert_allclose(out, clean, atol=1e-6)
