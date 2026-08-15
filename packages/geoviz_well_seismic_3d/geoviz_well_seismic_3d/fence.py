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


def sample_fence_polyline(vertices_xy, n_along: int) -> np.ndarray:
    """Equal arc-length resample of a fence polyline (#51).

    Returns ``(n_along, 2)`` XY positions at uniform cumulative distance along
    the polyline. Shared by the 3D curtain (``joint_widget._curtain_mesh``)
    and ``extract_fence_strip`` so the along-fence index always means the same
    thing — never vertex-index fractions, which misalign on unequal-length
    segments.
    """
    verts = np.asarray(vertices_xy, dtype=np.float64).reshape(-1, 2)
    seg = np.diff(verts, axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    total = float(seg_len.sum()) or 1.0
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    targets = np.linspace(0.0, total, n_along)
    samples = np.zeros((n_along, 2), dtype=np.float64)
    for i, t in enumerate(targets):
        j = int(np.searchsorted(cum, t, side="right") - 1)
        j = max(0, min(j, len(seg_len) - 1))
        local = (t - cum[j]) / (seg_len[j] if seg_len[j] > 1e-12 else 1.0)
        samples[i] = verts[j] + local * (verts[j + 1] - verts[j])
    return samples


def extract_fence_strip(
    volume: np.ndarray | VolumeAccess,
    *,
    fence: FenceSection,
    xy_to_il_xl=None,
    iline_start: float = 0.0,
    iline_step: float = 1.0,
    xline_start: float = 0.0,
    xline_step: float = 1.0,
    n_along: int = 128,
    sample_axis: np.ndarray | None = None,
    registration=None,
) -> FenceExtraction:
    """Sample volume along fence polyline; single result for 3D+2D consumers.

    Prefer ``registration`` (VolumeRegistration) when the cube is a preview so
    indices scale to the loaded shape. Legacy il/xl params remain for tests.

    Supports dense ndarray, objects with ``.data``, and source-backed
    :class:`VolumeAccess` (``shape`` + slice/sample methods) without forcing a
    full-cube materialisation.
    """
    dense = None
    if hasattr(volume, "data") and getattr(volume, "data") is not None:
        dense = np.asarray(volume.data)
        if dense.ndim != 3:
            dense = None
    elif isinstance(volume, np.ndarray):
        dense = np.asarray(volume)
        if dense.ndim != 3:
            raise ValueError("volume must be 3-D")

    if dense is not None:
        ni, nx, nt = (int(x) for x in dense.shape)
    else:
        shape = getattr(volume, "shape", None)
        if shape is None or len(shape) != 3:
            raise ValueError("volume must be 3-D or VolumeAccess with shape")
        ni, nx, nt = (int(x) for x in shape)

    verts = fence.vertices_xy
    seg = np.diff(verts, axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    total = float(seg_len.sum()) or 1.0
    targets = np.linspace(0.0, total, n_along)
    samples_xy = sample_fence_polyline(verts, n_along)

    amp = np.zeros((n_along, nt), dtype=np.float32)
    sample_trace = getattr(volume, "sample_trace", None)
    for i, (x, y) in enumerate(samples_xy):
        if registration is not None:
            vi, vx = registration.xy_to_volume_idx(float(x), float(y))
            ii = int(max(0, min(ni - 1, round(vi))))
            xi = int(max(0, min(nx - 1, round(vx))))
        else:
            il, xl = xy_to_il_xl(float(x), float(y))
            ii = int(round((il - iline_start) / (iline_step or 1)))
            xi = int(round((xl - xline_start) / (xline_step or 1)))
            ii = max(0, min(ni - 1, ii))
            xi = max(0, min(nx - 1, xi))
        if dense is not None:
            amp[i, :] = dense[ii, xi, :]
        elif callable(sample_trace):
            amp[i, :] = np.asarray(sample_trace(ii, xi), dtype=np.float32)
        else:
            # VolumeAccess without sample_trace: one inline read per column.
            line = np.asarray(volume.slice_inline(ii), dtype=np.float32)
            amp[i, :] = line[min(xi, line.shape[0] - 1), :]

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
