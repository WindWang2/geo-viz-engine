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
