"""Regression tests: CurveTrack._value_to_x must never log10 a non-positive value.

WL-16 (#429): hover-snap painting called ``_value_to_x`` with a display range
whose lower bound is <= 0 (and > -100, so the range sanitizer does not rewrite
it), raising ``ValueError: math domain error`` inside paintEvent. The fix
shares the render path's ``max(lo, 1e-10)`` floor so the snap dot x position
matches the drawn polyline exactly.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import math

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from geoviz_well_log.models import CurveData
from geoviz_well_log.renderer.curve_track import CurveTrack


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def log_track(qapp):
    curve = CurveData(
        name="RT",
        unit="",
        depth=[1.0, 2.0],
        values=[1.0, 2.0],
        display_range=(1.0, 100.0),
    )
    return CurveTrack(curves=[curve], label="RT", width=150, log_scale=True)


@pytest.mark.parametrize("value", [-5.0, 0.0, 1e-12, 5.0])
@pytest.mark.parametrize("lo", [-0.5, 0.0, 0.1])
def test_log_scale_value_to_x_never_logs_nonpositive(log_track, value, lo):
    """Non-positive values and non-positive range lows must not raise, and must
    match the render path's shared clip semantics (floor = max(lo, 1e-10))."""
    rect = QRectF(20.0, 0.0, 200.0, 100.0)
    x = log_track._value_to_x(value, (lo, 100.0), rect)
    assert math.isfinite(x)

    floor = max(lo, 1e-10)
    clipped = max(value, floor)
    log_lo = math.log10(floor)
    log_hi = math.log10(max(100.0, 1e-10))
    expected = rect.left() + (math.log10(clipped) - log_lo) / (log_hi - log_lo) * rect.width()
    assert x == pytest.approx(expected, rel=1e-12, abs=1e-9)


def test_log_scale_positive_value_unchanged(log_track):
    rect = QRectF(0.0, 0.0, 100.0, 100.0)
    x = log_track._value_to_x(10.0, (1.0, 100.0), rect)
    expected = 0.0 + (math.log10(10.0) - math.log10(1.0)) / (
        math.log10(100.0) - math.log10(1.0)
    ) * 100.0
    assert x == pytest.approx(expected, rel=1e-12)


def test_log_scale_zero_range_uses_midpoint(log_track):
    """Degenerate equal range (after flooring) must not divide by zero."""
    rect = QRectF(10.0, 0.0, 50.0, 100.0)
    x = log_track._value_to_x(-1.0, (0.0, 0.0), rect)
    assert x == pytest.approx(rect.left() + 0.5 * rect.width())


def test_linear_scale_unchanged():
    track = CurveTrack(curves=[], label="", width=150, log_scale=False)
    rect = QRectF(10.0, 0.0, 100.0, 100.0)
    assert track._value_to_x(5.0, (0.0, 10.0), rect) == pytest.approx(60.0)
