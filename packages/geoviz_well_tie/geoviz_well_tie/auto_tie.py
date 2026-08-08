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


def correlate_synthetic_to_trace(
    synthetic: np.ndarray,
    seismic_trace: np.ndarray,
) -> tuple[int, float]:
    """Cross-correlate a synthetic against a field trace, on mean-removed z-scores.

    Promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::
    WellSeismicTieCalibration.auto_correlate``.

    Differs from :func:`auto_tie_with_quality` in three ways, which is why both
    exist: this one (a) removes the mean before correlating, so a DC offset in the
    field trace cannot dominate the peak, (b) does **not** truncate the two inputs
    to a common length, and (c) takes ``argmax`` of the signed correlation rather
    than its absolute value, so it will not lock onto a polarity-reversed match.

    Args:
        synthetic: Synthetic trace ``(M,)``.
        seismic_trace: Real seismic trace ``(N,)``.

    Returns:
        ``(shift_samples, correlation_coefficient)``. Positive shift means the
        synthetic should move later in time to line up with the field trace. Both
        values are ``(0, 0.0)`` when either input is empty or effectively constant.
    """
    synthetic = np.asarray(synthetic, dtype=np.float64)
    seismic_trace = np.asarray(seismic_trace, dtype=np.float64)
    if len(synthetic) == 0 or len(seismic_trace) == 0:
        return 0, 0.0

    s_std = np.std(synthetic)
    t_std = np.std(seismic_trace)
    if s_std < 1e-10 or t_std < 1e-10:
        return 0, 0.0

    s_norm = (synthetic - np.mean(synthetic)) / s_std
    t_norm = (seismic_trace - np.mean(seismic_trace)) / t_std

    corr = np.correlate(t_norm, s_norm, mode="full")
    corr /= max(len(s_norm), len(t_norm))

    best_idx = int(np.argmax(corr))
    shift = best_idx - (len(s_norm) - 1)
    return shift, min(float(corr[best_idx]), 1.0)
