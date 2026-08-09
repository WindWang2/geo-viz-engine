"""Head→bottom well trajectories projected into the active vertical domain."""

from __future__ import annotations

import numpy as np

from .models import TimeDepthTable, VerticalDomain, WellHead, WellTrajectory3D

_DEFAULT_SAMPLES = 32


def project_well_trajectory(
    well: WellHead,
    *,
    domain: VerticalDomain,
    td: TimeDepthTable | None,
    n_samples: int = _DEFAULT_SAMPLES,
) -> WellTrajectory3D:
    """Build a head→bottom polyline in scene XYZ for the given vertical domain.

    In **Time** domain, Z is TWT (ms) from the TD table. Without TD, only the
    wellhead point is returned with a warning (no fabricated time path).
    """
    if domain is VerticalDomain.TIME:
        return _project_time(well, td=td, n_samples=n_samples)
    # Depth path reserved for ticket #63; still return geometric MD path.
    return _project_depth(well, n_samples=n_samples)


def _linspace_path(well: WellHead, n_samples: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = max(2, int(n_samples))
    frac = np.linspace(0.0, 1.0, n, dtype=np.float64)
    xs = well.x + frac * (well.bottom_x - well.x)
    ys = well.y + frac * (well.bottom_y - well.y)
    md = frac * float(well.total_depth_m)
    return xs, ys, md


def _project_time(
    well: WellHead,
    *,
    td: TimeDepthTable | None,
    n_samples: int,
) -> WellTrajectory3D:
    if td is None:
        pts = np.array([[well.x, well.y, 0.0]], dtype=np.float64)
        return WellTrajectory3D(
            name=well.name,
            points=pts,
            has_td=False,
            warning=f"Well {well.name}: missing time-depth table; showing wellhead only in Time domain",
        )

    xs, ys, md = _linspace_path(well, n_samples)
    twt = np.asarray(td.md_to_time_ms(md), dtype=np.float64)
    pts = np.column_stack([xs, ys, twt])
    return WellTrajectory3D(name=well.name, points=pts, has_td=True, warning=None)


def _project_depth(well: WellHead, *, n_samples: int) -> WellTrajectory3D:
    xs, ys, md = _linspace_path(well, n_samples)
    # Z = MD as depth proxy (TVDSS refinement lands with DepthTransform ticket).
    pts = np.column_stack([xs, ys, md])
    return WellTrajectory3D(name=well.name, points=pts, has_td=True, warning=None)


def offset_curve_along_trajectory(
    well_path: np.ndarray,
    curve_values: np.ndarray,
    *,
    scale: float = 0.1,
) -> np.ndarray:
    """Offset a log curve sideways off a well path, for a 3D "curve beside the well" track.

    Promoted from ``paleo_workbench/viz/geomodel/well_seismic.py::
    WellCurve3DGenerator.generate_curve_mesh``. The result is a polyline ready for
    ``pyqtgraph.opengl.GLLinePlotItem(pos=...)``.

    At each station the offset direction is the horizontal normal to the trajectory
    tangent — i.e. ``(-ty, tx, 0)`` — so the curve always stays in plan view and never
    tips into the vertical. Perfectly vertical wells have no horizontal tangent, so
    they fall back to offsetting along +X.

    Args:
        well_path: ``(N, 3)`` trajectory points in scene XYZ.
        curve_values: ``(N,)`` log values, one per trajectory point.
        scale: Metres of lateral offset per unit of ``curve_values``. Normalize or
            pre-scale the log yourself — this applies no auto-ranging.

    Returns:
        ``(N, 3)`` float32 offset polyline. Empty ``(0, 3)`` for an empty path.

    Raises:
        ValueError: If ``curve_values`` is shorter than ``well_path``.
    """
    well_path = np.asarray(well_path, dtype=np.float32)
    curve_values = np.asarray(curve_values, dtype=np.float32)

    n_pts = len(well_path)
    if n_pts == 0:
        return np.empty((0, 3), dtype=np.float32)
    if len(curve_values) < n_pts:
        raise ValueError(
            f"curve_values has {len(curve_values)} samples but well_path has {n_pts} points"
        )

    # Forward differences, with the last station reusing the previous segment.
    tangents = np.empty_like(well_path)
    tangents[:-1] = well_path[1:] - well_path[:-1]
    tangents[-1] = tangents[-2] if n_pts > 1 else (0.0, 0.0, 1.0)

    # Normalize first so the "is this well vertical?" threshold below is independent
    # of station spacing.
    tangent_norm = np.linalg.norm(tangents, axis=1)
    tangents /= np.where(tangent_norm < 1e-5, 1.0, tangent_norm)[:, None]

    # Horizontal normal: rotate the tangent's XY part by 90°, drop Z.
    perp = np.column_stack(
        [-tangents[:, 1], tangents[:, 0], np.zeros(n_pts, dtype=np.float32)]
    )
    perp_norm = np.linalg.norm(perp, axis=1)
    vertical = perp_norm < 1e-5
    perp[vertical] = (1.0, 0.0, 0.0)
    perp_norm[vertical] = 1.0
    perp /= perp_norm[:, None]

    return (well_path + perp * (curve_values[:n_pts, None] * scale)).astype(np.float32)


def build_synthetic_seismogram_overlay(
    well_path: np.ndarray,
    synthetic_trace: np.ndarray,
    *,
    scale: float = 1.0,
) -> np.ndarray:
    """Build a 3D wiggle-track polyline for a synthetic seismogram beside a well.

    Companion to :func:`offset_curve_along_trajectory` (which renders a log
    curve beside the well). This renders a **synthetic seismogram** as a
    wiggle track: at each trajectory station the trace amplitude deflects the
    point laterally along the trajectory's horizontal normal, producing a
    filled-looking oscillation in plan view. The result is a single polyline
    suitable for ``pyqtgraph.opengl.GLLinePlotItem(pos=...)``.

    The synthetic trace is produced upstream by
    :func:`geoviz_well_tie.synthetic_from_logs` (sonic + density -> Ricker). It
    has one fewer sample than the logs (reflectivity is a first difference),
    so it is linearly resampled to the trajectory station count here.

    Args:
        well_path: ``(N, 3)`` trajectory points in scene XYZ.
        synthetic_trace: ``(M,)`` synthetic amplitudes (``M`` need not equal
            ``N``; it is resampled to ``N``).
        scale: Lateral deflection (scene units) per unit of trace amplitude.
            Synthetic traces are typically ~1e-3 scale; pre-normalize or pick a
            ``scale`` that reads well beside the well.

    Returns:
        ``(N, 3)`` float32 wiggle-track polyline (the deflected stations). Empty
        ``(0, 3)`` for an empty path or trace. NaN/inf amplitudes are clamped to
        zero so they don't blow up the geometry.

    Raises:
        ValueError: If ``well_path`` is not ``(N, 3)``.
    """
    well_path = np.asarray(well_path, dtype=np.float32)
    if well_path.ndim != 2 or well_path.shape[1] != 3:
        raise ValueError(f"well_path must be (N, 3), got {well_path.shape}")
    n_pts = len(well_path)
    if n_pts == 0:
        return np.empty((0, 3), dtype=np.float32)

    trace = np.asarray(synthetic_trace, dtype=np.float32).ravel()
    if trace.size == 0:
        # No trace -> zero deflection -> overlay coincides with the path.
        return well_path.copy()
    # Guard against NaN/inf blowing up the geometry.
    trace = np.where(np.isfinite(trace), trace, 0.0)

    # Resample the trace to the trajectory station count (linear interp).
    if trace.size != n_pts:
        src = np.linspace(0.0, 1.0, trace.size)
        dst = np.linspace(0.0, 1.0, n_pts)
        trace = np.interp(dst, src, trace).astype(np.float32)

    # Reuse the horizontal-normal computation from offset_curve_along_trajectory.
    tangents = np.empty_like(well_path)
    tangents[:-1] = well_path[1:] - well_path[:-1]
    tangents[-1] = tangents[-2] if n_pts > 1 else (0.0, 0.0, 1.0)
    tangent_norm = np.linalg.norm(tangents, axis=1)
    tangents /= np.where(tangent_norm < 1e-5, 1.0, tangent_norm)[:, None]
    perp = np.column_stack(
        [-tangents[:, 1], tangents[:, 0], np.zeros(n_pts, dtype=np.float32)]
    )
    perp_norm = np.linalg.norm(perp, axis=1)
    vertical = perp_norm < 1e-5
    perp[vertical] = (1.0, 0.0, 0.0)
    perp_norm[vertical] = 1.0
    perp /= perp_norm[:, None]

    return (well_path + perp * (trace[:, None] * scale)).astype(np.float32)

