"""Injectable Min-Max LOD downsampling for curve rendering.

Default provider is the engine's NumPy implementation. Host applications
(e.g. paleo_workbench) may inject a C++-accelerated provider at startup via
``set_downsample_provider`` — the engine itself has no such dependency.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

DownsampleFn = Callable[
    [list[float], list[float], int], tuple[list[float], list[float]]
]


def numpy_minmax_downsample(
    depths: list[float], values: list[float], pixel_height: int
) -> tuple[list[float], list[float]]:
    """Min-max 2-points-per-bin downsampling (engine default)."""
    if len(depths) <= pixel_height * 2:
        return depths, values
    arr_v = np.array(values)
    step = max(1, len(arr_v) // pixel_height)
    result_d: list[float] = []
    result_v: list[float] = []
    for i in range(0, len(arr_v), step):
        chunk = arr_v[i:i + step]
        max_idx = i + int(np.argmax(chunk))
        min_idx = i + int(np.argmin(chunk))
        # Emit in depth order to avoid zigzag artifacts
        if max_idx <= min_idx:
            result_d.append(depths[max_idx])
            result_v.append(values[max_idx])
            result_d.append(depths[min_idx])
            result_v.append(values[min_idx])
        else:
            result_d.append(depths[min_idx])
            result_v.append(values[min_idx])
            result_d.append(depths[max_idx])
            result_v.append(values[max_idx])
    return result_d, result_v


_provider: DownsampleFn = numpy_minmax_downsample


def get_downsample_provider() -> DownsampleFn:
    return _provider


def set_downsample_provider(fn: DownsampleFn | None) -> None:
    """Install a custom downsample provider; ``None`` restores the default."""
    global _provider
    _provider = fn if fn is not None else numpy_minmax_downsample
