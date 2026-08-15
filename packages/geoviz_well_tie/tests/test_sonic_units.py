"""Unit-aware sonic normalization for well-tie TWT (WL-9 / #406).

The workbench host classified sonic curves with a numeric median heuristic
that misfires on tight carbonates (typical 140-150 µs/m is inside the guessed
µs/ft band, so TWT came out ~3.3x too large). The engine helper resolves the
unit from curve.unit metadata first and only falls back to the heuristic —
with a warning — when the unit is missing or unknown.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from geoviz_well_tie import (
    US_FT_TO_US_M,
    canonical_sonic_unit,
    normalize_sonic_units,
)


@pytest.mark.parametrize("unit", ["US/M", "us/m", "µs/m", "μs/m", "USM", "UM", "US/M"])
def test_us_per_m_variants_unchanged(unit):
    sonic = np.full(100, 145.0)
    out, resolved, warn = normalize_sonic_units(sonic, unit)
    assert resolved == "us/m"
    assert warn is None
    np.testing.assert_array_equal(out, sonic)


@pytest.mark.parametrize("unit", ["US/F", "us/ft", "µs/ft", "USF", "UF", "US/FT"])
def test_us_per_ft_variants_scaled(unit):
    sonic = np.full(100, 145.0)
    out, resolved, warn = normalize_sonic_units(sonic, unit)
    assert resolved == "us/m"
    assert warn is None
    assert out[0] == pytest.approx(145.0 * US_FT_TO_US_M)


def test_canonical_unit_unknown_returns_none():
    assert canonical_sonic_unit(None) is None
    assert canonical_sonic_unit("") is None
    assert canonical_sonic_unit("DT") is None
    assert canonical_sonic_unit("API") is None


def test_tight_carbonate_us_per_m_twt_is_physical():
    """Acceptance: US/M + median 145 µs/m must NOT be scaled; 1000 m gives
    two-way time 2 * 1000 m * 145 µs/m / 1000 = 290 ms."""
    depths = np.linspace(1000.0, 2000.0, 1001)  # 1000 m of interval
    sonic = np.full_like(depths, 145.0)
    out, resolved, warn = normalize_sonic_units(sonic, "US/M")
    assert warn is None

    dz = np.diff(depths)
    owt_us = dz * (out[:-1] + out[1:]) / 2.0
    twt = np.zeros_like(depths)
    twt[1:] = 2.0 * np.cumsum(owt_us) / 1000.0
    assert twt[-1] == pytest.approx(290.0, abs=1e-6)


def test_us_per_ft_converts_to_physical_twt():
    """US/F must still convert: 145 µs/ft = 475.7 µs/m -> 951.4 ms per 1000 m."""
    depths = np.linspace(1000.0, 2000.0, 1001)
    sonic = np.full_like(depths, 145.0)
    out, _, warn = normalize_sonic_units(sonic, "US/F")
    assert warn is None

    dz = np.diff(depths)
    owt_us = dz * (out[:-1] + out[1:]) / 2.0
    twt = np.zeros_like(depths)
    twt[1:] = 2.0 * np.cumsum(owt_us) / 1000.0
    assert twt[-1] == pytest.approx(2.0 * 1000.0 * 145.0 * US_FT_TO_US_M / 1000.0)


def test_missing_unit_falls_back_to_heuristic_with_warning():
    """145 µs/m with no unit metadata: legacy heuristic converts and warns."""
    sonic = np.full(100, 145.0)
    out, resolved, warn = normalize_sonic_units(sonic, None)
    assert resolved == "us/m"
    assert out[0] == pytest.approx(145.0 * US_FT_TO_US_M)
    assert warn is not None and "µs/ft" in warn

    # Control group: shale-like 350 µs/m stays untouched but still warns.
    sonic2 = np.full(100, 350.0)
    out2, _, warn2 = normalize_sonic_units(sonic2, None)
    assert out2[0] == pytest.approx(350.0)
    assert warn2 is not None


def test_unknown_unit_with_nan_samples_no_crash():
    sonic = np.array([np.nan, np.nan])
    out, resolved, warn = normalize_sonic_units(sonic, "DT")
    assert resolved == "us/m"
    assert warn is not None
    assert np.all(np.isnan(out))
