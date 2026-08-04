"""Directional anisotropy helpers for the trend-surface backend (ISS-ALG-02).

Promoted verbatim from ``paleo_workbench/workflow/directional_trend.py``
(Phase-2 promote-down). Operates on plain dicts / numpy arrays; no
``paleo_workbench.project.models`` dependency.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

# Default anisotropy: elongate along strike (a > b).
DEFAULT_SEMI_MAJOR = 1.0
DEFAULT_SEMI_MINOR = 0.4


def resolve_anisotropy_params(
    direction_params: Sequence[dict[str, Any]] | None,
) -> tuple[float, float, float]:
    """Pick azimuth / a / b from the first active direction-line param dict."""
    if not direction_params:
        return 0.0, DEFAULT_SEMI_MAJOR, DEFAULT_SEMI_MINOR
    p0 = direction_params[0]
    az = float(p0.get("azimuth_deg") if p0.get("azimuth_deg") is not None else 0.0)
    a = float(p0.get("semi_major") if p0.get("semi_major") is not None else DEFAULT_SEMI_MAJOR)
    b = float(p0.get("semi_minor") if p0.get("semi_minor") is not None else DEFAULT_SEMI_MINOR)
    if a <= 0:
        a = DEFAULT_SEMI_MAJOR
    if b <= 0:
        b = DEFAULT_SEMI_MINOR
    return az, a, b


def extract_xy_z_weights(
    sample_points: list[dict[str, Any]] | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (x, y, z, q, b_i) arrays from sample_points / WellTable export dicts.

    Skips QC-flagged points (``qc_flag`` not in {"ok", ""}) unless explicitly
    kept. Quality weights ``q`` and bias terms ``b_i`` default to 1.0 and are
    floored at 0.
    """
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    qs: list[float] = []
    bs: list[float] = []
    for pt in sample_points or []:
        if not isinstance(pt, dict):
            continue
        try:
            if "x" in pt and "y" in pt:
                x = float(pt["x"])
                y = float(pt["y"])
            elif "lng" in pt and "lat" in pt:
                x = float(pt["lng"])
                y = float(pt["lat"])
            else:
                continue
            z = float(pt.get("value", pt.get("z", pt.get("v"))))
        except (TypeError, ValueError):
            continue
        if not (math.isfinite(x) and math.isfinite(y) and math.isfinite(z)):
            continue
        # Skip QC-flagged points unless explicitly kept.
        flag = str(pt.get("qc_flag") or "ok")
        if flag not in {"ok", ""}:
            continue
        try:
            q = float(pt.get("q", 1.0))
        except (TypeError, ValueError):
            q = 1.0
        try:
            bi = float(pt.get("b_i", 1.0))
        except (TypeError, ValueError):
            bi = 1.0
        xs.append(x)
        ys.append(y)
        zs.append(z)
        qs.append(max(0.0, q))
        bs.append(max(0.0, bi))
    return (
        np.asarray(xs, dtype=np.float64),
        np.asarray(ys, dtype=np.float64),
        np.asarray(zs, dtype=np.float64),
        np.asarray(qs, dtype=np.float64),
        np.asarray(bs, dtype=np.float64),
    )
