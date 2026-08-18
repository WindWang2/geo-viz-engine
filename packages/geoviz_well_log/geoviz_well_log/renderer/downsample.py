"""Injectable Min-Max LOD downsampling for curve rendering.

Provider protocol (ndarray in, ndarray out):
``provider(depths: np.ndarray, values: np.ndarray, pixel_height: int)``
-> ``(np.ndarray, np.ndarray)``.

Default provider is the engine's NumPy implementation. Host applications
(e.g. paleo_workbench) may inject a C++-accelerated provider at startup via
``set_downsample_provider`` — the engine itself has no such dependency.

Contract (the engine default is the reference — injected providers MUST
match it, or rendering diverges; #845):
1. **Binning** — floor-based: ``step = len // pixel_height`` full bins plus
   one trailing partial bin. (A ceil-based partition produces different
   sample sets for the same curve.)
2. **NaN handling** — a bin containing any non-finite sample MUST emit its
   finite min and max *and* one NaN sample at the bin's first non-finite
   index, in index (depth) order, so the polyline breaks at the hole
   instead of being bridged (#726 / #845). A fully non-finite bin emits its
   first sample. Use :func:`minmax_bin_indices` for the reference logic.
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

    finite = np.isfinite(v_trunc)
    if bool(finite.all()):
        # Fast path: no NaNs, keep the previous 2-points-per-bin layout.
        col_max = np.argmax(v_trunc, axis=1)
        col_min = np.argmin(v_trunc, axis=1)
        row_offsets = np.arange(n_full_bins) * step
        global_max = row_offsets + col_max
        global_min = row_offsets + col_min
        min_first = global_min <= global_max
        first = np.where(min_first, global_min, global_max)
        second = np.where(min_first, global_max, global_min)
        out_idx = np.empty(n_full_bins * 2, dtype=np.intp)
        out_idx[0::2] = first
        out_idx[1::2] = second
    else:
        # A NaN wins both argmin and argmax, wiping the bin's finite extrema.
        # Keep finite min/max and emit one NaN so the polyline still breaks.
        out_parts = [_bin_keep_indices(v_trunc[i]) + i * step for i in range(n_full_bins)]
        out_idx = (
            np.concatenate(out_parts) if out_parts else np.empty(0, dtype=np.intp)
        )

    # Trailing partial bin (n not divisible by step).
    if full_count < n:
        extra = _bin_keep_indices(values[full_count:]) + full_count
        out_idx = np.concatenate([out_idx, extra]) if out_idx.size else extra

    return depths[out_idx], values[out_idx]


def _bin_keep_indices(chunk: np.ndarray) -> np.ndarray:
    """Reference per-bin sample indices for one min/max LOD bin.

    Public contract helper (:func:`minmax_bin_indices`) — injected providers
    (e.g. a C++-accelerated host hook) must reproduce this NaN breakout, or
    holes in the curve get bridged (#845)."""
    return minmax_bin_indices(chunk)


def minmax_bin_indices(chunk: np.ndarray) -> np.ndarray:
    """In-bin sample indices to emit for one min/max LOD bin.

    Reference semantics (the engine default and the hook contract, #845):
    keep the finite min/max; when the bin contains any non-finite sample,
    also emit the FIRST non-finite index so the rendered polyline breaks at
    the hole. A fully non-finite bin emits its first sample. Output is
    sorted by index.
    """
    finite = np.isfinite(chunk)
    if not np.any(finite):
        return np.array([0], dtype=np.intp)
    filled_min = np.where(finite, chunk, np.inf)
    filled_max = np.where(finite, chunk, -np.inf)
    mn = int(np.argmin(filled_min))
    mx = int(np.argmax(filled_max))
    if bool(finite.all()):
        lo, hi = (mn, mx) if mn <= mx else (mx, mn)
        return np.array([lo, hi], dtype=np.intp)
    nan_i = int(np.flatnonzero(~finite)[0])
    return np.unique(np.array([mn, mx, nan_i], dtype=np.intp))


_provider: DownsampleFn = numpy_minmax_downsample


def get_downsample_provider() -> DownsampleFn:
    return _provider


def set_downsample_provider(fn: DownsampleFn | None) -> None:
    """Install a custom downsample provider; ``None`` restores the default."""
    global _provider
    _provider = fn if fn is not None else numpy_minmax_downsample
