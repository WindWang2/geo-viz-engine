"""#113: domain presets must never return an inverted (vmin > vmax) range.

The RHOB/NPHI presets hard-code one unit system (g/cm3 density clamped to
[1.5, 3.0], decimal-fraction neutron clamped to [-0.05, 1.0]). The same
mnemonics arrive in other units — neutron in % (2..45), density in kg/m3
(2200..2650) — where p1/p99 exceed the clamped bound and the preset returned
vmin > vmax (measured: NPHI% -> (2.36, 1.0)). CurveTrack._value_to_x then
divides by a negative denominator and the curve silently vanishes
(x = -1838.8 px outside the track).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QApplication

from geoviz_well_log.models import CurveData
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.robust_scale import compute_robust_display_range


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _ramp(lo: float, hi: float) -> np.ndarray:
    return np.tile(np.linspace(lo, hi, 500), 3)


@pytest.mark.parametrize(
    "name, unit, lo, hi",
    [
        ("NPHI", "%", 2.0, 40.0),      # percent neutron, ResForm '中子 %'
        ("CNL", "%", 2.0, 45.0),
        ("中子", "%", 2.0, 40.0),
        ("RHOB", "kg/m3", 2200.0, 2650.0),
        ("DEN", "kg/m3", 2200.0, 2650.0),
        ("密度", "kg/m3", 2200.0, 2650.0),
    ],
)
def test_alternate_unit_presets_are_not_inverted(name, unit, lo, hi):
    vals = _ramp(lo, hi)
    vmin, vmax = compute_robust_display_range(vals, name)
    assert vmin <= vmax, f"{name} [{unit}] inverted range ({vmin}, {vmax})"
    # The fallback range must still cover the data it will display.
    assert vmin <= lo, f"{name} vmin={vmin} clips data min {lo}"
    assert vmax >= hi, f"{name} vmax={vmax} clips data max {hi}"


@pytest.mark.parametrize(
    "name, lo, hi, floor, ceil",
    [
        ("NPHI", 0.05, 0.45, -0.05, 1.0),   # decimal fraction -> preset applies
        ("RHOB", 2.20, 2.65, 1.5, 3.0),     # g/cm3 -> preset applies
    ],
)
def test_canonical_unit_presets_still_apply(name, lo, hi, floor, ceil):
    vmin, vmax = compute_robust_display_range(_ramp(lo, hi), name)
    assert vmin <= vmax
    assert floor <= vmin <= vmax <= ceil


def test_percent_neutron_curve_stays_inside_track(qapp):
    """End-to-end victim path: the robust range feeds CurveTrack mapping and
    every sample x must land inside the track rect (old: -1838.8 px)."""
    vals = _ramp(2.0, 40.0)
    rng = compute_robust_display_range(vals, "NPHI")
    assert rng[0] <= rng[1]

    curve = CurveData(
        name="NPHI",
        unit="%",
        depth=[float(d) for d in range(1500)],
        values=[float(v) for v in vals[:1500]],
        display_range=rng,
    )
    track = CurveTrack(curves=[curve], label="NPHI", width=100)
    rect = QRectF(0.0, 0.0, 100.0, 800.0)
    for value in (2.0, 20.0, 40.0):
        x = track._value_to_x(value, track._curves[0].display_range, rect)
        assert rect.left() - 1e-6 <= x <= rect.right() + 1e-6, (
            f"value {value} mapped to x={x} outside track"
        )


def test_constant_percent_neutron_range_not_inverted():
    """All-equal percent samples: the preset collapses (vmin > vmax) and must
    fall back instead of returning e.g. (18.0, 1.0)."""
    vmin, vmax = compute_robust_display_range([20.0] * 100, "NPHI")
    assert vmin <= vmax
    assert vmax > vmin  # degenerate data still gets a drawable span
