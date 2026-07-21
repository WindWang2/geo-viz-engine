"""Tests for the injectable curve downsample provider."""
from __future__ import annotations

from geoviz_well_log.renderer.downsample import (
    get_downsample_provider,
    numpy_minmax_downsample,
    set_downsample_provider,
)


def _sample(n: int = 1000):
    depths = [float(i) for i in range(n)]
    values = [float((i * 37) % 101) for i in range(n)]
    return depths, values


def test_default_provider_is_numpy_impl():
    assert get_downsample_provider() is numpy_minmax_downsample


def test_numpy_downsample_preserves_extrema_and_order():
    depths, values = _sample()
    out_d, out_v = numpy_minmax_downsample(depths, values, 50)
    assert len(out_d) == len(out_v)
    assert len(out_d) <= 2 * 50 + 2
    assert max(out_v) == max(values)
    assert min(out_v) == min(values)
    # Depth order non-decreasing (no zigzag)
    assert all(b >= a for a, b in zip(out_d, out_d[1:]))


def test_numpy_downsample_passthrough_when_small():
    depths, values = _sample(40)
    out_d, out_v = numpy_minmax_downsample(depths, values, 50)
    assert out_d == depths
    assert out_v == values


def test_set_and_reset_provider():
    calls = []

    def fake(depths, values, pixel_height):
        calls.append(pixel_height)
        return depths[:2], values[:2]

    set_downsample_provider(fake)
    try:
        assert get_downsample_provider() is fake
        out_d, out_v = get_downsample_provider()([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], 10)
        assert out_d == [1.0, 2.0]
        assert calls == [10]
    finally:
        set_downsample_provider(None)
    assert get_downsample_provider() is numpy_minmax_downsample


def test_curve_track_delegates_to_provider():
    """CurveTrack._downsample must route through the module provider."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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
        seen.append((len(depths), pixel_height))
        return depths, values

    set_downsample_provider(spy)
    try:
        track._downsample([1.0, 2.0], [3.0, 4.0], 100)
    finally:
        set_downsample_provider(None)
    assert seen == [(2, 100)]
