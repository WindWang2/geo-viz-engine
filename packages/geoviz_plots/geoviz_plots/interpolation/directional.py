"""Directional distance and bounded-memory weighted trend interpolation."""

from __future__ import annotations

import math

import numpy as np

_DEFAULT_A = 1.0
_DEFAULT_B = 0.4
_EPS = 1e-15
_DEFAULT_MAX_CELLS_PER_CHUNK = 16_384


def azimuth_to_rad(azimuth_deg: float) -> float:
    return math.radians(float(azimuth_deg) % 360.0)


def rotate_to_uv(
    dx: np.ndarray,
    dy: np.ndarray,
    *,
    azimuth_deg: float,
) -> tuple[np.ndarray, np.ndarray]:
    theta = azimuth_to_rad(azimuth_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    return dx * sin_t + dy * cos_t, dx * cos_t - dy * sin_t


def _positive_axis(value: float, name: str) -> float:
    axis = float(value)
    if not math.isfinite(axis) or axis <= 0.0:
        raise ValueError(f"{name} must be a finite positive value")
    return axis


def directional_distance(
    u: np.ndarray,
    v: np.ndarray,
    *,
    a: float,
    b: float,
) -> np.ndarray:
    aa = _positive_axis(a, "a")
    bb = _positive_axis(b, "b")
    return np.hypot(np.asarray(u, dtype=np.float64) / aa, np.asarray(v, dtype=np.float64) / bb)


def directional_weights(
    distance: np.ndarray,
    *,
    q: np.ndarray | float = 1.0,
    b_i: np.ndarray | float = 1.0,
) -> np.ndarray:
    weights = (
        np.exp(-(np.asarray(distance, dtype=np.float64) ** 2))
        * np.asarray(q, dtype=np.float64)
        * np.asarray(b_i, dtype=np.float64)
    )
    return np.maximum(np.where(np.isfinite(weights), weights, 0.0), 0.0)


def _sample_arrays(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    q: np.ndarray | None,
    b_i: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    xs = np.asarray(xs, dtype=np.float64).reshape(-1)
    ys = np.asarray(ys, dtype=np.float64).reshape(-1)
    zs = np.asarray(zs, dtype=np.float64).reshape(-1)
    if not (len(xs) == len(ys) == len(zs)):
        raise ValueError("xs, ys and zs must have equal lengths")
    q_arr = np.ones(len(zs), dtype=np.float64) if q is None else np.asarray(q, dtype=np.float64).reshape(-1)
    b_arr = np.ones(len(zs), dtype=np.float64) if b_i is None else np.asarray(b_i, dtype=np.float64).reshape(-1)
    if len(q_arr) != len(zs) or len(b_arr) != len(zs):
        raise ValueError("q and b_i must match sample count")
    finite = np.isfinite(xs) & np.isfinite(ys) & np.isfinite(zs)
    return xs[finite], ys[finite], zs[finite], q_arr[finite], b_arr[finite]


def trend_value_at(
    x0: float,
    y0: float,
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    *,
    azimuth_deg: float = 0.0,
    a: float = _DEFAULT_A,
    b: float = _DEFAULT_B,
    q: np.ndarray | None = None,
    b_i: np.ndarray | None = None,
) -> float:
    xs, ys, zs, q_arr, b_arr = _sample_arrays(xs, ys, zs, q, b_i)
    if len(zs) == 0:
        return float("nan")
    u, v = rotate_to_uv(xs - float(x0), ys - float(y0), azimuth_deg=azimuth_deg)
    distance = directional_distance(u, v, a=a, b=b)
    weights = directional_weights(distance, q=q_arr, b_i=b_arr)
    total = float(np.sum(weights))
    if total <= _EPS:
        return float(zs[int(np.argmin(distance))])
    return float(np.sum(weights * zs) / total)


def directional_trend_grid(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    grid_x: np.ndarray,
    grid_y: np.ndarray,
    *,
    azimuth_deg: float = 0.0,
    a: float = _DEFAULT_A,
    b: float = _DEFAULT_B,
    q: np.ndarray | None = None,
    b_i: np.ndarray | None = None,
    max_cells_per_chunk: int = _DEFAULT_MAX_CELLS_PER_CHUNK,
    cancellation_token=None,
) -> np.ndarray:
    """Evaluate a trend grid without allocating an entire ``H×W×N`` cube."""
    xs, ys, zs, q_arr, b_arr = _sample_arrays(xs, ys, zs, q, b_i)
    grid_x = np.asarray(grid_x, dtype=np.float64).reshape(-1)
    grid_y = np.asarray(grid_y, dtype=np.float64).reshape(-1)
    _positive_axis(a, "a")
    _positive_axis(b, "b")
    chunk_size = int(max_cells_per_chunk)
    if chunk_size <= 0:
        raise ValueError("max_cells_per_chunk must be positive")
    height, width = len(grid_y), len(grid_x)
    if len(zs) == 0 or height == 0 or width == 0:
        return np.full((height, width), np.nan)

    cell_x = np.tile(grid_x, height)
    cell_y = np.repeat(grid_y, width)
    out = np.full(cell_x.shape, np.nan, dtype=np.float64)
    for start in range(0, len(cell_x), chunk_size):
        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()
        stop = min(start + chunk_size, len(cell_x))
        dx = cell_x[start:stop, None] - xs[None, :]
        dy = cell_y[start:stop, None] - ys[None, :]
        u, v = rotate_to_uv(dx, dy, azimuth_deg=azimuth_deg)
        distance = directional_distance(u, v, a=a, b=b)
        weights = directional_weights(distance, q=q_arr, b_i=b_arr)
        totals = np.sum(weights, axis=1)
        valid = totals > _EPS
        values = np.full(stop - start, np.nan, dtype=np.float64)
        values[valid] = np.sum(weights[valid] * zs, axis=1) / totals[valid]
        if np.any(~valid):
            nearest = np.argmin(distance[~valid], axis=1)
            values[~valid] = zs[nearest]
        out[start:stop] = values
    return out.reshape(height, width)
