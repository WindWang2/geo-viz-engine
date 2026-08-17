"""Horizon file parsing, interpolation (nearest / RBF), and attribute extraction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict

import numpy as np
from scipy.ndimage import distance_transform_edt

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


def horizon_quad_faces(nI: int, nX: int) -> np.ndarray:
    """Triangle faces for an nI×nX regular grid, two tris per quad.

    Winding matches the historical nested-append path: (p0, p1, p2) and
    (p1, p3, p2) with p0=i*nX+j, p1=p0+1, p2=p0+nX, p3=p2+1.
    """
    if nI < 2 or nX < 2:
        return np.empty((0, 3), dtype=np.int64)
    i_idx, j_idx = np.mgrid[0:nI - 1, 0:nX - 1]
    p0 = i_idx * nX + j_idx
    p1 = p0 + 1
    p2 = p0 + nX
    p3 = p2 + 1
    return np.stack([p0, p1, p2, p1, p3, p2], axis=-1).reshape(-1, 3)


class HorizonAxes(TypedDict):
    """Axes definition expected by :meth:`HorizonParser.parse`.

    Attributes:
        ilines: 1-D array of inline numbers.
        xlines: 1-D array of crossline numbers.
        nI: Number of inlines (``len(ilines)``).
        nX: Number of crosslines (``len(xlines)``).
    """

    ilines: np.ndarray
    xlines: np.ndarray
    nI: int
    nX: int


class HorizonParser:
    """Parse tab-separated horizon files (inline, crossline, time/depth).

    Args:
        path: Path to horizon file.
        unit: Depth/time unit (``"ms"``, ``"m"``, ``"ft"``).
        scale: Multiplier applied to the third column.
        iline_offset: Offset added to inline numbers before matching.
        xline_offset: Offset added to crossline numbers before matching.
    """

    def __init__(self, path: str, unit: str = "ms", scale: float = 1.0,
                 iline_offset: int = 0, xline_offset: int = 0):
        self._path = path
        self._unit = unit
        self._scale = scale
        self._il_offset = iline_offset
        self._xl_offset = xline_offset

    def parse(self, axes: HorizonAxes) -> np.ndarray:
        """Parse the horizon file into a 2-D grid with NaN gaps.

        Args:
            axes: Inline/crossline axes definition (see :class:`HorizonAxes`).

        Returns:
            ``(nI, nX)`` float64 array with ``NaN`` where no data matches.
        """
        points = self._read_points()
        if not points:
            raise ValueError(
                f"No valid data points found in {self._path}. "
                f"Expected format: inline crossline time_ms (tab-separated). "
                f"Each line should have at least 3 numeric columns."
            )
        ilines = axes["ilines"]
        xlines = axes["xlines"]
        nI, nX = axes["nI"], axes["nX"]
        il_to_i = {int(v): i for i, v in enumerate(ilines)}
        xl_to_j = {int(v): j for j, v in enumerate(xlines)}

        matched = 0
        grid = np.full((nI, nX), np.nan, dtype=np.float64)
        for (il, xl), val in points.items():
            il_adj = il + self._il_offset
            xl_adj = xl + self._xl_offset
            i = il_to_i.get(il_adj)
            j = xl_to_j.get(xl_adj)
            if i is not None and j is not None:
                grid[i, j] = val
                matched += 1
        if matched == 0:
            import logging
            logging.getLogger(__name__).warning(
                "Horizon file %s: %d points read but 0 matched axes "
                "(ilines %d-%d, xlines %d-%d). Check inline/xline numbering.",
                self._path, len(points),
                int(ilines[0]), int(ilines[-1]),
                int(xlines[0]), int(xlines[-1]),
            )
        return grid

    def fill_nearest(self, grid: np.ndarray, max_dist: float = 0) -> np.ndarray:
        """Fill NaN gaps using nearest-neighbour interpolation.

        Args:
            grid: ``(nI, nX)`` array with NaN gaps.
            max_dist: Maximum pixel distance to fill. ``0`` means unlimited.

        Returns:
            Filled copy of *grid*.
        """
        mask = np.isfinite(grid)
        if mask.all():
            return grid.copy()
        dist, indices = distance_transform_edt(~mask, return_indices=True)
        filled = grid[indices[0], indices[1]]
        if max_dist > 0:
            filled[dist > max_dist] = np.nan
        return filled

    def fill_rbf(self, grid: np.ndarray, max_dist: float = 0,
                 neighbors: int = 24, smoothing: float = 0.0) -> np.ndarray:
        """Fill NaN gaps using RBF (radial basis function) interpolation.

        Args:
            grid: ``(nI, nX)`` array with NaN gaps.
            max_dist: Maximum pixel distance to fill. ``0`` means unlimited.
            neighbors: Number of nearest neighbours for RBF fitting.
            smoothing: Smoothing factor (0 = exact interpolation).

        Returns:
            Interpolated copy of *grid*.
        """
        from scipy.interpolate import RBFInterpolator
        mask = np.isfinite(grid)
        if mask.all():
            return grid.copy()
        ys, xs = np.where(mask)
        vals = grid[mask]
        target_ys, target_xs = np.where(~mask)
        if len(ys) == 0:
            return grid.copy()
        interp = RBFInterpolator(
            np.column_stack([ys, xs]), vals,
            kernel="linear", degree=0,
            neighbors=min(neighbors, len(ys)),
            smoothing=smoothing,
        )
        result = grid.copy()
        if len(target_ys) > 0:
            result[target_ys, target_xs] = interp(np.column_stack([target_ys, target_xs]))
        if max_dist > 0:
            # EDT measures distance from *zero* pixels, so (like fill_nearest)
            # transform the invalid-pixel mask — dist is then the distance of
            # each gap pixel to the nearest valid sample.
            dist = distance_transform_edt(~mask)
            result[(~mask) & (dist > max_dist)] = np.nan
        return result

    def _read_points(self) -> dict[tuple[int, int], float]:
        points: dict[tuple[int, int], float] = {}
        text = Path(self._path).read_text(encoding="utf-8", errors="replace")
        for line in text.strip().splitlines():
            nums = _NUM_RE.findall(line)
            if len(nums) < 3:
                continue
            il = int(float(nums[0]))
            xl = int(float(nums[1]))
            val = float(nums[2]) * self._scale
            points[(il, xl)] = val
        return points


def extract_along_horizon(
    volume: np.ndarray,
    grid: np.ndarray,
    dt_ms: float,
    t0_ms: float = 0.0,
    window: int = 0,
) -> np.ndarray:
    """Extract seismic amplitudes along a horizon surface.

    For each ``(il, xl)`` position in *grid*, the TWT value is converted
    to a sample index and the corresponding sample is read from *volume*.

    Args:
        volume: Seismic volume with shape ``(nI, nX, nS)`` (inline, crossline,
            sample) and float32 dtype.
        grid: Horizon grid ``(nI, nX)`` in milliseconds (from
            :meth:`HorizonParser.parse`). NaN marks absent picks.
        dt_ms: Sample interval in milliseconds.
        t0_ms: Time of first sample in milliseconds.
        window: Half-window in samples. ``0`` extracts a single sample per
            trace; ``N > 0`` extracts ``2N + 1`` samples centred on the
            horizon, and the result is the RMS over the window.

    Returns:
        ``(nI, nX)`` float32 attribute map. NaN where *grid* is NaN or the
        extraction window extends outside the volume.
    """
    nI, nX, nS = volume.shape
    result = np.full((nI, nX), np.nan, dtype=np.float32)
    valid = np.isfinite(grid)
    if not valid.any():
        return result

    sample_idx = np.where(valid, (grid - t0_ms) / dt_ms, 0).astype(np.int32)
    sample_idx = np.clip(sample_idx, 0, nS - 1)

    if window <= 0:
        result[valid] = np.take_along_axis(
            volume.reshape(nI * nX, nS),
            sample_idx.reshape(nI * nX, 1),
            axis=1,
        ).reshape(nI, nX)[valid]
    else:
        half = window
        extracted = np.full((nI, nX, 2 * half + 1), np.nan, dtype=np.float32)
        for k, offset in enumerate(range(-half, half + 1)):
            idx = sample_idx + offset
            in_bounds = valid & (idx >= 0) & (idx < nS)
            idx_safe = np.clip(idx, 0, nS - 1)
            vals = np.take_along_axis(
                volume.reshape(nI * nX, nS),
                idx_safe.reshape(nI * nX, 1),
                axis=1,
            ).reshape(nI, nX)
            extracted[in_bounds, k] = vals[in_bounds]
        mean_sq = np.nanmean(extracted ** 2, axis=2)
        result = np.sqrt(np.maximum(mean_sq, 0)).astype(np.float32)
        all_nan = np.all(np.isnan(extracted), axis=2)
    return result


class HorizonROIPatch:
    """Stores a region-of-interest (ROI) patch of a horizon grid for undo/redo."""

    def __init__(self, grid: np.ndarray, roi: tuple[int, int, int, int]):
        min_i, max_i, min_j, max_j = roi
        self.roi = roi
        self.before_values = grid[min_i:max_i, min_j:max_j].copy()
        self.after_values: np.ndarray | None = None

    def capture_after(self, grid: np.ndarray):
        min_i, max_i, min_j, max_j = self.roi
        self.after_values = grid[min_i:max_i, min_j:max_j].copy()

    def undo(self, grid: np.ndarray):
        min_i, max_i, min_j, max_j = self.roi
        grid[min_i:max_i, min_j:max_j] = self.before_values

    def redo(self, grid: np.ndarray):
        if self.after_values is not None:
            min_i, max_i, min_j, max_j = self.roi
            grid[min_i:max_i, min_j:max_j] = self.after_values


def unproject_ray(
    win_pos: tuple[float, float],
    viewport_rect: tuple[float, float, float, float],
    inv_mvp: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Unproject viewport pixel coordinates to a 3D ray (origin, direction)."""
    wx, wy = win_pos
    vx, vy, vw, vh = viewport_rect

    ndc_x = (2.0 * (wx - vx) / max(vw, 1.0)) - 1.0
    ndc_y = 1.0 - (2.0 * (wy - vy) / max(vh, 1.0))

    near_ndc = np.array([ndc_x, ndc_y, -1.0, 1.0], dtype=np.float32)
    far_ndc = np.array([ndc_x, ndc_y, 1.0, 1.0], dtype=np.float32)

    near_world = inv_mvp @ near_ndc
    far_world = inv_mvp @ far_ndc

    if near_world[3] != 0:
        near_world /= near_world[3]
    if far_world[3] != 0:
        far_world /= far_world[3]

    origin = near_world[:3]
    direction = far_world[:3] - origin
    norm = np.linalg.norm(direction)
    if norm > 0:
        direction /= norm
    else:
        direction = np.array([0.0, 0.0, 1.0], dtype=np.float32)

    return origin.astype(np.float32), direction.astype(np.float32)


