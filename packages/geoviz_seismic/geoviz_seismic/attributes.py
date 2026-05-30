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


def compute_spectral_decomposition(
    data: np.ndarray,
    freq_bands: list[tuple[float, float]],
    sample_interval: float = 1.0,
    axis: int = -1,
) -> np.ndarray:
    """Spectral decomposition via STFT bandpass filter bank.

    Decomposes seismic data into frequency-band energy volumes using
    short-time Fourier transform. Each band produces an envelope-like
    attribute representing energy in that frequency range.

    Args:
        data: 2-D seismic amplitude array (n_samples x n_traces).
        freq_bands: List of (low_freq, high_freq) tuples in Hz.
            E.g. [(10, 20), (20, 40), (40, 60)] for three bands.
        sample_interval: Sample interval in seconds.
        axis: Time/sample axis (default: last).

    Returns:
        3-D array of shape (n_bands, n_samples, n_traces) with float32
        envelope energy per band.
    """
    from scipy.signal import stft, istft

    data = np.asarray(data, dtype=np.float32)
    n_bands = len(freq_bands)

    # STFT parameters — window of ~200ms for decent freq resolution
    nperseg = min(64, data.shape[axis])
    noverlap = nperseg // 2

    # Work along the time axis
    data_ax = np.moveaxis(data, axis, -1)
    orig_shape = data_ax.shape
    flat = data_ax.reshape(-1, orig_shape[-1])

    f, t_stft, Zxx = stft(flat, fs=1.0 / sample_interval, nperseg=nperseg,
                           noverlap=noverlap, axis=-1)

    result = np.zeros((n_bands, *data.shape), dtype=np.float32)

    for i, (flo, fhi) in enumerate(freq_bands):
        mask = (f >= flo) & (f <= fhi)
        if not np.any(mask):
            continue
        Zxx_band = np.zeros_like(Zxx)
        # Zxx shape: (n_traces, n_freqs, n_time_frames); mask applies to axis 1
        Zxx_band[:, mask, :] = Zxx[:, mask, :]
        _, reconstructed = istft(Zxx_band, fs=1.0 / sample_interval,
                                 nperseg=nperseg, noverlap=noverlap)
        # Trim/pad to match original length
        n_samples = orig_shape[-1]
        if reconstructed.shape[-1] > n_samples:
            reconstructed = reconstructed[:, :n_samples]
        elif reconstructed.shape[-1] < n_samples:
            pad = np.zeros((*reconstructed.shape[:-1], n_samples - reconstructed.shape[-1]))
            reconstructed = np.concatenate([reconstructed, pad], axis=-1)
        # Compute envelope of band-limited signal
        env = np.abs(_analytic_signal(
            np.moveaxis(reconstructed.reshape(orig_shape), -1, axis), axis=axis
        ))
        result[i] = env.astype(np.float32)

    return result


def fuse_rgb(
    attr_r: np.ndarray,
    attr_g: np.ndarray,
    attr_b: np.ndarray,
    clip_pct: float = 99.0,
) -> np.ndarray:
    """Fuse three attribute arrays into an RGB image.

    Each attribute is independently percentile-clipped to [0, 1] and
    scaled to [0, 255] uint8. The three channels are stacked into an
    (H, W, 3) uint8 array.

    Args:
        attr_r: Red channel attribute (2-D float32).
        attr_g: Green channel attribute (2-D float32).
        attr_b: Blue channel attribute (2-D float32).
        clip_pct: Percentile for clipping (default 99.0).

    Returns:
        (H, W, 3) uint8 RGB image.
    """
    def _normalize(a: np.ndarray) -> np.ndarray:
        lo = np.nanpercentile(a, 100.0 - clip_pct)
        hi = np.nanpercentile(a, clip_pct)
        if hi <= lo:
            hi = np.nanmax(a)
            lo = np.nanmin(a)
        if hi <= lo:
            return np.zeros_like(a, dtype=np.float32)
        return np.clip((a - lo) / (hi - lo), 0.0, 1.0)

    r = (_normalize(attr_r) * 255).astype(np.uint8)
    g = (_normalize(attr_g) * 255).astype(np.uint8)
    b = (_normalize(attr_b) * 255).astype(np.uint8)
    return np.stack([r, g, b], axis=-1)
