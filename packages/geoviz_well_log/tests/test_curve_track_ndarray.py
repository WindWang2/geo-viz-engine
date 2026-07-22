"""CurveTrack ndarray storage + rendering-equivalence tests."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _old_list_downsample(depths, values, pixel_height):
    """P1 list-based reference implementation (kept for parity checks)."""
    if len(depths) <= pixel_height * 2:
        return list(depths), list(values)
    arr_v = np.array(values)
    step = max(1, len(arr_v) // pixel_height)
    result_d, result_v = [], []
    for i in range(0, len(arr_v), step):
        chunk = arr_v[i:i + step]
        max_idx = i + int(np.argmax(chunk))
        min_idx = i + int(np.argmin(chunk))
        if max_idx <= min_idx:
            result_d.append(depths[max_idx]); result_v.append(values[max_idx])
            result_d.append(depths[min_idx]); result_v.append(values[min_idx])
        else:
            result_d.append(depths[min_idx]); result_v.append(values[min_idx])
            result_d.append(depths[max_idx]); result_v.append(values[max_idx])
    return result_d, result_v


def _make_track(n: int = 5000, with_nan: bool = False):
    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.curve_track import CurveTrack

    rng = np.random.default_rng(7)
    values = (rng.random(n) * 100).tolist()
    if with_nan:
        values[100] = float("nan")
        values[2500] = float("nan")
    curve = CurveData(
        name="GR", unit="API",
        depth=[float(i) * 0.125 for i in range(n)],
        values=values,
        display_range=(0.0, 100.0),
    )
    return CurveTrack([curve]), values


def test_sorted_storage_is_ndarray(qapp):
    track, _ = _make_track()
    assert isinstance(track._sorted_depths["GR"], np.ndarray)
    assert isinstance(track._sorted_values["GR"], np.ndarray)


def test_numpy_downsample_parity_with_list_reference():
    from geoviz_well_log.renderer.downsample import numpy_minmax_downsample

    n = 5000
    rng = np.random.default_rng(42)
    depths = np.arange(n, dtype=np.float64) * 0.125
    values = rng.random(n) * 100
    ref_d, ref_v = _old_list_downsample(depths.tolist(), values.tolist(), 200)
    out_d, out_v = numpy_minmax_downsample(depths, values, 200)
    assert isinstance(out_d, np.ndarray) and isinstance(out_v, np.ndarray)
    np.testing.assert_array_equal(out_d, np.array(ref_d))
    np.testing.assert_array_equal(out_v, np.array(ref_v))


def test_numpy_downsample_passthrough_when_small():
    from geoviz_well_log.renderer.downsample import numpy_minmax_downsample

    depths = np.array([1.0, 2.0, 3.0])
    values = np.array([4.0, 5.0, 6.0])
    out_d, out_v = numpy_minmax_downsample(depths, values, 100)
    np.testing.assert_array_equal(out_d, depths)
    np.testing.assert_array_equal(out_v, values)


def test_visible_data_matches_bisect_reference(qapp):
    track, _ = _make_track()
    track.set_depth_range(100.0, 500.0)
    depths, values = track._visible_data(track._curves[0])
    # Reference: old bisect logic on the same sorted arrays
    sd = track._sorted_depths["GR"]
    sv = track._sorted_values["GR"]
    import bisect

    margin = (500.0 - 100.0) * 0.05
    top, bottom = 100.0 - margin, 500.0 + margin
    start = max(0, bisect.bisect_left(sd.tolist(), top) - 1)
    end = min(len(sd), bisect.bisect_right(sd.tolist(), bottom) + 1)
    np.testing.assert_array_equal(depths, sd[start:end])
    np.testing.assert_array_equal(values, sv[start:end])


def test_header_range_uses_nan_safe_precomputed(qapp):
    track, _ = _make_track(with_nan=True)
    curve = track._curves[0]
    range_str = track._range_str_for(curve)
    vals = np.asarray(track._sorted_values["GR"], dtype=float)
    expected = f"{np.nanmin(vals):.1f}~{np.nanmax(vals):.1f} API".strip()
    assert range_str == expected
    assert "nan" not in range_str.lower()


def test_downsampled_cache_hits_on_repeated_key(qapp):
    track, _ = _make_track()
    track.set_depth_range(0.0, 625.0)
    from PySide6.QtCore import QRectF

    rect = QRectF(0, 0, 150, 800)
    d1 = track._cached_downsampled(track._curves[0], rect)
    d2 = track._cached_downsampled(track._curves[0], rect)
    assert d1[0] is d2[0] and d1[1] is d2[1]  # same cached arrays on hit


def test_downsample_cache_invalidated_on_zoom_at_fixed_top(qapp):
    track, _ = _make_track()
    track.set_depth_range(0.0, 625.0)
    from PySide6.QtCore import QRectF

    rect = QRectF(0, 0, 150, 800)
    d1 = track._cached_downsampled(track._curves[0], rect)
    # Zoom in at the same top edge: span halves
    track.set_depth_range(0.0, 312.5)
    d2 = track._cached_downsampled(track._curves[0], rect)
    assert d1[0] is not d2[0]  # recomputed, not a stale hit
    # Window actually narrowed
    assert d2[0].max() <= 312.5 * 1.05 + 0.125


def test_path_cache_returns_same_object_on_hit(qapp):
    """The QPainterPath is cached — repeated calls with the same rect return
    the identical path object (no per-paint rebuild). Regression guard for the
    classic PySide6 per-paint zip-loop bottleneck."""
    track, _ = _make_track()
    track.set_depth_range(0.0, 625.0)
    from PySide6.QtCore import QRectF

    rect = QRectF(0, 0, 150, 800)
    p1 = track._cached_path(track._curves[0], rect)
    p2 = track._cached_path(track._curves[0], rect)
    assert p1 is p2  # cache hit — same object
    assert not p1.isEmpty()


def test_path_cache_invalidated_on_zoom(qapp):
    """Zooming rebuilds the path (cache key includes the depth window)."""
    track, _ = _make_track()
    track.set_depth_range(0.0, 625.0)
    from PySide6.QtCore import QRectF

    rect = QRectF(0, 0, 150, 800)
    p1 = track._cached_path(track._curves[0], rect)
    track.set_depth_range(0.0, 312.5)  # zoom in: span halves
    p2 = track._cached_path(track._curves[0], rect)
    assert p1 is not p2  # rebuilt


def test_build_curve_path_splits_at_nan_gaps():
    """NaN entries break the curve into separate sub-paths (visual gaps)."""
    from geoviz_well_log.renderer.curve_track import build_curve_path

    xs = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
    ys = np.array([0.0, 1.0, np.nan, 3.0, 4.0, 5.0])
    path = build_curve_path(xs, ys)
    # Two sub-paths: [0,1] and [3,4,5], separated by the NaN at index 2.
    # elementCount counts moveTo+lineTo elements; first run has 2 points,
    # second run has 3 points -> 1 moveTo + 1 lineTo + 1 moveTo + 2 lineTo = 5.
    assert path.elementCount() == 5


def test_simplify_curve_screen_space_reduces_dense_arrays():
    """The screen-space simplifier reduces >1000-point arrays to ~buckets."""
    from geoviz_well_log.renderer.curve_track import simplify_curve_screen_space

    n = 5000
    xs = np.arange(n, dtype=np.float64)
    ys = np.arange(n, dtype=np.float64)
    sx, sy = simplify_curve_screen_space(xs, ys)
    assert len(sx) < n  # reduced
    assert len(sx) == len(sy)


def test_simplify_curve_screen_space_passthrough_small():
    """Small arrays pass through untouched."""
    from geoviz_well_log.renderer.curve_track import simplify_curve_screen_space

    xs = np.arange(100, dtype=np.float64)
    sx, sy = simplify_curve_screen_space(xs, xs)
    assert len(sx) == 100
