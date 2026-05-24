import numpy as np
import pytest

from geoviz_seismic.attributes import compute_envelope, compute_instantaneous_phase


def test_envelope_sine():
    """Envelope of a pure sine wave should be approximately constant."""
    t = np.linspace(0, 1, 500, dtype=np.float32)
    data = np.sin(2 * np.pi * 10 * t).astype(np.float32)
    env = compute_envelope(data)
    assert env.shape == data.shape
    # Envelope of a pure sinusoid should be close to 1.0
    np.testing.assert_allclose(env[50:-50], 1.0, atol=0.05)


def test_envelope_2d():
    """Envelope along time axis of 2D data."""
    data = np.random.randn(100, 50).astype(np.float32)
    env = compute_envelope(data, axis=0)
    assert env.shape == data.shape
    assert env.dtype == np.float32
    assert np.all(env >= 0)


def test_envelope_preserves_positive():
    """Envelope is always non-negative."""
    data = np.random.randn(200).astype(np.float32)
    env = compute_envelope(data)
    assert np.all(env >= 0)


def test_instantaneous_phase_range():
    """Instantaneous phase should be in [-pi, pi]."""
    t = np.linspace(0, 1, 500, dtype=np.float32)
    data = np.sin(2 * np.pi * 10 * t).astype(np.float32)
    phase = compute_instantaneous_phase(data)
    assert phase.shape == data.shape
    assert np.all(phase >= -np.pi)
    assert np.all(phase <= np.pi)
