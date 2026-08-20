from __future__ import annotations

import math

import numpy as np
import pytest


def test_modified_z_scores_flags_deviation_when_mad_is_zero():
    from geoviz import modified_z_scores

    scores = modified_z_scores([0.0, 0.0, 0.0, 100.0])

    assert np.array_equal(scores[:3], np.zeros(3))
    assert math.isinf(float(scores[3]))
    assert float(scores[3]) > 0


def test_sand_ratio_core_enforces_closed_unit_interval():
    from geoviz import compute_sand_ratio

    assert compute_sand_ratio(0.0, 5.0) == (0.0, "ok")
    assert compute_sand_ratio(5.0, 5.0) == (1.0, "ok")
    assert compute_sand_ratio(5.1, 5.0) == (None, "invalid_ratio")
    assert compute_sand_ratio(1.0, 0.0) == (None, "invalid_ratio")


def test_directional_distance_rejects_non_positive_axes():
    from geoviz import directional_distance

    with pytest.raises(ValueError, match="positive"):
        directional_distance(np.array([1.0]), np.array([1.0]), a=0.0, b=1.0)


def test_chunked_directional_grid_matches_single_chunk():
    from geoviz import directional_trend_grid

    xs = np.array([0.0, 1.0, 0.0, 1.0])
    ys = np.array([0.0, 0.0, 1.0, 1.0])
    zs = np.array([1.0, 2.0, 3.0, 4.0])
    gx = np.linspace(0.0, 1.0, 11)
    gy = np.linspace(0.0, 1.0, 9)

    chunked = directional_trend_grid(
        xs, ys, zs, gx, gy, a=2.0, b=0.5, max_cells_per_chunk=7
    )
    single = directional_trend_grid(
        xs, ys, zs, gx, gy, a=2.0, b=0.5, max_cells_per_chunk=10_000
    )

    assert np.allclose(chunked, single)


def test_directional_grid_checks_cancellation_between_chunks():
    from geoviz import JobCancelled, directional_trend_grid

    class CancelOnSecondCheckpoint:
        calls = 0

        def raise_if_cancelled(self):
            self.calls += 1
            if self.calls == 2:
                raise JobCancelled("cancelled between chunks")

    token = CancelOnSecondCheckpoint()
    with pytest.raises(JobCancelled):
        directional_trend_grid(
            np.array([0.0, 1.0]),
            np.array([0.0, 1.0]),
            np.array([1.0, 2.0]),
            np.linspace(0.0, 1.0, 6),
            np.linspace(0.0, 1.0, 4),
            max_cells_per_chunk=2,
            cancellation_token=token,
        )


def _ramp_samples(seed: int = 5, n: int = 20, span: float = 5.0):
    rng = np.random.default_rng(seed)
    x = rng.uniform(0.0, span, n)
    y = rng.uniform(0.0, span, n)
    z = x + 0.5 * y
    return x, y, z


def test_directional_trend_grid_preserves_ramp_variance_across_coordinate_scales():
    """#112: kernel axes are normalized by the sample span, so the trend
    retains the input variation at any coordinate scale (degree-like small
    spans and metre-like UTM spans) instead of collapsing to a flat mean
    field (7.2% variance retention) or the nearest-neighbour fallback."""
    from geoviz import directional_trend_grid

    for scale in (1.0, 1e-3, 1e3):
        x, y, z = _ramp_samples(span=5.0)
        gx = np.linspace(0.0, 5.0, 30) * scale
        gy = np.linspace(0.0, 5.0, 30) * scale
        grid = directional_trend_grid(x * scale, y * scale, z, gx, gy)
        assert np.all(np.isfinite(grid))
        ratio = float(np.nanstd(grid)) / float(np.std(z))
        assert ratio >= 0.5, f"scale={scale}: std ratio {ratio:.3f} < 0.5"


def test_directional_trend_grid_utm_scale_is_not_nearest_neighbour():
    """#112: metric-scale (UTM) input with default a/b must not degenerate
    into the anisotropic nearest-neighbour field (exact match was observed
    before the fix)."""
    from geoviz import directional_trend_grid, rotate_to_uv

    x, y, _ = _ramp_samples()
    x = x * 1000.0
    y = y * 1000.0
    z = 0.001 * x + 0.0005 * y
    gx = np.linspace(0.0, 5000.0, 30)
    gy = np.linspace(0.0, 5000.0, 30)

    grid = directional_trend_grid(x, y, z, gx, gy)

    xx, yy = np.meshgrid(gx, gy)
    u, v = rotate_to_uv(xx - x[:, None, None], yy - y[:, None, None], azimuth_deg=0.0)
    dist = np.hypot(u / 1.0, v / 0.4)
    nearest = z[np.argmin(dist, axis=0)]
    assert not np.allclose(grid, nearest)


def test_directional_trend_grid_is_scale_and_shift_invariant():
    """#112: normalizing the axes by the sample span makes the trend field
    invariant under affine rescaling of the input coordinates."""
    from geoviz import directional_trend_grid

    x, y, z = _ramp_samples(span=5.0)
    gx = np.linspace(0.0, 5.0, 20)
    gy = np.linspace(0.0, 5.0, 20)

    base = directional_trend_grid(x, y, z, gx, gy, azimuth_deg=30.0)
    transformed = directional_trend_grid(
        x * 0.001 + 7.0, y * 0.001 - 3.0, z,
        gx * 0.001 + 7.0, gy * 0.001 - 3.0,
        azimuth_deg=30.0,
    )
    assert np.allclose(base, transformed)


def test_directional_trend_grid_degenerate_sample_sets():
    """#112: empty / single / coincident samples degrade gracefully instead
    of dividing by a zero span."""
    from geoviz import directional_trend_grid

    gx = np.linspace(0.0, 1.0, 4)
    gy = np.linspace(0.0, 1.0, 4)

    empty = directional_trend_grid(np.array([]), np.array([]), np.array([]), gx, gy)
    assert empty.shape == (4, 4)
    assert np.all(np.isnan(empty))

    single = directional_trend_grid(
        np.array([0.4]), np.array([0.6]), np.array([12.5]), gx, gy
    )
    assert np.all(np.isfinite(single))
    assert np.allclose(single, 12.5)

    coincident = directional_trend_grid(
        np.array([0.4, 0.4]), np.array([0.6, 0.6]), np.array([2.0, 6.0]), gx, gy
    )
    assert np.allclose(coincident, 4.0)  # unweighted mean of coincident samples


def test_directional_factor_grid_retains_default_sample_variance():
    """#112: the 制备页 ``方向趋势`` default synthetic sample path (degree
    coordinates, default a=1.0/b=0.4) must retain at least half of the input
    variance (measured 7.2% before the fix)."""
    from geoviz_plots.factor.interpolation import interpolate_factor_grid, synthetic_sample_points

    pts = synthetic_sample_points(seed=42, factor_type="地层厚度", count=8)
    zs = np.asarray([p["value"] for p in pts])
    out = interpolate_factor_grid(pts, method="方向趋势", grid_n=30)
    gz = np.asarray(
        [[np.nan if v is None else v for v in row] for row in out["grid_z"]]
    )
    assert float(np.nanstd(gz)) / float(np.std(zs)) >= 0.5
