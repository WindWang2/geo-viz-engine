"""Reflectivity computation and synthetic seismogram generation."""

from __future__ import annotations

import numpy as np


def compute_reflectivity(
    sonic: np.ndarray,
    density: np.ndarray,
) -> np.ndarray:
    """Compute acoustic impedance and P-wave reflectivity from well logs.

    Reflectivity at interface *i*::

        R_i = (Z_{i+1} - Z_i) / (Z_{i+1} + Z_i)

    where ``Z = sonic^{-1} × density`` (acoustic impedance).

    Args:
        sonic: Sonic transit time in µs/m (slowness). Shape ``(N,)``.
        density: Bulk density in g/cm³. Shape ``(N,)``.

    Returns:
        ``(N-1,)`` float32 reflectivity series. First sample is at the
        first interface, last sample at the ``(N-2)``-th interface.
    """
    sonic = np.asarray(sonic, dtype=np.float64)
    density = np.asarray(density, dtype=np.float64)
    velocity = 1.0e6 / sonic  # µs/m → m/s
    impedance = velocity * density
    z_upper = impedance[:-1]
    z_lower = impedance[1:]
    denom = z_upper + z_lower
    denom = np.where(np.abs(denom) < 1e-12, 1e-12, denom)
    reflectivity = (z_lower - z_upper) / denom
    return reflectivity.astype(np.float32)


def generate_synthetic(
    reflectivity: np.ndarray,
    wavelet: np.ndarray,
) -> np.ndarray:
    """Convolve reflectivity with a wavelet to produce a synthetic seismogram.

    Args:
        reflectivity: ``(N,)`` reflectivity series from :func:`compute_reflectivity`.
        wavelet: ``(M,)`` wavelet from :func:`ricker_wavelet` or :func:`ormsby_wavelet`.

    Returns:
        ``(N,)`` float32 synthetic trace.
    """
    reflectivity = np.asarray(reflectivity, dtype=np.float64)
    wavelet = np.asarray(wavelet, dtype=np.float64)
    n_ref = len(reflectivity)
    if n_ref == 0:
        return np.empty(0, dtype=np.float32)
    # Ensure output length matches reflectivity by padding reflectivity when
    # the wavelet is longer.
    if len(wavelet) > n_ref:
        pad = len(wavelet) - n_ref
        padded = np.pad(reflectivity, pad)
        conv = np.convolve(padded, wavelet, mode="same")
        # Extract the centre portion matching original reflectivity positions
        start = pad
        synthetic = conv[start:start + n_ref]
    else:
        synthetic = np.convolve(reflectivity, wavelet, mode="same")
    return synthetic.astype(np.float32)


def generate_synthetic_twt(
    reflectivity: np.ndarray,
    wavelet_type: str = "ricker",
    dt_ms: float = 4.0,
    peak_freq: float = 25.0,
    *,
    f1: float = 5.0,
    f2: float = 10.0,
    f3: float = 40.0,
    f4: float = 50.0,
) -> np.ndarray:
    """Unit-safe wrapper: generate synthetic accepting *dt_ms* (milliseconds).

    Internally converts to seconds for wavelet generation, then convolves.

    Args:
        reflectivity: ``(N,)`` reflectivity series.
        wavelet_type: ``"ricker"`` or ``"ormsby"``.
        dt_ms: Sample interval in milliseconds.
        peak_freq: Peak frequency in Hz (Ricker only).
        f1..f4: Ormsby frequency parameters (Hz).

    Returns:
        ``(N,)`` float32 synthetic trace.
    """
    from .wavelet import ricker_wavelet, ormsby_wavelet

    dt_sec = dt_ms / 1000.0
    n_ref = len(reflectivity)
    n_wavelet = min(81, max(21, n_ref if n_ref > 0 else 21))

    if wavelet_type == "ormsby":
        w = ormsby_wavelet(n_wavelet, dt=dt_sec, f1=f1, f2=f2, f3=f3, f4=f4)
    else:
        w = ricker_wavelet(n_wavelet, dt=dt_sec, peak_freq=peak_freq)

    return generate_synthetic(reflectivity, w)
