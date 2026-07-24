"""Fence section model and shared amplitude strip extraction (#60–#61)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

import numpy as np

from .volume_access import VolumeAccess


@dataclass
class FenceSection:
    """Named polyline fence in survey XY (metres)."""

    name: str
    vertices_xy: np.ndarray  # (N, 2)
    visible: bool = True
    id: str = field(default_factory=lambda: uuid4().hex[:12])

    def __post_init__(self) -> None:
        self.vertices_xy = np.asarray(self.vertices_xy, dtype=np.float64).reshape(-1, 2)
        if len(self.vertices_xy) < 2:
            raise ValueError("fence needs at least 2 vertices")


@dataclass(frozen=True)
class FenceExtraction:
    """One amplitude strip shared by 3D curtain and 2D VD."""

    fence_id: str
    amplitude: np.ndarray  # (n_along, n_sample)
    arc_length_m: np.ndarray  # (n_along,)
    sample_axis: np.ndarray  # (n_sample,) vertical values in active domain units


def extract_fence_strip(
    volume: np.ndarray | VolumeAccess,
    *,
    fence: FenceSection,
    xy_to_il_xl,
    iline_start: float,
    iline_step: float,
    xline_start: float,
    xline_step: float,
    n_along: int = 128,
    sample_axis: np.ndarray | None = None,
) -> FenceExtraction:
    """Sample volume along fence polyline; single result for 3D+2D consumers."""
    if hasattr(volume, "data"):
        data = np.asarray(volume.data)
    else:
        data = np.asarray(volume)
    if data.ndim != 3:
        raise ValueError("volume must be 3-D")
    ni, nx, nt = data.shape
    verts = fence.vertices_xy
    # Arc-length parameterization
    seg = np.diff(verts, axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    total = float(seg_len.sum()) or 1.0
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    targets = np.linspace(0.0, total, n_along)
    samples_xy = np.zeros((n_along, 2), dtype=np.float64)
    for i, t in enumerate(targets):
        j = int(np.searchsorted(cum, t, side="right") - 1)
        j = max(0, min(j, len(seg_len) - 1))
        local = (t - cum[j]) / (seg_len[j] if seg_len[j] > 1e-12 else 1.0)
        samples_xy[i] = verts[j] + local * (verts[j + 1] - verts[j])

    amp = np.zeros((n_along, nt), dtype=np.float32)
    for i, (x, y) in enumerate(samples_xy):
        il, xl = xy_to_il_xl(float(x), float(y))
        ii = int(round((il - iline_start) / (iline_step or 1)))
        xi = int(round((xl - xline_start) / (xline_step or 1)))
        ii = max(0, min(ni - 1, ii))
        xi = max(0, min(nx - 1, xi))
        amp[i, :] = data[ii, xi, :]

    if sample_axis is None:
        sample_axis = np.arange(nt, dtype=np.float64)
    return FenceExtraction(
        fence_id=fence.id,
        amplitude=amp,
        arc_length_m=targets.astype(np.float64),
        sample_axis=np.asarray(sample_axis, dtype=np.float64),
    )


def well_to_well_path(well_xy: list[tuple[float, float]]) -> np.ndarray:
    """Polyline through well surface positions."""
    if len(well_xy) < 2:
        raise ValueError("need at least two wells")
    return np.asarray(well_xy, dtype=np.float64).reshape(-1, 2)
