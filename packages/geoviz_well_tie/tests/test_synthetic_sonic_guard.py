"""ISSUE-025: non-positive / non-finite sonic must not poison the whole
reflectivity series via inf intermediates."""

from __future__ import annotations

import numpy as np

from geoviz_well_tie.synthetic import compute_reflectivity


def test_zero_sonic_yields_local_gap_not_global_nan():
    sonic = np.array([240.0, 250.0, 0.0, 260.0, 250.0])
    density = np.full(5, 2.4)
    r = compute_reflectivity(sonic, density)
    assert r.shape == (4,)
    # Interfaces not adjacent to the zero sample must stay finite.
    assert np.isfinite(r[0])
    # Interfaces touching the bad sample become explicit gaps (NaN), not
    # fabricated values.
    assert np.isnan(r[1]) and np.isnan(r[2])
    assert np.isfinite(r[3])


def test_all_valid_sonic_unchanged():
    sonic = np.array([240.0, 250.0, 260.0, 250.0])
    density = np.full(4, 2.4)
    r = compute_reflectivity(sonic, density)
    assert np.all(np.isfinite(r))
    # Sonic increasing → velocity/impedance decreasing → negative
    # reflectivity first; sonic decreasing after the peak reverses it.
    assert r[0] < 0 and r[2] > 0
