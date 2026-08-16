"""Tests for IDW interpolation with fault polyline barriers."""
import numpy as np
import pytest
from geoviz_plots.interpolation.idw import interpolate_idw, segments_intersect

def test_segments_intersect():
    # Cross intersection
    p1, p2 = (0.0, 0.0), (2.0, 2.0)
    q1, q2 = (0.0, 2.0), (2.0, 0.0)
    assert segments_intersect(p1, p2, q1, q2) is True

    # Parallel non-intersecting lines
    p1, p2 = (0.0, 0.0), (2.0, 0.0)
    q1, q2 = (0.0, 1.0), (2.0, 1.0)
    assert segments_intersect(p1, p2, q1, q2) is False


def test_segments_intersect_counts_endpoint_touch_and_collinear_overlap():
    assert segments_intersect((0, 0), (2, 0), (2, 0), (2, 2))
    assert segments_intersect((0, 0), (3, 0), (1, 0), (2, 0))


def test_idw_filters_infinite_samples_and_chunks_equivalently():
    x = np.array([0.0, 1.0, np.inf])
    y = np.array([0.0, 1.0, 0.5])
    z = np.array([0.0, 10.0, 999.0])
    gx = np.linspace(0.0, 1.0, 9)
    gy = np.linspace(0.0, 1.0, 7)

    chunked = interpolate_idw(x, y, z, gx, gy, max_cells_per_chunk=5)
    single = interpolate_idw(x, y, z, gx, gy, max_cells_per_chunk=10_000)

    assert np.all(np.isfinite(chunked))
    assert np.allclose(chunked, single)


def test_idw_checks_cancellation_between_chunks():
    from geoviz import JobCancelled

    class CancelOnSecondCheckpoint:
        calls = 0

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls == 2:
                raise JobCancelled("cancelled between chunks")

    with pytest.raises(JobCancelled):
        interpolate_idw(
            np.array([0.0, 1.0]),
            np.array([0.0, 1.0]),
            np.array([1.0, 2.0]),
            np.linspace(0.0, 1.0, 6),
            np.linspace(0.0, 1.0, 4),
            max_cells_per_chunk=2,
            cancellation_token=CancelOnSecondCheckpoint(),
        )

def test_idw_without_faults():
    x = np.array([0.0, 10.0, 0.0, 10.0])
    y = np.array([0.0, 0.0, 10.0, 10.0])
    z = np.array([10.0, 20.0, 30.0, 40.0])

    grid_x = np.linspace(0, 10, 5)
    grid_y = np.linspace(0, 10, 5)

    grid_z = interpolate_idw(x, y, z, grid_x, grid_y)
    assert grid_z.shape == (5, 5)
    assert not np.isnan(grid_z).any()
    assert pytest.approx(grid_z[0, 0], abs=1e-3) == 10.0

def test_idw_with_fault_barrier():
    # Points on left side (z=10) and right side (z=100)
    x = np.array([1.0, 1.0, 9.0, 9.0])
    y = np.array([1.0, 9.0, 1.0, 9.0])
    z = np.array([10.0, 10.0, 100.0, 100.0])

    grid_x = np.linspace(0, 10, 11)
    grid_y = np.linspace(0, 10, 11)

    # Vertical fault barrier along x=5.0 separating left and right
    fault_polylines = [[(5.0, -1.0), (5.0, 11.0)]]

    grid_z = interpolate_idw(x, y, z, grid_x, grid_y, fault_polylines=fault_polylines)
    
    # Left side (x < 5) should only be influenced by left points (z ~ 10)
    assert grid_z[5, 2] < 20.0
    # Right side (x > 5) should only be influenced by right points (z ~ 100)
    assert grid_z[5, 8] > 80.0


def test_vectorized_barrier_matches_scalar_reference_on_large_inputs():
    """#507 lock: inputs above _FAULT_REFERENCE_LIMIT must take the
    broadcast path and still match the scalar segments_intersect reference
    exactly (crossings, endpoint touches, collinear overlap)."""
    from geoviz_plots.interpolation.idw import (
        _FAULT_REFERENCE_LIMIT,
        _apply_fault_barriers,
    )

    r = np.random.default_rng(99)
    C, S, F = 128, 64, 9  # 73728 > 65536 -> vectorized path
    assert C * S * F > _FAULT_REFERENCE_LIMIT
    nx = r.uniform(-5, 5, C)
    ny = r.uniform(-5, 5, C)
    sx = r.uniform(-5, 5, S)
    sy = r.uniform(-5, 5, S)
    segs = [tuple(map(tuple, r.uniform(-5, 5, (2, 2)))) for _ in range(F)]

    w = np.ones((C, S))
    _apply_fault_barriers(w, nx, ny, sx, sy, segs)

    mismatch = 0
    for i in range(C):
        for j in range(S):
            ref = any(
                segments_intersect((nx[i], ny[i]), (sx[j], sy[j]), s[0], s[1])
                for s in segs
            )
            if bool(w[i, j] == 0.0) != ref:
                mismatch += 1
    assert mismatch == 0


def test_barrier_interpolation_audit_scale_completes_fast():
    """#507 lock: the audit's trigger scale (50x50 grid, 100 wells, 20 fault
    segments — minutes with the old triple Python loop) must stay in the
    sub-second range on the vectorized path."""
    import time

    r = np.random.default_rng(7)
    x = r.uniform(0, 100, 100)
    y = r.uniform(0, 100, 100)
    z = r.uniform(0, 50, 100)
    gx = np.linspace(0, 100, 50)
    gy = np.linspace(0, 100, 50)
    faults = [[tuple(p) for p in r.uniform(0, 100, (2, 2))] for _ in range(20)]

    t0 = time.perf_counter()
    res = interpolate_idw(x, y, z, gx, gy, fault_polylines=faults)
    dt = time.perf_counter() - t0

    assert res.shape == (50, 50)
    # Generous CI margin (audit measured the old loop at 30-60 s; the
    # vectorized path measures ~0.3 s locally).
    assert dt < 10.0, f"barrier IDW regressed to {dt:.1f}s at audit scale"