def intersect_ray_grid(
    ray_origin: np.ndarray,
    ray_dir: np.ndarray,
    grid_z: np.ndarray,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    steps: int = 100,
) -> tuple[float, float, float] | None:
    """Find intersection point (X, Y, Z) of a 3D ray with a grid heightmap."""
    nI, nX = grid_z.shape
    x0, x1 = x_range
    y0, y1 = y_range

    dx = max(1e-6, x1 - x0)
    dy = max(1e-6, y1 - y0)

    z_min = float(np.nanmin(grid_z)) if np.isfinite(grid_z).any() else 0.0
    z_max = float(np.nanmax(grid_z)) if np.isfinite(grid_z).any() else 1000.0

    # Ray marching sample points
    t_vals = np.linspace(0.0, 5000.0, steps)
    for t in t_vals:
        pos = ray_origin + t * ray_dir
        px, py, pz = pos[0], pos[1], pos[2]

        if x0 <= px <= x1 and y0 <= py <= y1:
            i = int(np.clip((py - y0) / dy * (nI - 1), 0, nI - 1))
            j = int(np.clip((px - x0) / dx * (nX - 1), 0, nX - 1))
            gz = grid_z[i, j]
            if np.isfinite(gz) and abs(pz - gz) < max(5.0, (z_max - z_min) * 0.05):
                return float(px), float(py), float(gz)

    return None


