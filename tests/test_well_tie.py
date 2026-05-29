import numpy as np
import pytest

from geoviz_well_tie.wavelet import ricker_wavelet, ormsby_wavelet
from geoviz_well_tie.synthetic import compute_reflectivity, generate_synthetic
from geoviz_well_tie.calibration import WellTieCalibration


# --- Wavelet tests ---

def test_ricker_shape_and_peak():
    w = ricker_wavelet(61, dt=0.001, peak_freq=25.0)
    assert w.shape == (61,)
    assert w.dtype == np.float32
    # Peak should be near centre
    assert np.argmax(np.abs(w)) == 30


def test_ricker_unit_amplitude():
    w = ricker_wavelet(81, dt=0.001, peak_freq=30.0)
    np.testing.assert_allclose(np.max(np.abs(w)), 1.0, atol=0.01)


def test_ricker_symmetry():
    w = ricker_wavelet(51, dt=0.001, peak_freq=20.0)
    np.testing.assert_allclose(w, w[::-1], atol=1e-6)


def test_ormsby_shape():
    w = ormsby_wavelet(81, dt=0.001, f1=5, f2=10, f3=40, f4=50)
    assert w.shape == (81,)
    assert w.dtype == np.float32


def test_ormsby_symmetry():
    w = ormsby_wavelet(101, dt=0.001, f1=5, f2=10, f3=40, f4=50)
    np.testing.assert_allclose(w, w[::-1], atol=1e-5)


# --- Reflectivity tests ---

def test_reflectivity_single_interface():
    sonic = np.array([200.0, 200.0, 100.0, 100.0], dtype=np.float32)
    density = np.array([2.5, 2.5, 2.5, 2.5], dtype=np.float32)
    ref = compute_reflectivity(sonic, density)
    assert ref.shape == (3,)
    assert ref.dtype == np.float32
    # At interface between sample 1 and 2: velocity jumps from 5000 to 10000 m/s
    # Z1 = 5000*2.5 = 12500, Z2 = 10000*2.5 = 25000
    # R = (25000 - 12500) / (25000 + 12500) = 0.333
    np.testing.assert_allclose(ref[1], 1.0 / 3.0, atol=0.01)


def test_reflectivity_uniform():
    sonic = np.full(10, 200.0)
    density = np.full(10, 2.5)
    ref = compute_reflectivity(sonic, density)
    np.testing.assert_allclose(ref, 0.0, atol=1e-6)


def test_reflectivity_length():
    n = 100
    ref = compute_reflectivity(np.ones(n), np.ones(n))
    assert len(ref) == n - 1


# --- Synthetic seismogram tests ---

def test_synthetic_nonzero():
    sonic = np.array([200.0, 150.0, 100.0, 150.0, 200.0])
    density = np.array([2.0, 2.5, 3.0, 2.5, 2.0])
    ref = compute_reflectivity(sonic, density)
    w = ricker_wavelet(21, dt=0.001, peak_freq=25.0)
    syn = generate_synthetic(ref, w)
    assert syn.shape == ref.shape
    assert syn.dtype == np.float32
    assert np.max(np.abs(syn)) > 0


def test_synthetic_zero_reflectivity():
    ref = np.zeros(50, dtype=np.float32)
    w = ricker_wavelet(21, dt=0.001, peak_freq=25.0)
    syn = generate_synthetic(ref, w)
    np.testing.assert_allclose(syn, 0.0, atol=1e-6)


# --- Calibration tests ---

def test_calibration_depth_to_twt():
    depths = np.array([0.0, 100.0, 200.0, 300.0])
    twt = np.array([0.0, 50.0, 110.0, 180.0])
    cal = WellTieCalibration(depths, twt)
    assert cal.depth_to_twt(100.0) == pytest.approx(50.0)
    assert cal.depth_to_twt(150.0) == pytest.approx(80.0)


def test_calibration_twt_to_depth():
    depths = np.array([0.0, 100.0, 200.0, 300.0])
    twt = np.array([0.0, 50.0, 110.0, 180.0])
    cal = WellTieCalibration(depths, twt)
    assert cal.twt_to_depth(50.0) == pytest.approx(100.0)


def test_calibration_resample():
    depths = np.linspace(0, 300, 301)
    twt = np.linspace(0, 180, 301)
    log = np.sin(depths / 50.0)  # arbitrary log
    cal = WellTieCalibration(depths, twt)
    resampled = cal.resample_to_twt(log, dt_ms=2.0)
    assert resampled.dtype == np.float32
    assert len(resampled) > 0


def test_calibration_from_sonic():
    depths = np.linspace(0, 1000, 501)
    sonic = np.full(501, 200.0)  # uniform slowness
    cal = WellTieCalibration.from_sonic(depths, sonic)
    assert len(cal.depths) == 501
    assert len(cal.twt) == 501
    assert cal.twt[0] == 0.0
    assert cal.twt[-1] > 0  # TWT should increase with depth


def test_calibration_mismatched_lengths():
    with pytest.raises(ValueError, match="same length"):
        WellTieCalibration(np.array([0, 1, 2]), np.array([0, 1]))
