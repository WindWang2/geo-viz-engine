"""Color-scale primitives shared by joint 2D and 3D renderers."""

from __future__ import annotations

import numpy as np

SEISMIC_COLOR_SCALES: dict[str, tuple[tuple[int, int, int], ...]] = {
    "blue-white-red": ((33, 102, 172), (255, 255, 255), (178, 24, 43)),
    "gray": ((0, 0, 0), (128, 128, 128), (255, 255, 255)),
    "red-white-blue": ((178, 24, 43), (255, 255, 255), (33, 102, 172)),
}

GR_COLOR_SCALES: dict[str, tuple[tuple[int, int, int], ...]] = {
    "viridis": (
        (68, 1, 84),
        (59, 82, 139),
        (33, 145, 140),
        (94, 201, 98),
        (253, 231, 37),
    ),
    "cividis": (
        (0, 34, 78),
        (66, 64, 134),
        (122, 123, 120),
        (188, 174, 108),
        (254, 232, 56),
    ),
    "plasma": (
        (13, 8, 135),
        (126, 3, 168),
        (204, 71, 120),
        (248, 148, 65),
        (240, 249, 33),
    ),
    "turbo": (
        (48, 18, 59),
        (70, 107, 227),
        (26, 228, 182),
        (249, 231, 33),
        (234, 42, 20),
    ),
}

MISSING_GR_RGBA = (115, 115, 115, 255)


def colorize_amplitude(
    amplitude: np.ndarray,
    *,
    color_scale: str = "blue-white-red",
) -> np.ndarray:
    """Map amplitude to zero-centred RGBA using a robust symmetric range."""
    values = np.asarray(amplitude, dtype=np.float32)
    finite = np.abs(values[np.isfinite(values)])
    limit = float(np.nanpercentile(finite, 98.0)) if finite.size else 1.0
    if not np.isfinite(limit) or limit <= 1e-12:
        limit = 1.0
    normalized = np.clip(values / limit, -1.0, 1.0)
    stops = np.asarray(
        SEISMIC_COLOR_SCALES.get(
            color_scale, SEISMIC_COLOR_SCALES["blue-white-red"]
        ),
        dtype=np.float32,
    )
    rgb = np.empty(values.shape + (3,), dtype=np.float32)
    negative = normalized <= 0.0
    t_negative = np.clip(normalized + 1.0, 0.0, 1.0)[..., None]
    t_positive = np.clip(normalized, 0.0, 1.0)[..., None]
    rgb[negative] = (
        stops[0] + t_negative[negative] * (stops[1] - stops[0])
    )
    rgb[~negative] = (
        stops[1] + t_positive[~negative] * (stops[2] - stops[1])
    )
    rgba = np.empty(values.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = np.rint(rgb).astype(np.uint8)
    rgba[..., 3] = 255
    rgba[~np.isfinite(values), :3] = 128
    return rgba


def colorize_gr(
    values: np.ndarray,
    *,
    value_range: tuple[float, float],
    color_scale: str = "viridis",
) -> np.ndarray:
    """Map GR values to sequential RGBA; missing samples remain neutral gray."""
    samples = np.asarray(values, dtype=np.float64)
    lo, hi = (float(value_range[0]), float(value_range[1]))
    if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
        lo, hi = 0.0, 1.0
    normalized = np.clip((samples - lo) / (hi - lo), 0.0, 1.0)
    normalized = np.where(np.isfinite(normalized), normalized, 0.0)
    stops = np.asarray(
        GR_COLOR_SCALES.get(color_scale, GR_COLOR_SCALES["viridis"]),
        dtype=np.float64,
    )
    position = normalized * (len(stops) - 1)
    left = np.floor(position).astype(np.int64)
    right = np.minimum(left + 1, len(stops) - 1)
    fraction = (position - left)[..., None]
    rgb = stops[left] + fraction * (stops[right] - stops[left])
    rgba = np.empty(samples.shape + (4,), dtype=np.uint8)
    rgba[..., :3] = np.rint(rgb).astype(np.uint8)
    rgba[..., 3] = 255
    rgba[~np.isfinite(samples)] = MISSING_GR_RGBA
    return rgba
