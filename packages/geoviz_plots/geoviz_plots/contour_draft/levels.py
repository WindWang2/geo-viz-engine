"""Level suggestion for contour drafts (pure numpy)."""

from __future__ import annotations

import math

import numpy as np

GENERATOR_VERSION = "contour-draft-v1"
DEFAULT_N_LEVELS = 8


def suggest_levels(
    grid_z: np.ndarray,
    *,
    n_levels: int = DEFAULT_N_LEVELS,
    vmin: float | None = None,
    vmax: float | None = None,
) -> list[float]:
    """Evenly spaced interior levels between min/max of finite cells.

    Endpoints (exact min/max) are excluded so isolines don't collapse onto the
    grid boundary. Returns ``[]`` if the grid has no finite values or a
    degenerate (non-finite / equal) range; returns ``[lo]`` for a flat grid.
    """
    finite = grid_z[np.isfinite(grid_z)]
    if finite.size == 0:
        return []
    lo = float(np.min(finite) if vmin is None else vmin)
    hi = float(np.max(finite) if vmax is None else vmax)
    if not math.isfinite(lo) or not math.isfinite(hi):
        return []
    if math.isclose(lo, hi):
        return [lo]
    n = max(2, int(n_levels))
    # Exclude exact min/max endpoints for cleaner isolines.
    levels = np.linspace(lo, hi, n + 2)[1:-1]
    return [round(float(v), 6) for v in levels]
