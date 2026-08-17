"""Seismic wavelet generation (Ricker, Ormsby)."""

from __future__ import annotations

import numpy as np


def ricker_wavelet(
    n_samples: int,
    dt: float,
    peak_freq: float,
) -> np.ndarray:
    """Generate a Ricker (Mexican-hat) wavelet.

    Args:
        n_samples: Number of samples (should be odd for zero-centred wavelet).
        dt: Sample interval in seconds.
        peak_freq: Peak (dominant) frequency in Hz.

    Returns:
        ``(n_samples,)`` float32 wavelet normalised to unit peak amplitude.
    """
    t = np.arange(n_samples, dtype=np.float64) * dt
    t = t - t[len(t) // 2]
    p2 = (np.pi * peak_freq * t) ** 2
    w = (1.0 - 2.0 * p2) * np.exp(-p2)
    return w.astype(np.float32)


def ormsby_wavelet(
    n_samples: int,
    dt: float,
    f1: float,
    f2: float,
    f3: float,
    f4: float,
) -> np.ndarray:
    """Generate an Ormsby band-pass wavelet.

    Args:
        n_samples: Number of samples (should be odd).
        dt: Sample interval in seconds.
        f1: Low-cut frequency (Hz).
        f2: Low-pass frequency (Hz).
        f3: High-pass frequency (Hz).
        f4: High-cut frequency (Hz).
        Must satisfy ``f1 < f2 <= f3 < f4``.

    Returns:
        ``(n_samples,)`` float32 wavelet normalised to unit peak amplitude.
    """
    t = np.arange(n_samples, dtype=np.float64) * dt
    t = t - t[len(t) // 2]

    # Standard Ormsby (Ryan 1994): each band group is divided by its own
    # bandwidth.  The previous pairing (f1,f4) / (f2,f3) with cross factors
    # (pi*f)^2 produced a shape with a 2x wrong band-weight ratio (#540).
    def _sinc_sq(f):
        return np.sinc(f * t) ** 2

    high = (f4**2 * _sinc_sq(f4) - f3**2 * _sinc_sq(f3)) / max(1e-6, f4 - f3)
    low = (f2**2 * _sinc_sq(f2) - f1**2 * _sinc_sq(f1)) / max(1e-6, f2 - f1)
    w = np.pi * (high - low)
    peak = np.max(np.abs(w))
    if peak > 0:
        w = w / peak
    return w.astype(np.float32)
