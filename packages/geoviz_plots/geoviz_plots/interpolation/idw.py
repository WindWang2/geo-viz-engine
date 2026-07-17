"""Bounded-memory IDW interpolation with fault barrier support."""
from typing import Sequence, Tuple, Optional
import math
import numpy as np


def _orientation(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, tolerance: float) -> bool:
    return (
        min(a[0], b[0]) - tolerance <= p[0] <= max(a[0], b[0]) + tolerance
        and min(a[1], b[1]) - tolerance <= p[1] <= max(a[1], b[1]) + tolerance
    )


def segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float],
    *,
    tolerance: float = 1e-12,
) -> bool:
    """Return true for crossings, endpoint touches and collinear overlap."""
    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)
    if ((o1 > tolerance and o2 < -tolerance) or (o1 < -tolerance and o2 > tolerance)) and (
        (o3 > tolerance and o4 < -tolerance) or (o3 < -tolerance and o4 > tolerance)
    ):
        return True
    return (
        (abs(o1) <= tolerance and _on_segment(p1, p2, q1, tolerance))
        or (abs(o2) <= tolerance and _on_segment(p1, p2, q2, tolerance))
        or (abs(o3) <= tolerance and _on_segment(q1, q2, p1, tolerance))
        or (abs(o4) <= tolerance and _on_segment(q1, q2, p2, tolerance))
    )


def interpolate_idw(
    x,
    y,
    z,
    grid_x,
    grid_y,
    power: float = 2.0,
    epsilon: float = 1e-12,
    fault_polylines: Optional[Sequence[Sequence[Tuple[float, float]]]] = None,
    max_cells_per_chunk: int = 16_384,
    cancellation_token=None,
) -> np.ndarray:
    """Interpolate scattered 3D points (x, y, z) onto a grid (grid_x, grid_y) using vectorized IDW.

    Optionally respects fault polyline barriers that block interpolation between nodes.

    Args:
        x, y, z: 1D arrays of scattered point coordinates and values.
        grid_x, grid_y: 1D coordinate arrays defining the target interpolation grid.
        power: Power parameter for weighting (standard is 2.0).
        epsilon: Small buffer value to avoid division by zero.
        fault_polylines: Optional list of polylines (each is a list of (x, y) coordinates) acting as barriers.

    Returns:
        A 2D array of interpolated values with shape (len(grid_y), len(grid_x)).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)

    if not (len(x) == len(y) == len(z)):
        raise ValueError("x, y and z must have equal lengths")
    if not math.isfinite(power) or power <= 0:
        raise ValueError("power must be a finite positive value")
    if not math.isfinite(epsilon) or epsilon <= 0:
        raise ValueError("epsilon must be a finite positive value")
    chunk_size = int(max_cells_per_chunk)
    if chunk_size <= 0:
        raise ValueError("max_cells_per_chunk must be positive")

    # Non-finite control points cannot participate in spatial distances.
    mask = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x = x[mask]
    y = y[mask]
    z = z[mask]

    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)

    H, W = len(grid_y), len(grid_x)
    if len(x) == 0 or H == 0 or W == 0:
        return np.full((H, W), np.nan)

    fault_segments = []
    if fault_polylines:
        for polyline in fault_polylines:
            if len(polyline) >= 2:
                for i in range(len(polyline) - 1):
                    fault_segments.append((polyline[i], polyline[i + 1]))

    cell_x = np.tile(grid_x, H)
    cell_y = np.repeat(grid_y, W)
    output = np.full(cell_x.shape, np.nan, dtype=np.float64)
    for start in range(0, len(cell_x), chunk_size):
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        stop = min(start + chunk_size, len(cell_x))
        dx = cell_x[start:stop, None] - x[None, :]
        dy = cell_y[start:stop, None] - y[None, :]
        distances = np.maximum(np.hypot(dx, dy), epsilon)
        weights = 1.0 / (distances**power)
        if fault_segments:
            for local_cell, (node_x, node_y) in enumerate(
                zip(cell_x[start:stop], cell_y[start:stop])
            ):
                node = (float(node_x), float(node_y))
                for sample_index, (sample_x, sample_y) in enumerate(zip(x, y)):
                    control = (float(sample_x), float(sample_y))
                    if any(
                        segments_intersect(node, control, segment_start, segment_end)
                        for segment_start, segment_end in fault_segments
                    ):
                        weights[local_cell, sample_index] = 0.0
        totals = np.sum(weights, axis=1)
        populated = totals > epsilon
        values = np.full(stop - start, np.nan, dtype=np.float64)
        values[populated] = (
            np.sum(weights[populated] * z, axis=1) / totals[populated]
        )
        output[start:stop] = values
    return output.reshape(H, W)
