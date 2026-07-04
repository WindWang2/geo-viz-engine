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
