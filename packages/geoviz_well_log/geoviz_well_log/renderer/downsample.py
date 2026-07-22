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

    Vectorised: the per-bin ``argmin``/``argmax`` scan is done across a
    reshaped ``(n_bins, step)`` view in two vectorised passes instead of a
    Python ``for`` loop — the loop was the classic fallback-path bottleneck
    when the C++ provider is unavailable.
    """
    depths = np.asarray(depths, dtype=np.float64)
    values = np.asarray(values, dtype=np.float64)
    n = len(depths)
    if n <= pixel_height * 2:
        return depths, values
    step = max(1, n // pixel_height)
    n_full_bins = n // step
    # Handle the full bins vectorised; the trailing partial bin (if any) is
    # handled separately to avoid ragged-array reshape.
    full_count = n_full_bins * step
    v_trunc = values[:full_count].reshape(n_full_bins, step)

    # Per-bin argmin/argmax -> column index within each row.
    col_max = np.argmax(v_trunc, axis=1)
    col_min = np.argmin(v_trunc, axis=1)
    row_offsets = np.arange(n_full_bins) * step
    global_max = row_offsets + col_max
    global_min = row_offsets + col_min

    # Emit min then max, in index order within each bin (avoid zigzag).
    # When min_idx < max_idx: emit [min, max]; else [max, min].
    min_first = global_min <= global_max
    first = np.where(min_first, global_min, global_max)
    second = np.where(min_first, global_max, global_min)
    out_idx = np.empty(n_full_bins * 2, dtype=np.intp)
    out_idx[0::2] = first
    out_idx[1::2] = second

    # Trailing partial bin (n not divisible by step).
    if full_count < n:
        chunk = values[full_count:]
        mx = full_count + int(np.argmax(chunk))
        mn = full_count + int(np.argmin(chunk))
        lo, hi = (mn, mx) if mn <= mx else (mx, mn)
        out_idx = np.concatenate([out_idx, [lo, hi]])

    return depths[out_idx], values[out_idx]


_provider: DownsampleFn = numpy_minmax_downsample


def get_downsample_provider() -> DownsampleFn:
    return _provider


def set_downsample_provider(fn: DownsampleFn | None) -> None:
    """Install a custom downsample provider; ``None`` restores the default."""
    global _provider
    _provider = fn if fn is not None else numpy_minmax_downsample
