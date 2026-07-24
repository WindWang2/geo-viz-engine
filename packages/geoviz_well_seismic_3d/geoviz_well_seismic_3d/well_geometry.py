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
