"""WL-13: depth track / grid nice-number intervals must work for any span magnitude."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.depth_ruler import DepthRuler
from geoviz_well_log.renderer.track_base import nice_depth_interval

RECT_HEIGHT = 600.0


def _tick_count(span: float, interval: float) -> int:
    return int(span / interval) + 1


@pytest.mark.parametrize("span", [0.05, 0.1, 0.5, 0.9, 7.0, 7000.0, 50000.0])
def test_interval_is_sub_unit_and_bounded(span):
    interval = nice_depth_interval(span, RECT_HEIGHT, min_px=20.0)
    assert 0 < interval <= span / 2
    assert _tick_count(span, interval) >= 2


def test_sub_unit_span_produces_decimal_intervals():
    assert nice_depth_interval(0.3, RECT_HEIGHT, min_px=20.0) <= 0.15
    assert nice_depth_interval(0.05, RECT_HEIGHT, min_px=20.0) <= 0.025


def test_depth_track_interval_follows_span():
    track = DepthTrack(top_depth=1000.0, bottom_depth=1000.5)
    assert track._compute_tick_interval(RECT_HEIGHT) <= 0.25
    track.set_depth_range(0.0, 30000.0)
    interval = track._compute_tick_interval(RECT_HEIGHT)
    assert interval >= 1000.0  # beyond the old 5000-candidate ceiling the step keeps growing


def test_matches_depth_ruler_algorithm_for_same_inputs():
    ruler = DepthRuler()
    for span in (0.05, 0.3, 42.0, 12345.0):
        top, bottom = 10.0, 10.0 + span
        assert ruler._compute_nice_intervals(top, bottom, int(RECT_HEIGHT)) == nice_depth_interval(
            span, RECT_HEIGHT, min_px=ruler._TARGET_PIXEL_SPACING
        )