def apply_gaussian_sculpt(
    grid_z: np.ndarray,
    center_xy: tuple[float, float],
    radius: float,
    strength: float,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
) -> tuple[np.ndarray, tuple[int, int, int, int]]:
    """Apply 2D Gaussian elevation delta to grid_z in-place and return ROI bounds."""
    nI, nX = grid_z.shape
    x0, x1 = x_range
    y0, y1 = y_range

    dx = max(1e-6, x1 - x0)
    dy = max(1e-6, y1 - y0)

    cx, cy = center_xy
    sigma = max(radius / 3.0, 1e-3)

    # Convert center to grid coordinates
    ci = (cy - y0) / dy * (nI - 1)
    cj = (cx - x0) / dx * (nX - 1)

    r_grid_i = int(np.ceil((radius / dy) * (nI - 1)))
    r_grid_j = int(np.ceil((radius / dx) * (nX - 1)))


    min_i = max(0, int(np.floor(ci - r_grid_i)))
    max_i = min(nI, int(np.ceil(ci + r_grid_i + 1)))
    min_j = max(0, int(np.floor(cj - r_grid_j)))
    max_j = min(nX, int(np.ceil(cj + r_grid_j + 1)))

    if min_i >= max_i or min_j >= max_j:
        return grid_z, (0, 0, 0, 0)

    # Grid cell coordinates in world space
    xs = np.linspace(x0, x1, nX)[min_j:max_j]
    ys = np.linspace(y0, y1, nI)[min_i:max_i]
    grid_x, grid_y = np.meshgrid(xs, ys)

    dist_sq = (grid_x - cx) ** 2 + (grid_y - cy) ** 2
    delta = strength * np.exp(-dist_sq / (2.0 * sigma ** 2))

    roi = grid_z[min_i:max_i, min_j:max_j]
    valid_mask = np.isfinite(roi)
    roi[valid_mask] += delta[valid_mask]

    return grid_z, (min_i, max_i, min_j, max_j)

