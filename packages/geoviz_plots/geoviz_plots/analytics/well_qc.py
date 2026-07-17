"""Pure mathematical quality controls for well-table values."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np

_MAD_Z_SCALE = 0.6745
_EPS = 1e-15


def median_absolute_deviation(values: Iterable[float]) -> float:
    """Return ``median(abs(x - median(x)))`` over finite values."""
    arr = np.asarray(list(values), dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return float("nan")
    median = float(np.median(arr))
    return float(np.median(np.abs(arr - median)))


def modified_z_scores(values: Iterable[float]) -> np.ndarray:
    """Return modified z-scores while retaining information at zero MAD.

    When MAD is zero, values equal to the median have score zero and finite
    deviations have signed infinite scores.  Returning all zero would silently
    classify an isolated extreme value as normal.
    """
    arr = np.asarray(list(values), dtype=np.float64)
    out = np.full(arr.shape, np.nan, dtype=np.float64)
    finite = np.isfinite(arr)
    if not np.any(finite):
        return out
    samples = arr[finite]
    median = float(np.median(samples))
    deviation = samples - median
    mad = float(np.median(np.abs(deviation)))
    if mad < _EPS:
        scores = np.zeros(samples.shape, dtype=np.float64)
        nonzero = np.abs(deviation) >= _EPS
        scores[nonzero] = np.copysign(np.inf, deviation[nonzero])
        out[finite] = scores
        return out
    out[finite] = _MAD_Z_SCALE * deviation / mad
    return out


def compute_sand_ratio(
    sand_thickness: float | None,
    total_thickness: float | None,
) -> tuple[float | None, str]:
    """Validate ``0 <= H_s <= H_t`` and return ``(H_s / H_t, flag)``."""
    if sand_thickness is None or total_thickness is None:
        return None, "ok"
    try:
        hs = float(sand_thickness)
        ht = float(total_thickness)
    except (TypeError, ValueError):
        return None, "invalid_ratio"
    if not (math.isfinite(hs) and math.isfinite(ht)):
        return None, "invalid_ratio"
    if ht <= 0.0 or hs < 0.0 or hs > ht:
        return None, "invalid_ratio"
    return hs / ht, "ok"
