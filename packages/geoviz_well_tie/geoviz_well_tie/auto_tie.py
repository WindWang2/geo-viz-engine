"""Auto-tie: cross-correlation bulk time-shift estimation."""
from __future__ import annotations

import numpy as np


def auto_tie(seismic: np.ndarray, synthetic: np.ndarray) -> int:
    """Estimate optimal bulk time shift via cross-correlation.

    Args:
        seismic: Real seismic trace ``(N,)``.
        synthetic: Synthetic trace ``(M,)``.

    Returns:
        Integer shift in samples. Positive = synthetic should shift down
        (later in time). Negative = synthetic should shift up.
    """
    seismic = np.asarray(seismic, dtype=np.float64)
    synthetic = np.asarray(synthetic, dtype=np.float64)
    n = min(len(seismic), len(synthetic))
    seismic = seismic[:n]
    synthetic = synthetic[:n]

    corr = np.correlate(seismic, synthetic, mode="full")
    # Peak of correlation → optimal lag
    peak_idx = int(np.argmax(np.abs(corr)))
    # Lag relative to zero-shift (center of full correlation)
    lag = peak_idx - (n - 1)
    return -lag  # negate: positive lag means synthetic is late


def auto_tie_with_quality(
    seismic: np.ndarray,
    synthetic: np.ndarray,
) -> tuple[int, float]:
    """Estimate shift and return correlation coefficient.

    Returns:
        (shift_samples, correlation_coefficient) tuple.
    """
    seismic = np.asarray(seismic, dtype=np.float64)
    synthetic = np.asarray(synthetic, dtype=np.float64)
    n = min(len(seismic), len(synthetic))
    seismic = seismic[:n]
    synthetic = synthetic[:n]

    corr = np.correlate(seismic, synthetic, mode="full")
    peak_idx = int(np.argmax(np.abs(corr)))
    lag = peak_idx - (n - 1)

    # Normalized correlation coefficient at peak
    norm = np.sqrt(np.sum(seismic ** 2) * np.sum(synthetic ** 2))
    if norm < 1e-12:
        cc = 0.0
    else:
        cc = float(corr[peak_idx] / norm)

    return -lag, cc
