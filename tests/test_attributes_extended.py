import numpy as np
import pytest

from geoviz_seismic.attributes import (
    compute_envelope,
    compute_instantaneous_phase,
    compute_instantaneous_frequency,
    compute_rms_amplitude,
    compute_sweetness,
    compute_relative_impedance,
)


def test_instantaneous_frequency_sine():
    """Instantaneous frequency of a 10 Hz sine at 1 kHz fs should be ~10 Hz."""
    fs = 1000.0
    t = np.linspace(0, 1, int(fs), dtype=np.float32)
    data = np.sin(2 * np.pi * 10 * t).astype(np.float32)
    freq = compute_instantaneous_frequency(data, sample_interval=1.0 / fs)
    assert freq.shape == data.shape
    assert freq.dtype == np.float32
    # Interior samples should be close to 10 Hz
    np.testing.assert_allclose(freq[50:-50], 10.0, atol=1.0)


def test_instantaneous_frequency_2d():
    data = np.random.randn(100, 50).astype(np.float32)
    freq = compute_instantaneous_frequency(data, axis=0)
    assert freq.shape == data.shape
    assert freq.dtype == np.float32


def test_rms_amplitude_nonneg():
    data = np.random.randn(200).astype(np.float32)
    rms = compute_rms_amplitude(data, window=10)
    assert rms.shape == data.shape
    assert rms.dtype == np.float32
    assert np.all(rms >= 0)


def test_rms_amplitude_2d():
    data = np.random.randn(100, 50).astype(np.float32)
    rms = compute_rms_amplitude(data, window=5, axis=0)
    assert rms.shape == data.shape
    assert np.all(rms >= 0)


def test_rms_amplitude_constant():
    data = np.ones(100, dtype=np.float32) * 3.0
    rms = compute_rms_amplitude(data, window=10)
    np.testing.assert_allclose(rms[20:-20], 3.0, atol=0.1)


def test_sweetness_nonneg():
    data = np.random.randn(500).astype(np.float32)
    sweet = compute_sweetness(data)
    assert sweet.shape == data.shape
    assert sweet.dtype == np.float32
    # Sweetness should be non-negative (envelope is always >= 0)
    assert np.all(sweet >= 0)


def test_relative_impedance_cumsum():
    data = np.ones(100, dtype=np.float32)
    imp = compute_relative_impedance(data)
    assert imp.shape == data.shape
    assert imp.dtype == np.float32
    np.testing.assert_allclose(imp, np.arange(1, 101, dtype=np.float32))


def test_relative_impedance_2d():
    data = np.random.randn(50, 30).astype(np.float32)
    imp = compute_relative_impedance(data, axis=0)
    assert imp.shape == data.shape
    # First sample along axis should equal original data
    np.testing.assert_allclose(imp[0], data[0])
