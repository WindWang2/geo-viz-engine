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
