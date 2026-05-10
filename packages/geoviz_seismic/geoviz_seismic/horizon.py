from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt

_NUM_RE = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")


class HorizonParser:
    def __init__(self, path: str, unit: str = "ms", scale: float = 1.0,
                 iline_offset: int = 0, xline_offset: int = 0):
        self._path = path
        self._unit = unit
        self._scale = scale
        self._il_offset = iline_offset
        self._xl_offset = xline_offset

    def parse(self, axes: dict) -> np.ndarray:
        points = self._read_points()
        if not points:
            raise ValueError(
                f"No valid data points found in {self._path}. "
                f"Expected format: inline crossline time_ms (tab-separated). "
                f"Each line should have exactly 3 numeric columns."
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
            dist = distance_transform_edt(mask)
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
            val = float(nums[-1]) * self._scale
            points[(il, xl)] = val
        return points
