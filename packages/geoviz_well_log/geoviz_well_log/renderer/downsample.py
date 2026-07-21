"""Injectable Min-Max LOD downsampling for curve rendering.

Provider protocol (ndarray in, ndarray out):
``provider(depths: np.ndarray, values: np.ndarray, pixel_height: int)``
-> ``(np.ndarray, np.ndarray)``.

Default provider is the engine's NumPy implementation. Host applications
(e.g. paleo_workbench) may inject a C++-accelerated provider at startup via
``set_downsample_provider`` — the engine itself has no such dependency.
"""
from __future__ import annotations

from typing import Callable

import numpy as np

DownsampleFn = Callable[
    [np.ndarray, np.ndarray, int], tuple[np.ndarray, np.ndarray]
]


def numpy_minmax_downsample(
    depths: np.ndarray, values: np.ndarray, pixel_height: int
) -> tuple[np.ndarray, np.ndarray]:
    """Min-max 2-points-per-bin downsampling (engine default, ndarray-native).

    Semantics are identical to the legacy list-based implementation:
    bins of ``step = len // pixel_height`` (last bin may be partial), each
    bin emits its min and max in index (depth) order.
    """
    depths = np.asarray(depths, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    n = len(depths)
    if n <= pixel_height * 2:
        return depths, values
    step = max(1, n // pixel_height)
    out_d: list[float] = []
    out_v: list[float] = []
    for i in range(0, n, step):
        chunk = values[i:i + step]
        max_idx = i + int(np.argmax(chunk))
        min_idx = i + int(np.argmin(chunk))
        lo, hi = (max_idx, min_idx) if max_idx < min_idx else (min_idx, max_idx)
        # Emit in index (depth) order to avoid zigzag artifacts
        out_d.append(depths[lo])
        out_v.append(values[lo])
        out_d.append(depths[hi])
        out_v.append(values[hi])
    return np.asarray(out_d, dtype=np.float64), np.asarray(out_v, dtype=np.float64)


_provider: DownsampleFn = numpy_minmax_downsample


def get_downsample_provider() -> DownsampleFn:
    return _provider


def set_downsample_provider(fn: DownsampleFn | None) -> None:
    """Install a custom downsample provider; ``None`` restores the default."""
    global _provider
    _provider = fn if fn is not None else numpy_minmax_downsample
