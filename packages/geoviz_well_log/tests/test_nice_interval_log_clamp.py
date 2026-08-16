"""WL-13 / WL-16 regression tests: sub-unit nice-number ticks and log-clamp
parity in _value_to_x.

- WL-13 (#428): the depth grid/tick candidate table was integer-only
  [1..5000]; a visible span below 1 depth unit produced zero grid lines and
  labels rounding onto the same integer.
- WL-16 (#429): _value_to_x replaced non-positive values with the raw lo
  BEFORE clamping lo to 1e-10, so a range like (-0.5, 100) raised a log10
  domain error inside paintEvent; the clamping also diverged from the
  polyline render path.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from geoviz_well_log.models import CurveData
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.track_base import BaseTrack


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


RECT = QRectF(0, 0, 60, 400)


def _mantissa_exponent(interval: float) -> tuple[float, int]:
    exp = math.floor(math.log10(interval))
    return interval / 10**exp, exp


class TestGridInterval:
    def test_sub_unit_span_yields_sub_unit_interval(self, qapp):
        track = DepthTrack(top_depth=1000.152, bottom_depth=1000.612)
        interval = track._compute_tick_interval(RECT.height())
        assert 0 < interval < 1, "span of 0.46 must produce a sub-unit interval"
        mantissa, _ = _mantissa_exponent(interval)
        assert mantissa in (1.0, 2.0, 5.0)

    def test_grid_interval_sub_unit(self, qapp):
        # Span 0.46 over 400 px: raw = 0.46/400*20 = 0.023 -> 0.05
        track = DepthTrack()
        interval = track._compute_grid_interval(400.0, 0.46)
        assert interval == pytest.approx(0.05)

    def test_grid_interval_above_old_table(self, qapp):
        # raw = 20000/100*20 = 4000 -> 5000, and far larger spans keep walking
        track = DepthTrack()
        assert track._compute_grid_interval(100.0, 20000.0) == pytest.approx(5000.0)
        # raw = 2e5/50*20 = 8e4: no {1,2,5}x10^4 candidate >= 8e4, so the
        # step advances to the NEXT decade (1e5) — the smallest nice step
        # whose spacing still meets the 20px floor (5e4 would render 12.5px).
        # (The old fixed table capped at 5000 and rendered a grid 10x too
        # dense; the pre-unify walk saturated the decade at 5x10^4.)
        assert track._compute_grid_interval(50.0, 2e5) == pytest.approx(1e5)

    def test_interval_keeps_pixels_per_tick_floor(self, qapp):
        # nice_depth_interval always returns a step >= raw, so tick spacing
        # meets the 20px floor exactly; keep the >=10px assertion as the
        # hard regression floor against any future re-tightening.
        track = DepthTrack()
        for span in (0.3, 0.46, 2.7, 137.0, 5000.0, 123456.0):
            interval = track._compute_grid_interval(400.0, span)
            px_per_tick = 400.0 / (span / interval)
            assert px_per_tick >= 10.0, f"span={span} interval={interval}"

    def test_scene_ruler_matches_track_interval_policy(self, qapp):
        """Scene/export ruler delegates to the shared nice-step policy.

        The scene item used to carry its own decade table that only ever
        coincided with the renderer policy; this lock-step test pins both
        to concrete expected steps so the two sites can never diverge again
        (e.g. by reintroducing a decade-saturating walk on either side).
        """
        from geoviz_well_log.scene.depth_ruler_item import DepthRulerItem

        item = DepthRulerItem(height=400)
        # (top, bottom, height, expected scene interval at 60px target)
        expected_scene = [
            (0.0, 0.46, 400.0, 0.1),     # raw = 0.069 -> 0.1
            (1000.0, 21000.0, 100.0, 20000.0),  # raw = 1.2e4 -> 2x10^4
            (0.0, 2e5, 50.0, 5e5),       # raw = 2.4e5 -> 5x10^5
            (0.0, 123456.0, 400.0, 20000.0),  # raw = 18518.4 -> 2x10^4
        ]
        for top, bottom, height, want in expected_scene:
            got = item._compute_nice_intervals(top, bottom, height)
            assert got == pytest.approx(want), (top, bottom, height, got, want)

    def test_depth_track_paints_labels_offscreen(self, qapp):
        """Full offscreen paint of a <1-unit window must draw SOMETHING and
        not raise (previously: zero lines, all labels the same integer)."""
        track = DepthTrack(top_depth=1000.152, bottom_depth=1000.612)
        track.resize(60, 400)
        img = QImage(60, 400, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        try:
            track.paint_grid(painter, RECT)
            track.paint_content(painter, RECT)
        finally:
            painter.end()
        # The old integer table rendered an empty track for this window;
        # grid lines plus labels must leave visible pixels somewhere.
        data = img.constBits().tobytes()
        assert data.count(0) < len(data), "no visible pixels painted"


class TestValueToXLogClamp:
    def _track(self, qapp, lo: float, hi: float) -> CurveTrack:
        curve = CurveData(
            name="RT",
            unit="ohmm",
            depth=[1000.0, 1000.5, 1001.0],
            values=[1.0, 10.0, 100.0],
            display_range=(lo, hi),
        )
        return CurveTrack([curve], log_scale=True)

    def test_nonpositive_value_with_nonpositive_lo_does_not_raise(self, qapp):
        track = self._track(qapp, -0.5, 100.0)
        # Pre-fix: value=-3 -> value=lo=-0.5 -> log10(-0.5) ValueError
        x = track._value_to_x(-3.0, (-0.5, 100.0), QRectF(0, 0, 150, 400))
        assert 0.0 <= x <= 150.0

    def test_zero_value_clamped_to_floor(self, qapp):
        track = self._track(qapp, 1e-12, 100.0)
        x_floor = track._value_to_x(0.0, (1e-12, 100.0), QRectF(0, 0, 150, 400))
        assert x_floor == pytest.approx(0.0, abs=1e-6)

    def test_matches_render_path_clamping(self, qapp):
        """_value_to_x must share the polyline's max(lo, 1e-10) floor: the
        snapped hover point lands on the same x the curve paints at."""
        track = self._track(qapp, -0.5, 100.0)
        rect = QRectF(0, 0, 150, 400)
        lo, hi = -0.5, 100.0
        for v in (-7.0, 0.0, 1e-8, 1.0, 55.0):
            x = track._value_to_x(v, (lo, hi), rect)
            clamped = max(v, max(lo, 1e-10))
            expected = rect.left() + (
                (math.log10(clamped) - math.log10(max(lo, 1e-10)))
                / (math.log10(max(hi, 1e-10)) - math.log10(max(lo, 1e-10)))
            ) * rect.width()
            assert x == pytest.approx(expected)

    def test_positive_values_linear_case_unchanged(self, qapp):
        track = self._track(qapp, 0.2, 2000.0)
        rect = QRectF(0, 0, 150, 400)
        x_mid = track._value_to_x(20.0, (0.2, 2000.0), rect)
        assert x_mid == pytest.approx(75.0)  # geometric middle of 0.2..2000
