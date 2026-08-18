"""Legacy cross-correlation auto-tie evaluator (lag shift + residual).

.. deprecated::
    Prefer :func:`geoviz_well_tie.auto_tie.correlate_synthetic_to_trace` —
    the canonical auto-tie entry point.  This module keeps its own
    normalized coefficient and residual outputs, but its lag sign was the
    mirror image of the canonical one for the same (synthetic, seismic)
    input (+5 vs −5, #845) and has been aligned so "positive lag = the
    synthetic moves later in time".
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def compute_cross_correlation(s1: np.ndarray, s2: np.ndarray) -> Tuple[float, int]:
    """Compute peak cross-correlation coefficient R and best lag shift (samples).

    The lag follows the canonical auto-tie convention
    (:func:`geoviz_well_tie.auto_tie.correlate_synthetic_to_trace`): with
    ``(synthetic, seismic)`` arguments, a positive lag means the synthetic
    should move later in time to line up with the seismic trace. The legacy
    implementation correlated ``(s1, s2)`` directly in that order, which
    reversed the sign for identical input (#845).
    """
    a = np.nan_to_num(np.asarray(s1, dtype=np.float64))
    b = np.nan_to_num(np.asarray(s2, dtype=np.float64))

    n = min(len(a), len(b))
    if n == 0:
        return 0.0, 0

    a = a[:n]
    b = b[:n]

    std_a = np.std(a)
    std_b = np.std(b)
    if std_a == 0 or std_b == 0:
        return 0.0, 0

    corr = np.correlate(a - np.mean(a), b - np.mean(b), mode="full")
    norm = n * std_a * std_b
    corr_norm = corr / max(1e-6, norm)

    best = int(np.argmax(corr_norm))
    max_r = float(corr_norm[best])
    # correlate(a, b) peaks at +k when b trails a by k; the canonical
    # (seismic-first) correlation therefore reports -k for the same pair.
    # Negating the raw offset reproduces the canonical sign for the
    # (synthetic, seismic) argument order.
    lag = -(best - (n - 1))

    return max_r, lag


def evaluate_tie_quality(synthetic: np.ndarray, seismic: np.ndarray) -> Tuple[float, int, np.ndarray]:
    """Evaluate well-seismic tie quality. Returns (R, lag_shift, amplitude_residual).

    ``lag_shift`` is positive when the synthetic should move later in time
    to align with the seismic trace (canonical auto-tie convention, #845).
    """
    max_r, lag = compute_cross_correlation(synthetic, seismic)

    n = min(len(synthetic), len(seismic))
    syn_crop = synthetic[:n]
    seis_crop = seismic[:n]

    residual = np.abs(syn_crop - seis_crop)
    return max_r, lag, residual