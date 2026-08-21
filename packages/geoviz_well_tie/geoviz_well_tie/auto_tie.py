"""Auto-tie: cross-correlation bulk time-shift estimation."""
from __future__ import annotations

import warnings

import numpy as np


def correlate_synthetic_to_trace(
    synthetic: np.ndarray,
    seismic_trace: np.ndarray,
) -> tuple[int, float]:
    """Cross-correlate a synthetic against a field trace, on mean-removed z-scores.

    Promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::
    WellSeismicTieCalibration.auto_correlate``.

    This is the canonical auto-tie entry point. The legacy
    :func:`auto_tie` / :func:`auto_tie_with_quality` are deprecated thin
    wrappers around it, kept for backward compatibility.

    Args:
        synthetic: Synthetic trace ``(M,)``.
        seismic_trace: Real seismic trace ``(N,)``.

    Returns:
        ``(shift_samples, correlation_coefficient)``. Positive shift means the
        synthetic should move later in time to line up with the field trace. Both
        values are ``(0, 0.0)`` when either input is empty or effectively constant.

    The coefficient is the Pearson correlation of the two traces over each
    lag's overlapping window (normalized cross-correlation), so a perfect
    match scores ~1.0 even when the traces have unequal lengths. The
    previous global normalization divided every lag by ``max(len)`` and a
    perfect 100-sample synthetic against a 1000-sample trace scored only
    ~0.1 (#117). Lags overlapping fewer than a quarter of the shorter
    trace (or fewer than 2 samples) are excluded: normalizing a handful of
    overlapping samples amplifies noise into spurious peaks at extreme
    lags.
    """
    synthetic = np.asarray(synthetic, dtype=np.float64)
    seismic_trace = np.asarray(seismic_trace, dtype=np.float64)
    n_s = len(synthetic)
    n_t = len(seismic_trace)
    if n_s == 0 or n_t == 0:
        return 0, 0.0

    s_std = np.std(synthetic)
    t_std = np.std(seismic_trace)
    if s_std < 1e-10 or t_std < 1e-10:
        return 0, 0.0

    # Lag convention: seismic sample i lines up with synthetic sample i-lag;
    # lag > 0 means the synthetic moves later in time.
    lags = np.arange(n_s + n_t - 1) - (n_s - 1)
    # Overlap window on the synthetic axis per lag.
    start_s = np.maximum(0, -lags)
    end_s = np.minimum(n_s, n_t - lags)
    start_t = start_s + lags
    end_t = end_s + lags
    n_overlap = end_s - start_s
    min_overlap = max(2, min(n_s, n_t) // 4)
    if not np.any(n_overlap >= min_overlap):
        return 0, 0.0

    # Sliding-window Pearson correlation via prefix sums.
    cs = np.concatenate(([0.0], np.cumsum(synthetic)))
    cs2 = np.concatenate(([0.0], np.cumsum(synthetic * synthetic)))
    ct = np.concatenate(([0.0], np.cumsum(seismic_trace)))
    ct2 = np.concatenate(([0.0], np.cumsum(seismic_trace * seismic_trace)))
    sum_s = cs[end_s] - cs[start_s]
    sum_s2 = cs2[end_s] - cs2[start_s]
    sum_t = ct[end_t] - ct[start_t]
    sum_t2 = ct2[end_t] - ct2[start_t]
    sum_st = np.correlate(seismic_trace, synthetic, mode="full")

    mean_s = sum_s / n_overlap
    mean_t = sum_t / n_overlap
    var_s = np.maximum(sum_s2 / n_overlap - mean_s * mean_s, 0.0)
    var_t = np.maximum(sum_t2 / n_overlap - mean_t * mean_t, 0.0)
    cov = sum_st / n_overlap - mean_s * mean_t
    denom = np.sqrt(var_s * var_t)
    corr = np.divide(cov, denom, out=np.zeros_like(cov), where=denom > 0.0)
    corr = np.where(n_overlap >= min_overlap, corr, -np.inf)

    best_idx = int(np.argmax(corr))
    shift = int(lags[best_idx])
    return shift, min(float(corr[best_idx]), 1.0)


def auto_tie(seismic: np.ndarray, synthetic: np.ndarray) -> int:
    """Estimate optimal bulk time shift via cross-correlation.

    .. deprecated::
        Use :func:`correlate_synthetic_to_trace` instead. This is a thin
        wrapper kept for backward compatibility, and now shares that
        function's semantics exactly: inputs are mean-removed and
        z-scored, no truncation to a common length, and the signed
        (not absolute) correlation peak is used.

    Args:
        seismic: Real seismic trace ``(N,)``.
        synthetic: Synthetic trace ``(M,)``.

    Returns:
        Integer shift in samples. Positive = synthetic should shift down
        (later in time). Negative = synthetic should shift up.
    """
    warnings.warn(
        "auto_tie is deprecated; use correlate_synthetic_to_trace instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    shift, _ = correlate_synthetic_to_trace(synthetic, seismic)
    return shift


def auto_tie_with_quality(
    seismic: np.ndarray,
    synthetic: np.ndarray,
) -> tuple[int, float]:
    """Estimate shift and return correlation coefficient.

    .. deprecated::
        Use :func:`correlate_synthetic_to_trace` instead. This is a thin
        wrapper kept for backward compatibility, with the same mean-removed,
        signed, non-truncating semantics; the normalized correlation
        coefficient is preserved.

    Returns:
        ``(shift_samples, correlation_coefficient)``. Positive shift means the
        synthetic should move later in time to line up with the field trace.
    """
    warnings.warn(
        "auto_tie_with_quality is deprecated; "
        "use correlate_synthetic_to_trace instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return correlate_synthetic_to_trace(synthetic, seismic)
