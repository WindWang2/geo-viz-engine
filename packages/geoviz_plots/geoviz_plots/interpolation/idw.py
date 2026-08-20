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


def _contact_strictly_between(a, b, p) -> bool:
    """True when collinear point ``p`` lies strictly inside segment ``a``-``b``.

    Uses the projection parameter along the segment so degenerate
    (axis-aligned) configurations stay correct: the check answers whether
    the contact point is the ``a``/``b`` endpoint itself.
    """
    abx = b[0] - a[0]
    aby = b[1] - a[1]
    length_sq = abx * abx + aby * aby
    if length_sq <= 0.0:
        return False
    t = ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / length_sq
    return 0.0 < t < 1.0


def segments_intersect(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    q1: Tuple[float, float],
    q2: Tuple[float, float],
    *,
    tolerance: float = 1e-12,
    strict_interior_touch: bool = False,
) -> bool:
    """Return true for crossings, endpoint touches and collinear overlap.

    With ``strict_interior_touch=True`` only contacts located strictly
    between ``p1`` and ``p2`` count: a touch whose contact point is a
    ``p1``/``p2`` endpoint itself — including ``p1`` or ``p2`` lying on the
    ``q`` segment — no longer intersects. The fault-barrier kernel uses this
    so a grid node that happens to sit exactly on a fault line is not
    severed from every sample (a vertical fault at an integer grid x used
    to zero the whole column into a NaN strip, #118).
    """
    o1 = _orientation(p1, p2, q1)
    o2 = _orientation(p1, p2, q2)
    o3 = _orientation(q1, q2, p1)
    o4 = _orientation(q1, q2, p2)
    if ((o1 > tolerance and o2 < -tolerance) or (o1 < -tolerance and o2 > tolerance)) and (
        (o3 > tolerance and o4 < -tolerance) or (o3 < -tolerance and o4 > tolerance)
    ):
        return True
    if strict_interior_touch:
        return (
            (abs(o1) <= tolerance and _contact_strictly_between(p1, p2, q1))
            or (abs(o2) <= tolerance and _contact_strictly_between(p1, p2, q2))
        )
    return (
        (abs(o1) <= tolerance and _on_segment(p1, p2, q1, tolerance))
        or (abs(o2) <= tolerance and _on_segment(p1, p2, q2, tolerance))
        or (abs(o3) <= tolerance and _on_segment(q1, q2, p1, tolerance))
        or (abs(o4) <= tolerance and _on_segment(q1, q2, p2, tolerance))
    )


# Number of (cell, sample, fault) intersection tests below which the scalar
# reference loop is cheaper than building broadcast arrays.
_FAULT_REFERENCE_LIMIT = 65_536
# Cap on temporary bytes for the broadcast orientation arrays (o1..o4).
_FAULT_BATCH_BUDGET = 128 * 1024 * 1024


