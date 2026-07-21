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
