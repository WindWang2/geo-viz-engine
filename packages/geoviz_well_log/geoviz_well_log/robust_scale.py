from __future__ import annotations

import math
import numpy as np


def compute_robust_display_range(
    val_arr: np.ndarray | list[float],
    curve_name: str = "",
    null_value: float | None = None,
) -> tuple[float, float]:
    """Calculate a robust, outlier-free display (vmin, vmax) range for a well log curve."""
    if val_arr is None:
        return (0.0, 100.0)

    arr = np.asarray(val_arr, dtype=np.float64)
    if arr.size == 0:
        return (0.0, 100.0)

    # 1. Mask out non-finite (NaN, Inf) samples only. Valid negative values
    #    (e.g. SP curves around -100..50) must be kept — no numeric-range
    #    truncation.
    mask = np.isfinite(arr)
    if null_value is not None and np.isfinite(null_value):
        mask = mask & ~np.isclose(arr, null_value, atol=1e-3)

    valid = arr[mask]
    if valid.size == 0:
        return (0.0, 100.0)

    c_upper = curve_name.upper().strip()

    # 2. Check standard domain presets for common well log curves
    if any(k in c_upper for k in ("GR", "伽马")):
        p1 = float(np.percentile(valid, 1))
        p99 = float(np.percentile(valid, 99))
        vmin = max(0.0, min(p1, 0.0))
        vmax = max(150.0, round(p99 + 10.0, 1))
        return (vmin, vmax)

    if any(k in c_upper for k in ("RHOB", "DEN", "密度")):
        p1 = float(np.percentile(valid, 1))
        p99 = float(np.percentile(valid, 99))
        vmin = max(1.5, round(p1 - 0.05, 2))
        vmax = min(3.0, round(p99 + 0.05, 2))
        return (vmin, vmax)

    if any(k in c_upper for k in ("NPHI", "CNL", "中子")):
        p1 = float(np.percentile(valid, 1))
        p99 = float(np.percentile(valid, 99))
        vmin = max(-0.05, round(p1 - 0.02, 2))
        vmax = min(1.0, round(p99 + 0.02, 2))
        return (vmin, vmax)

    # 3. General quantile-based robust bounds (P2 ~ P98)
    p2 = float(np.percentile(valid, 2))
    p98 = float(np.percentile(valid, 98))

    if math.isclose(p2, p98) or p2 >= p98:
        vmin = float(np.min(valid))
        vmax = float(np.max(valid))
        if math.isclose(vmin, vmax):
            return (vmin, vmin + 10.0)
        p2, p98 = vmin, vmax

    span = p98 - p2
    vmin = p2 - 0.05 * span
    vmax = p98 + 0.05 * span

    if span > 10:
        vmin = math.floor(vmin * 10) / 10.0
        vmax = math.ceil(vmax * 10) / 10.0
    else:
        vmin = round(vmin, 2)
        vmax = round(vmax, 2)

    return (vmin, vmax)