def _apply_fault_barriers(
    weights: np.ndarray,
    node_x: np.ndarray,
    node_y: np.ndarray,
    sample_x: np.ndarray,
    sample_y: np.ndarray,
    fault_segments: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]],
) -> None:
    """Zero out weights for (node, sample) pairs blocked by fault segments, in place.

    A pair is blocked when its straight segment intersects any fault segment,
    using the same test as ``segments_intersect(..., strict_interior_touch=True)``
    (proper crossings, collinear overlap, and fault-endpoint contacts located
    STRICTLY between the node and the sample). Contacts whose contact point
    is the grid node or the sample itself do NOT block: a node sitting
    exactly on a fault line must stay reachable from both walls instead of
    being masked into a NaN strip (#118). Small inputs reuse the scalar
    reference loop; larger inputs broadcast the orientation tests over
    (cell, sample, fault) arrays, batching fault segments to bound memory.
    """
    tolerance = 1e-12
    num_cells = len(node_x)
    num_samples = len(sample_x)
    num_faults = len(fault_segments)
    if num_cells * num_samples * num_faults <= _FAULT_REFERENCE_LIMIT:
        for local_cell, (nx, ny) in enumerate(zip(node_x, node_y)):
            node = (float(nx), float(ny))
            for sample_index, (sx_, sy_) in enumerate(zip(sample_x, sample_y)):
                control = (float(sx_), float(sy_))
                if any(
                    segments_intersect(
                        node, control, segment_start, segment_end,
                        strict_interior_touch=True,
                    )
                    for segment_start, segment_end in fault_segments
                ):
                    weights[local_cell, sample_index] = 0.0
        return

    # Orientation formulas below mirror segments_intersect operation by
    # operation, so broadcast results are bit-for-bit identical.
    cx = np.asarray(node_x, dtype=np.float64)[:, None]
    cy = np.asarray(node_y, dtype=np.float64)[:, None]
    sx = np.asarray(sample_x, dtype=np.float64)
    sy = np.asarray(sample_y, dtype=np.float64)
    fx1 = np.array([seg[0][0] for seg in fault_segments], dtype=np.float64)
    fy1 = np.array([seg[0][1] for seg in fault_segments], dtype=np.float64)
    fx2 = np.array([seg[1][0] for seg in fault_segments], dtype=np.float64)
    fy2 = np.array([seg[1][1] for seg in fault_segments], dtype=np.float64)

    # (cell, sample) segment deltas, shared by all batches.
    dx = sx - cx  # control - node
    dy = sy - cy
    seg_len_sq = dx * dx + dy * dy
    reachable_denom = np.where(seg_len_sq > 0.0, seg_len_sq, 1.0)

    blocked = np.zeros((num_cells, num_samples), dtype=bool)
    # Each broadcast batch holds 4 float64 orientation arrays per element.
    fault_batch = max(
        1, min(num_faults, _FAULT_BATCH_BUDGET // (num_cells * num_samples * 32))
    )
    for f0 in range(0, num_faults, fault_batch):
        f1 = min(f0 + fault_batch, num_faults)
        q1x = fx1[f0:f1][None, None, :]
        q1y = fy1[f0:f1][None, None, :]
        q2x = fx2[f0:f1][None, None, :]
        q2y = fy2[f0:f1][None, None, :]

        # o1/o2 = orient(node, control, fault_start/end): proper crossing and
        # fault-endpoint contact tests on the (node, control) side.
        o1 = dx[..., None] * (q1y - cy[..., None]) - dy[..., None] * (
            q1x - cx[..., None]
        )
        o2 = dx[..., None] * (q2y - cy[..., None]) - dy[..., None] * (
            q2x - cx[..., None]
        )
        node_cross = ((o1 > tolerance) & (o2 < -tolerance)) | (
            (o1 < -tolerance) & (o2 > tolerance)
        )
        # o3/o4 = orient(fault_start, fault_end, node/control): proper
        # crossing test on the fault side.
        dqx = q2x - q1x
        dqy = q2y - q1y
        o3 = dqx * (cy[..., None] - q1y) - dqy * (cx[..., None] - q1x)
        o4 = dqx * (sy[None, :, None] - q1y) - dqy * (sx[None, :, None] - q1x)
        fault_cross = ((o3 > tolerance) & (o4 < -tolerance)) | (
            (o3 < -tolerance) & (o4 > tolerance)
        )
        # Contact test (#118): a fault endpoint blocks only when it lies
        # STRICTLY between the node and the sample (projection parameter in
        # the open interval (0, 1)); contacts AT the node or the sample —
        # including a node sitting exactly on the fault line — do not block.
        # Unreachable pairs (node == control) cannot have a strictly-inside
        # contact; their forced t = -1 keeps them unblocked here.
        t1 = (
            (q1x - cx[..., None]) * dx[..., None]
            + (q1y - cy[..., None]) * dy[..., None]
        ) / reachable_denom[..., None]
        t2 = (
            (q2x - cx[..., None]) * dx[..., None]
            + (q2y - cy[..., None]) * dy[..., None]
        ) / reachable_denom[..., None]
        t1 = np.where((seg_len_sq > 0.0)[..., None], t1, -1.0)
        t2 = np.where((seg_len_sq > 0.0)[..., None], t2, -1.0)
        touch_strict = (
            ((np.abs(o1) <= tolerance) & (t1 > 0.0) & (t1 < 1.0))
            | ((np.abs(o2) <= tolerance) & (t2 > 0.0) & (t2 < 1.0))
        )

        intersects = (node_cross & fault_cross) | touch_strict
        blocked |= intersects.any(axis=-1)
    weights[blocked] = 0.0


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
            _apply_fault_barriers(
                weights,
                cell_x[start:stop],
                cell_y[start:stop],
                x,
                y,
                fault_segments,
            )
        totals = np.sum(weights, axis=1)
        # Depopulation test: totals are a SUM OF WEIGHTS, not a distance. The
        # `epsilon` above is the distance floor applied before exponentiation;
        # comparing the weight sum against it wrongly depopulates distant cells
        # at high power, where a perfectly well-defined positive total falls
        # below 1e-12 (UTM coordinates at power>=4: a ~1 km nearest-well
        # distance yields weights ~1e-12 each). IDW is sum(w*z)/sum(w) and is
        # defined for ANY positive weight sum. The workbench batch path was
        # fixed by #844; this engine kernel was missed (#877).
        populated = totals > 0.0
        values = np.full(stop - start, np.nan, dtype=np.float64)
        values[populated] = (
            np.sum(weights[populated] * z, axis=1) / totals[populated]
        )
        output[start:stop] = values
    return output.reshape(H, W)
