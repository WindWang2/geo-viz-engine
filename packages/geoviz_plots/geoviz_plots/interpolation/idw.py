"""NumPy vectorized Inverse Distance Weighting (IDW) interpolation with fault barrier support."""
from typing import List, Sequence, Tuple, Optional
import numpy as np


def _ccw(A: Tuple[float, float], B: Tuple[float, float], C: Tuple[float, float]) -> bool:
    """Helper to check if 3 points A, B, C are in counter-clockwise order."""
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float],
) -> bool:
    """Determine if line segment p1-p2 intersects with line segment q1-q2."""
    return (_ccw(p1, q1, q2) != _ccw(p2, q1, q2)) and (_ccw(p1, p2, q1) != _ccw(p1, p2, q2))


def interpolate_idw(
    x,
    y,
    z,
    grid_x,
    grid_y,
    power: float = 2.0,
    epsilon: float = 1e-12,
    fault_polylines: Optional[Sequence[Sequence[Tuple[float, float]]]] = None,
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

    # Filter NaNs
    mask = ~np.isnan(x) & ~np.isnan(y) & ~np.isnan(z)
    x = x[mask]
    y = y[mask]
    z = z[mask]

    grid_x = np.asarray(grid_x, dtype=np.float64)
    grid_y = np.asarray(grid_y, dtype=np.float64)

    H, W = len(grid_y), len(grid_x)
    if len(x) == 0 or H == 0 or W == 0:
        return np.full((H, W), np.nan)

    # Create meshgrid
    X, Y = np.meshgrid(grid_x, grid_y)  # shape (H, W)

    # Compute distances to all points: expand X, Y to (H, W, N) and broadcast
    dx = X[:, :, np.newaxis] - x  # shape (H, W, N)
    dy = Y[:, :, np.newaxis] - y  # shape (H, W, N)
    dist = np.hypot(dx, dy)  # shape (H, W, N)

    # Bound distance
    dist = np.maximum(dist, epsilon)

    # Calculate base weights
    weights = 1.0 / (dist**power)

    # Apply fault barrier masking if provided
    if fault_polylines:
        # Extract all fault segments
        fault_segments = []
        for polyline in fault_polylines:
            if len(polyline) >= 2:
                for i in range(len(polyline) - 1):
                    fault_segments.append((polyline[i], polyline[i + 1]))

        if fault_segments:
            N = len(x)
            for i in range(H):
                for j in range(W):
                    node_pt = (X[i, j], Y[i, j])
                    for k in range(N):
                        ctrl_pt = (x[k], y[k])
                        # Check against all fault segments
                        for seg_start, seg_end in fault_segments:
                            if segments_intersect(node_pt, ctrl_pt, seg_start, seg_end):
                                weights[i, j, k] = 0.0
                                break

    sum_weights = np.sum(weights, axis=-1)
    # Mask unpopulated cells where all control points were blocked by faults
    unpopulated_mask = sum_weights <= epsilon

    sum_weights = np.maximum(sum_weights, epsilon)
    grid_z = np.sum(weights * z, axis=-1) / sum_weights
    grid_z[unpopulated_mask] = np.nan

    return grid_z
