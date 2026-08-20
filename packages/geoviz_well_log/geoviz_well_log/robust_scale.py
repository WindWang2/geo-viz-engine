from __future__ import annotations

import math
import numpy as np


def _general_quantile_range(valid: np.ndarray) -> tuple[float, float]:
    """General quantile-based robust bounds (P2 ~ P98)."""
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

    # 2. Check standard domain presets for common well log curves. The
    #    presets assume one unit system (GR in API, density in g/cm3,
    #    neutron as a decimal fraction); data in other units (neutron in %,
    #    density in kg/m3) can push the quantiles past the clamped bound
    #    and produce an inverted vmin > vmax range (#113), so an inverted
    #    preset falls back to the general quantile path instead.
    preset: tuple[float, float] | None = None
    if any(k in c_upper for k in ("GR", "伽马")):
        p1 = float(np.percentile(valid, 1))
        p99 = float(np.percentile(valid, 99))
        preset = (max(0.0, min(p1, 0.0)), max(150.0, round(p99 + 10.0, 1)))
    elif any(k in c_upper for k in ("RHOB", "DEN", "密度")):
        p1 = float(np.percentile(valid, 1))
        p99 = float(np.percentile(valid, 99))
        preset = (max(1.5, round(p1 - 0.05, 2)), min(3.0, round(p99 + 0.05, 2)))
    elif any(k in c_upper for k in ("NPHI", "CNL", "中子")):
        p1 = float(np.percentile(valid, 1))
        p99 = float(np.percentile(valid, 99))
        preset = (max(-0.05, round(p1 - 0.02, 2)), min(1.0, round(p99 + 0.02, 2)))

    if preset is not None and preset[0] <= preset[1]:
        return preset

    # 3. General quantile-based robust bounds (P2 ~ P98)
    return _general_quantile_range(valid)
