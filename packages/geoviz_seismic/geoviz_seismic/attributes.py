"""Seismic attribute calculations (envelope, phase, frequency, RMS, etc.)."""
from __future__ import annotations

import numpy as np


def _analytic_signal(data: np.ndarray, axis: int = -1) -> np.ndarray:
    from scipy.signal import hilbert
    return hilbert(data, axis=axis)


def compute_envelope(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Envelope (instantaneous amplitude) via Hilbert transform."""
    return np.abs(_analytic_signal(data, axis)).astype(np.float32)


def compute_instantaneous_phase(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Instantaneous phase (radians, [-pi, pi]) via Hilbert transform."""
    return np.angle(_analytic_signal(data, axis)).astype(np.float32)


def compute_instantaneous_frequency(
    data: np.ndarray,
    sample_interval: float = 1.0,
    axis: int = -1,
) -> np.ndarray:
    """Instantaneous frequency via time-derivative of unwrapped phase.

    Args:
        data: Seismic amplitude array.
        sample_interval: Sample interval in the same unit as desired output
            (e.g. seconds → Hz, milliseconds → kHz).
        axis: Axis along which to compute (default: last / time).

    Returns:
        Frequency array (same shape). Edges are forward/backward diff.
    """
    phase = np.unwrap(np.angle(_analytic_signal(data, axis)), axis=axis)
    freq = np.gradient(phase, sample_interval, axis=axis) / (2 * np.pi)
    return freq.astype(np.float32)


def compute_rms_amplitude(
    data: np.ndarray,
    window: int = 21,
    axis: int = -1,
) -> np.ndarray:
    """Windowed RMS amplitude.

    Args:
        data: Seismic amplitude array.
        window: Half-window length (total window = 2*window+1 samples).
        axis: Axis along which to compute.

    Returns:
        RMS amplitude array (same shape, non-negative).
    """
    kernel = np.ones(2 * window + 1) / (2 * window + 1)
    # Expand kernel to match data dimensions for convolve
    for _ in range(data.ndim - 1):
        kernel = kernel[np.newaxis]
    # Move target axis to last position for uniform_filter-like behaviour
    data_sq = data.astype(np.float64) ** 2
    # Use uniform_filter1d via cumsum trick for speed
    from scipy.ndimage import uniform_filter1d
    mean_sq = uniform_filter1d(data_sq, size=2 * window + 1, axis=axis, mode="reflect")
    return np.sqrt(np.maximum(mean_sq, 0)).astype(np.float32)


def compute_sweetness(
    data: np.ndarray,
    sample_interval: float = 1.0,
    axis: int = -1,
) -> np.ndarray:
    """Sweetness attribute: envelope / sqrt(instantaneous frequency).

    Highlights high-amplitude, low-frequency zones (hydrocarbon indicators).
    Near-zero frequency values are clamped to avoid division issues.
    """
    env = compute_envelope(data, axis)
    freq = compute_instantaneous_frequency(data, sample_interval, axis)
    freq_safe = np.where(np.abs(freq) < 1e-6, 1e-6, np.abs(freq))
    return (env / np.sqrt(freq_safe)).astype(np.float32)


def compute_relative_impedance(data: np.ndarray, axis: int = -1) -> np.ndarray:
    """Relative acoustic impedance via running integration.

    Approximates impedance without full inversion. Assumes trace axis.
    """
    return np.cumsum(data, axis=axis).astype(np.float32)
