"""Tests for the injectable curve downsample provider (ndarray protocol)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np

from geoviz_well_log.renderer.downsample import (
    get_downsample_provider,
    numpy_minmax_downsample,
    set_downsample_provider,
)


def _sample(n: int = 1000):
    depths = np.arange(n, dtype=np.float64)
    values = ((np.arange(n) * 37) % 101).astype(np.float64)
    return depths, values


def test_default_provider_is_numpy_impl():
    assert get_downsample_provider() is numpy_minmax_downsample


def test_numpy_downsample_preserves_extrema_and_order():
    depths, values = _sample()
    out_d, out_v = numpy_minmax_downsample(depths, values, 50)
    assert len(out_d) == len(out_v)
    assert len(out_d) <= 2 * 50 + 2
    assert out_v.max() == values.max()
    assert out_v.min() == values.min()
    assert np.all(np.diff(out_d) >= 0)


def test_numpy_downsample_passthrough_when_small():
    depths, values = _sample(40)
    out_d, out_v = numpy_minmax_downsample(depths, values, 50)
    np.testing.assert_array_equal(out_d, depths)
    np.testing.assert_array_equal(out_v, values)


def test_set_and_reset_provider():
    calls = []

    def fake(depths, values, pixel_height):
        calls.append(pixel_height)
        return depths[:2], values[:2]

    set_downsample_provider(fake)
    try:
        assert get_downsample_provider() is fake
        out_d, out_v = get_downsample_provider()(
            np.array([1.0, 2.0, 3.0]), np.array([4.0, 5.0, 6.0]), 10
        )
        np.testing.assert_array_equal(out_d, np.array([1.0, 2.0]))
        assert calls == [10]
    finally:
        set_downsample_provider(None)
    assert get_downsample_provider() is numpy_minmax_downsample


def test_numpy_downsample_keeps_finite_extrema_when_bin_has_nan():
    """#726: a single NaN must not blank the whole bin's finite min/max."""
    # 20 bins of 5 samples; one NaN in the first bin next to the true extrema.
    values = np.tile(np.array([1.0, np.nan, 3.0, -5.0, 2.0]), 20)
    depths = np.arange(len(values), dtype=np.float64)
    out_d, out_v = numpy_minmax_downsample(depths, values, 20)
    finite = out_v[np.isfinite(out_v)]
    assert finite.size > 0
    assert finite.min() == -5.0
    assert finite.max() == 3.0
    assert np.isnan(out_v).any()


def test_curve_track_delegates_to_provider():
    """CurveTrack._downsample must route through the module provider."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])

    from geoviz_well_log.models import CurveData
    from geoviz_well_log.renderer.curve_track import CurveTrack

    curve = CurveData(
        name="GR", unit="API",
        depth=[float(i) for i in range(10)],
        values=[float(i) for i in range(10)],
        display_range=(0.0, 10.0),
    )
    track = CurveTrack([curve])

    seen = []

    def spy(depths, values, pixel_height):
        seen.append((isinstance(depths, np.ndarray), pixel_height))
        return depths, values

    set_downsample_provider(spy)
    try:
        track._downsample(np.array([1.0, 2.0]), np.array([3.0, 4.0]), 100)
    finally:
        set_downsample_provider(None)
    assert seen == [(True, 100)]


def test_numpy_downsample_bin_nan_break_index_is_in_bin():
    """#845 hook-parity: the NaN breakout must sit at the bin's FIRST
    non-finite index (so the polyline breaks at the hole), not be dropped or
    grafted elsewhere — the contract injected providers must match."""
    # One bin (8 samples) with the NaN at offset 3.
    values = np.array([1.0, 3.0, -5.0, np.nan, 2.0, 4.0, -1.0, 0.0])
    depths = np.arange(len(values), dtype=np.float64)
    out_d, out_v = numpy_minmax_downsample(depths, values, 1)
    nan_depths = out_d[np.isnan(out_v)]
    assert len(nan_depths) == 1
    assert float(nan_depths[0]) == 3.0, (
        "the NaN break sample must sit at the first non-finite index"
    )
    # Finite extrema survive the NaN bin.
    finite = out_v[np.isfinite(out_v)]
    assert finite.min() == -5.0
    assert finite.max() == 4.0


def test_minmax_bin_indices_document_contract():
    """#845: the reference helper is public and matches the documented
    NaN-break semantics for hook providers."""
    from geoviz_well_log.renderer.downsample import minmax_bin_indices

    # All-finite bin: exactly the min/max indices, sorted by index.
    idx = minmax_bin_indices(np.array([1.0, 3.0, -5.0, 2.0]))
    np.testing.assert_array_equal(idx, [1, 2])  # max(1), min(2), sorted
    # NaN bin: finite min/max plus the FIRST NaN index, sorted by index.
    idx = minmax_bin_indices(np.array([1.0, np.nan, 3.0, -5.0, np.nan, 2.0]))
    np.testing.assert_array_equal(idx, [1, 2, 3])  # nan(1), max(2), min(3)
    # Fully non-finite bin: its first sample.
    np.testing.assert_array_equal(
        minmax_bin_indices(np.array([np.nan, np.nan])), [0]
    )


def test_numpy_downsample_floor_binning_with_partial_tail():
    """#845 hook-parity: binning is floor-based — ``step = n // pixels`` with
    a trailing partial bin. A ceil-based partition would emit different
    samples for the same curve (the legacy hook divergence)."""
    # n=10, pixel_height=3 -> step=3, bins [0:3],[3:6],[6:9], partial [9:10].
    values = np.arange(10, dtype=np.float64)
    depths = np.arange(10, dtype=np.float64)
    out_d, out_v = numpy_minmax_downsample(depths, values, 3)
    # Per full bin the min+max = the bin edges; the single-sample tail is
    # kept by the same per-bin rule (min == max, emitted as a pair).
    np.testing.assert_array_equal(out_v, [0.0, 2.0, 3.0, 5.0, 6.0, 8.0, 9.0, 9.0])
