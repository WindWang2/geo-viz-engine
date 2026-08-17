"""Tests for DTWEngine."""
import numpy as np
import pytest

from geoviz_cross_well.dtw_engine import DTWEngine, DTWResult


def test_identical_curves_zero_cost():
    engine = DTWEngine()
    curve = np.sin(np.linspace(0, 4 * np.pi, 100))
    depths = np.linspace(0, 1000, 100)

    result = engine.correlate(curve, depths, curve.copy(), depths)
    assert result.cost < 0.01
    assert result.confidence > 0.99


def test_shifted_curve_correct_offset():
    engine = DTWEngine()
    n = 100
    rng = np.random.default_rng(0)
    ref_curve = rng.standard_normal(n).cumsum()
    ref_depths = np.linspace(0, 1000, n)

    # Target curve is shifted by 10 samples
    shift = 10
    target_curve = np.roll(ref_curve, shift)
    target_depths = np.linspace(0, 1000, n)
    depth_per_sample = (ref_depths[-1] - ref_depths[0]) / (n - 1)
    expected_offset = shift * depth_per_sample
    ref_depth = float(ref_depths[n // 2])

    result = engine.correlate(ref_curve, ref_depths, target_curve, target_depths)
    err = abs((result.suggested_depth - ref_depth) - expected_offset)
    assert err < depth_per_sample * 3, (
        f"suggested={result.suggested_depth} ref={ref_depth} "
        f"expected_offset={expected_offset} err={err}"
    )
    assert result.cost < 1.0


def test_band_radius_constraint():
    engine = DTWEngine()
    n = 50
    ref = np.random.randn(n)
    tgt = np.random.randn(n)
    ref_d = np.linspace(0, 500, n)
    tgt_d = np.linspace(0, 500, n)

    # With very tight band, should still complete without error
    result = engine.correlate(ref, ref_d, tgt, tgt_d, band_radius=5)
    assert isinstance(result, DTWResult)
    assert 0.0 <= result.cost <= 1.0


def test_short_curves():
    engine = DTWEngine()
    ref = np.array([1.0])
    tgt = np.array([2.0])
    ref_d = np.array([100.0])
    tgt_d = np.array([200.0])

    result = engine.correlate(ref, ref_d, tgt, tgt_d)
    assert result.cost == 1.0
    assert result.confidence == 0.0


def test_empty_curves():
    engine = DTWEngine()
    ref = np.array([])
    tgt = np.array([])
    result = engine.correlate(ref, np.array([]), tgt, np.array([]))
    assert result.confidence == 0.0


def test_ref_depth_propagates_correctly():
    """11.6-F regression: suggested_depth must follow ref_depth, not n//2."""
    engine = DTWEngine()
    n = 200
    rng = np.random.default_rng(0)
    ref_curve = rng.standard_normal(n).cumsum()
    ref_depths = np.linspace(1000.0, 3000.0, n)

    shift = 25
    target_curve = np.roll(ref_curve, shift)
    target_depths = ref_depths.copy()
    depth_per_sample = (ref_depths[-1] - ref_depths[0]) / (n - 1)
    expected_offset = shift * depth_per_sample

    # Three different ref_depths should yield three different suggested depths
    for ref_depth in (1300.0, 2000.0, 2700.0):
        result = engine.correlate(
            ref_curve, ref_depths, target_curve, target_depths,
            ref_depth=ref_depth,
        )
        # DTW on shifted curves should suggest a depth offset by ~shift samples
        err = abs((result.suggested_depth - ref_depth) - expected_offset)
        assert err < depth_per_sample * 3, (
            f"ref_depth={ref_depth} suggested={result.suggested_depth} "
            f"expected_offset={expected_offset} err={err}"
        )


def test_ref_depth_default_is_midpoint():
    """Backward compat: omitting ref_depth keeps legacy n//2 behavior."""
    engine = DTWEngine()
    n = 100
    rng = np.random.default_rng(1)
    curve = rng.standard_normal(n).cumsum()
    depths = np.linspace(0, 1000, n)

    res_default = engine.correlate(curve, depths, curve.copy(), depths)
    res_midpoint = engine.correlate(
        curve, depths, curve.copy(), depths, ref_depth=float(depths[n // 2]),
    )
    assert abs(res_default.suggested_depth - res_midpoint.suggested_depth) < 1e-6


def test_dtw_perf_under_one_second_for_1k_samples():
    """11.6-E regression: typical 1000-sample DTW must complete well under 1s
    so a 5-well auto-correlate (4 propagations) stays under the 5s budget."""
    import time
    engine = DTWEngine()
    n = 1000
    rng = np.random.default_rng(42)
    ref = rng.standard_normal(n).cumsum()
    tgt = np.roll(ref, n // 20)
    depths = np.linspace(1000.0, 3000.0, n)

    t0 = time.perf_counter()
    result = engine.correlate(ref, depths, tgt, depths)
    elapsed = time.perf_counter() - t0
    assert elapsed < 1.0, f"DTW took {elapsed:.3f}s — perf regression"
    assert 0.0 <= result.cost <= 1.0


def test_progress_callback_receives_monotonic_updates():
    """11.6-E: UI progress bar wiring needs (current, total) updates."""
    engine = DTWEngine()
    n = 200
    rng = np.random.default_rng(7)
    ref = rng.standard_normal(n).cumsum()
    tgt = np.roll(ref, 5)
    depths = np.linspace(0, 1000, n)

    seen: list[tuple[int, int]] = []
    engine.correlate(
        ref, depths, tgt, depths,
        progress_callback=lambda cur, total: seen.append((cur, total)),
    )

    assert len(seen) > 0
    # All totals consistent
    assert all(total == n for _, total in seen)
    # Strictly non-decreasing current
    currents = [cur for cur, _ in seen]
    assert currents == sorted(currents)
    # Reaches the end
    assert seen[-1][0] == n


def _naive_dtw(ref, tgt, ref_depths, tgt_depths, band_radius, ref_depth=None):
    """Scalar Sakoe-Chiba DTW matching DTWEngine.correlate semantics."""
    n, m = len(ref), len(tgt)
    dist = np.abs(ref[:, None] - tgt[None, :])
    cost = np.full((n, m), np.inf)
    cost[0, 0] = dist[0, 0]
    for i in range(n):
        for j in range(m):
            if abs(j - i) > band_radius:
                continue
            if i == 0 and j == 0:
                continue
            prev = []
            if i > 0:
                prev.append(cost[i - 1, j])
            if j > 0:
                prev.append(cost[i, j - 1])
            if i > 0 and j > 0:
                prev.append(cost[i - 1, j - 1])
            if prev:
                cost[i, j] = dist[i, j] + min(prev)

    i, j = n - 1, m - 1
    path = [(i, j)]
    total_dist = 0.0
    while i > 0 or j > 0:
        candidates = []
        if i > 0 and j > 0:
            candidates.append((cost[i - 1, j - 1], i - 1, j - 1))
        if i > 0:
            candidates.append((cost[i - 1, j], i - 1, j))
        if j > 0:
            candidates.append((cost[i, j - 1], i, j - 1))
        if not candidates:
            break
        c_val, ni, nj = min(candidates, key=lambda item: item[0])
        if c_val == np.inf:
            break
        total_dist += abs(ref[i] - tgt[j])
        i, j = ni, nj
        path.append((i, j))
    total_dist += abs(ref[0] - tgt[0])
    path.reverse()

    if ref_depth is None:
        ref_idx = n // 2
    else:
        ref_idx = int(np.argmin(np.abs(ref_depths - ref_depth)))
    target_indices = [pj for pi, pj in path if pi == ref_idx]
    if target_indices:
        matched = int(np.median(target_indices))
    else:
        closest = int(np.argmin([abs(pi - ref_idx) for pi, _pj in path]))
        matched = path[closest][1]
    suggested = float(tgt_depths[matched])
    normalized_cost = total_dist / len(path)
    max_diff = np.max(np.abs(ref)) + np.max(np.abs(tgt))
    norm_cost = min(normalized_cost / max(1e-6, max_diff), 1.0)
    return suggested, norm_cost, path


def test_vectorized_dtw_matches_reference_implementation():
    """Numerical equivalence: vectorized result must match a naive nested-loop
    reference within float tolerance on a small case."""
    engine = DTWEngine()

    # Hand-computed identity pair: midpoint of [100, 200, 300] stays at 200.
    ident = np.array([0.0, 1.0, 0.0])
    ident_d = np.array([100.0, 200.0, 300.0])
    ident_res = engine.correlate(ident, ident_d, ident.copy(), ident_d, band_radius=3)
    ident_sug, ident_cost, _ = _naive_dtw(ident, ident, ident_d, ident_d, 3)
    assert ident_res.suggested_depth == pytest.approx(200.0)
    assert ident_res.suggested_depth == pytest.approx(ident_sug)
    assert ident_res.cost == pytest.approx(ident_cost, abs=1e-12)

    rng = np.random.default_rng(13)
    n, m = 40, 35
    ref = rng.standard_normal(n).cumsum()
    tgt = rng.standard_normal(m).cumsum()
    ref_d = np.linspace(0, 400, n)
    tgt_d = np.linspace(0, 350, m)
    band = max(n, m)

    expected_depth, expected_cost, _path = _naive_dtw(ref, tgt, ref_d, tgt_d, band)
    res = engine.correlate(ref, ref_d, tgt, tgt_d, band_radius=band)
    assert res.suggested_depth == pytest.approx(expected_depth, abs=1e-9)
    assert res.cost == pytest.approx(expected_cost, abs=1e-9)

    res2 = engine.correlate(ref, ref_d, tgt, tgt_d, band_radius=band * 2)
    assert res2.suggested_depth == pytest.approx(res.suggested_depth, abs=1e-9)
    assert res2.cost == pytest.approx(res.cost, abs=1e-9)
