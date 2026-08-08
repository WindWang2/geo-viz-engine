"""Tests for build_synthetic_seismogram_overlay (3D synthetic beside a well)."""

from __future__ import annotations

import numpy as np
import pytest


def _vertical_path(n: int) -> np.ndarray:
    """A straight vertical well along -Z at (0, 0)."""
    return np.column_stack([
        np.zeros(n, dtype=np.float32),
        np.zeros(n, dtype=np.float32),
        -np.arange(n, dtype=np.float32),
    ])


def _deviated_path(n: int) -> np.ndarray:
    """A well that drifts in +X as it goes down."""
    return np.column_stack([
        np.arange(n, dtype=np.float32),
        np.zeros(n, dtype=np.float32),
        -np.arange(n, dtype=np.float32),
    ])


def test_overlay_empty_path_returns_empty():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    out = build_synthetic_seismogram_overlay(np.empty((0, 3)), np.array([0.1, 0.2]))
    assert out.shape == (0, 3)
    assert out.dtype == np.float32


def test_overlay_empty_trace_returns_zero_deflection():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    path = _vertical_path(5)
    out = build_synthetic_seismogram_overlay(path, np.array([]))
    # No trace -> no deflection -> overlay coincides with the path.
    assert out.shape == (5, 3)
    assert np.allclose(out, path)


def test_overlay_zero_amplitude_coincides_with_path():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    path = _deviated_path(6)
    out = build_synthetic_seismogram_overlay(path, np.zeros(6), scale=10.0)
    assert np.allclose(out, path)


def test_overlay_deflects_along_horizontal_normal():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    # Deviated path along +X/-Z: tangent ~ (1,0,-1); horizontal normal ~ (0,1,0).
    path = _deviated_path(4)
    trace = np.array([0.0, 1.0, -1.0, 0.5])
    out = build_synthetic_seismogram_overlay(path, trace, scale=2.0)
    # X and Z should be unchanged; only Y should deflect.
    assert np.allclose(out[:, 0], path[:, 0])
    assert np.allclose(out[:, 2], path[:, 2])
    # Y deflection = amplitude * scale (normal is unit (0,1,0)).
    assert np.allclose(out[:, 1], trace * 2.0, atol=1e-5)


def test_overlay_vertical_well_falls_back_to_x_offset():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    path = _vertical_path(3)  # vertical -> no horizontal normal -> fallback +X
    trace = np.array([1.0, 0.0, -1.0])
    out = build_synthetic_seismogram_overlay(path, trace, scale=1.0)
    # Y and Z unchanged; X deflects by amplitude.
    assert np.allclose(out[:, 1], 0.0)
    assert np.allclose(out[:, 2], path[:, 2])
    assert np.allclose(out[:, 0], trace)


def test_overlay_resamples_trace_to_path_length():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    path = _deviated_path(5)
    # Trace has 3 samples; must be resampled to 5.
    trace = np.array([0.0, 1.0, 0.0])
    out = build_synthetic_seismogram_overlay(path, trace, scale=1.0)
    assert out.shape == (5, 3)
    # Endpoints should match (resampling is linear, trace starts/ends at 0).
    assert np.allclose(out[0], path[0], atol=1e-5)
    assert np.allclose(out[-1], path[-1], atol=1e-5)


def test_overlay_nan_inf_amplitudes_clamped_to_zero():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    path = _deviated_path(4)
    trace = np.array([1.0, np.nan, np.inf, -np.inf])
    out = build_synthetic_seismogram_overlay(path, trace, scale=1.0)
    # Only the finite amplitude (index 0) should deflect; others coincide.
    assert np.allclose(out[1], path[1], atol=1e-5)
    assert np.allclose(out[2], path[2], atol=1e-5)
    assert np.allclose(out[3], path[3], atol=1e-5)
    assert not np.allclose(out[0], path[0])


def test_overlay_rejects_bad_path_shape():
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    with pytest.raises(ValueError, match="well_path must be"):
        build_synthetic_seismogram_overlay(np.zeros((4, 2)), np.zeros(4))


def test_overlay_end_to_end_with_synthetic_from_logs():
    """The full synthetic-overlay path: logs -> synthetic -> 3D wiggle track."""
    from geoviz_well_tie.synthetic import synthetic_from_logs
    from geoviz_well_seismic_3d.well_geometry import (
        build_synthetic_seismogram_overlay,
    )

    rng = np.random.default_rng(0)
    n = 40
    # Plausible sonic (~100-400 us/m) + density (~2.0-2.7 g/cc).
    sonic = 250.0 + 80.0 * np.sin(np.linspace(0, 6, n))
    density = 2.3 + 0.2 * rng.random(n)
    synth = synthetic_from_logs(sonic, density, wavelet_freq=30.0, dt_s=0.002)
    path = _deviated_path(n)
    out = build_synthetic_seismogram_overlay(path, synth, scale=20.0)
    assert out.shape == (n, 3)
    assert out.dtype == np.float32
    # Non-trivial deflection (synthetic is not all-zero).
    assert np.linalg.norm(out - path) > 0.0


def test_facade_exports_build_synthetic_seismogram_overlay():
    from geoviz import build_synthetic_seismogram_overlay  # noqa: F401
