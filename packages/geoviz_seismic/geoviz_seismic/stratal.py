"""Stratal / proportional slicing between two horizons.

A *stratal slice* (a.k.a. proportional slice, horizon-relative slice) is a 2-D
attribute map sampled along a geological-time surface that is interpolated
*proportionally* between an upper and a lower horizon. Where the two bounding
horizons pinch together or apart, the surface tracks the local stratigraphic
proportion rather than absolute time — this is the standard tool for inspecting
depositional facies parallel to bedding, which flat time slices cannot reveal
when the strata are dipping or faulted.

This module is **pure numpy** (headless) and lives in the visualization engine
core. The Qt/OpenGL rendering of stratal slices as GL planes is handled on
:class:`~geoviz_seismic.renderer_3d.Renderer3D` via ``set_stratal_slices``.

Convention reminder
-------------------
The seismic volume has shape ``(nI, nX, nS)`` (inline, crossline, sample) and a
horizon grid from :class:`~geoviz_seismic.horizon.HorizonParser` has shape
``(nI, nX)`` with values in **sample-index space** (already converted from ms via
``(twt_ms - t0_ms) / dt_ms``). Working in sample-index space keeps the slicer
unit-agnostic: the caller decides the physical meaning of the third axis. NaN in
a horizon grid marks an absent pick and is propagated through.

Linear interpolation in the sample axis (``order=1``) is used deliberately — it
supersedes the integer truncation in
:func:`~geoviz_seismic.horizon.extract_along_horizon`, which is fine for a
single horizon but visibly stair-steps a *proportional* surface between two
horizons because the fractional part carries real stratigraphic information.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy.ndimage import map_coordinates

__all__ = [
    "build_proportional_surfaces",
    "stratal_slice_volume",
    "extract_stratal_slice",
    "validate_horizon_pair",
]


def validate_horizon_pair(
    top: np.ndarray,
    bottom: np.ndarray,
    *,
    volume_shape: tuple[int, int, int] | None = None,
) -> np.ndarray:
    """Validate two horizon grids for stratal slicing and return a validity mask.

    The grids must be broadcast-compatible (normally identical ``(nI, nX)``
    shapes). A sample is *valid* where both horizons are finite **and** the top
    horizon lies at or above the bottom horizon (``top <= bottom``); an inverted
    pair is geometrically meaningless for proportional interpolation and is
    masked out rather than silently producing inverted surfaces.

    Args:
        top: Upper horizon grid, sample-index space. NaN marks absent picks.
        bottom: Lower horizon grid, sample-index space.
        volume_shape: Optional ``(nI, nX, nS)``. When given, positions outside
            ``[0, nS - 1]`` on either horizon are also masked invalid.

    Returns:
        ``(nI, nX)`` boolean mask — ``True`` where the pair is usable.
    """
    top = np.asarray(top, dtype=float)
    bottom = np.asarray(bottom, dtype=float)
    if top.shape != bottom.shape:
        raise ValueError(
            f"horizon shape mismatch: top {top.shape} vs bottom {bottom.shape}"
        )
    valid = np.isfinite(top) & np.isfinite(bottom) & (bottom >= top)
    if volume_shape is not None:
        n_s = volume_shape[2]
        valid &= (top >= 0) & (top < n_s) & (bottom >= 0) & (bottom < n_s)
    return valid


def build_proportional_surfaces(
    top: np.ndarray,
    bottom: np.ndarray,
    fractions: float | list[float] | np.ndarray = (0.25, 0.50, 0.75),
    *,
    clamp: bool = True,
) -> np.ndarray:
    """Build one or more proportional (stratal) surfaces between two horizons.

    For a fraction ``k ∈ [0, 1]`` the surface is
    ``surface_k = top + k * (bottom - top)``. ``k=0`` reproduces the top
    horizon, ``k=1`` the bottom horizon, and intermediate values give
    proportionally-interpolated geological-time surfaces.

    Args:
        top: Upper horizon grid, sample-index space ``(nI, nX)``.
        bottom: Lower horizon grid, sample-index space ``(nI, nX)``.
        fractions: One fraction, or a sequence. Defaults to quarter/half/three-
            quarter cuts. Values are clipped to ``[0, 1]``.
        clamp: When True (default), positions are clamped into ``[top, bottom]``
            exactly — this is a no-op for in-range fractions but protects against
            floating-point drift; it never invents geometry outside the pair.

    Returns:
        If a single fraction (scalar) is given, an ``(nI, nX)`` array.
        Otherwise an ``(K, nI, nX)`` array, one surface per fraction, in input
        order. NaN propagates from either horizon; inverted cells keep their NaN.
    """
    top = np.asarray(top, dtype=float)
    bottom = np.asarray(bottom, dtype=float)
    if top.shape != bottom.shape:
        raise ValueError(
            f"horizon shape mismatch: top {top.shape} vs bottom {bottom.shape}"
        )

    scalar = np.isscalar(fractions) or (
        isinstance(fractions, np.ndarray) and fractions.ndim == 0
    )
    fracs = np.atleast_1d(np.asarray(fractions, dtype=float)).ravel()
    fracs = np.clip(fracs, 0.0, 1.0)

    # Work in a safe numeric substrate so NaN stays NaN (np.where would mask it).
    span = bottom - top
    surfaces = top[np.newaxis, ...] + fracs[:, np.newaxis, np.newaxis] * span
    if clamp:
        lo = np.minimum(top, bottom)
        hi = np.maximum(top, bottom)
        surfaces = np.clip(surfaces, lo, hi)
    if scalar:
        return surfaces[0]
    return surfaces


def extract_stratal_slice(
    volume: np.ndarray,
    surface: np.ndarray,
    *,
    window: int = 0,
    mode: Literal["rms", "mean", "max"] = "rms",
    order: int = 1,
) -> np.ndarray:
    """Sample a seismic volume along one (non-planar) stratal surface.

    Uses :func:`scipy.ndimage.map_coordinates` with linear interpolation
    (``order=1``) so the fractional sample position of a proportional surface is
    honoured — this is the key difference from
    :func:`~geoviz_seismic.horizon.extract_along_horizon`, which truncates to an
    integer sample.

    Args:
        volume: ``(nI, nX, nS)`` float seismic volume.
        surface: ``(nI, nX)`` grid of **sample-index** positions (float OK).
            NaN marks absent picks; those cells become NaN in the output.
        window: Half-window in samples. ``0`` (default) extracts a single
            interpolated sample per trace. ``N > 0`` aggregates over
            ``[surface - N, surface + N]`` (clipped to the volume) according to
            *mode*.
        mode: Aggregation for ``window > 0``: ``"rms"`` (root-mean-square,
            default, standard for amplitude attributes), ``"mean"``, or
            ``"max"`` (maximum absolute amplitude).
        order: Spline interpolation order passed to ``map_coordinates``.
            ``1`` (linear) is the sane default; ``0`` (nearest) matches the old
            integer-truncation behaviour for comparison.

    Returns:
        ``(nI, nX)`` float32 attribute map. NaN where *surface* is NaN or the
        extraction window falls entirely outside the volume.
    """
    volume = np.asarray(volume)
    surface = np.asarray(surface, dtype=float)
    n_i, n_x, n_s = volume.shape
    if surface.shape != (n_i, n_x):
        raise ValueError(
            f"surface shape {surface.shape} does not match volume "
            f"(first two axes) {(n_i, n_x)}"
        )

    valid = np.isfinite(surface)
    out = np.full((n_i, n_x), np.nan, dtype=np.float32)
    if not valid.any():
        return out

    if window <= 0:
        # Single linearly-interpolated sample per trace.
        t_idx = np.clip(surface, 0, n_s - 1)
        ii = np.broadcast_to(np.arange(n_i)[:, None], (n_i, n_x))
        xx = np.broadcast_to(np.arange(n_x)[None, :], (n_i, n_x))
        coords = np.stack([ii, xx, t_idx])
        sampled = map_coordinates(
            volume.astype(float, copy=False), coords, order=order,
            mode="constant", cval=0.0,
        ).astype(np.float32)
        out[valid] = sampled[valid]
        return out

    # Windowed aggregation: build offsets, sample each, reduce.
    half = int(window)
    offsets = np.arange(-half, half + 1)
    stack = np.full((n_i, n_x, offsets.size), np.nan, dtype=np.float32)
    ii = np.broadcast_to(np.arange(n_i)[:, None], (n_i, n_x))
    xx = np.broadcast_to(np.arange(n_x)[None, :], (n_i, n_x))
    for k, off in enumerate(offsets):
        idx = surface + off
        in_bounds = valid & (idx >= 0) & (idx < n_s)
        if not in_bounds.any():
            continue
        idx_safe = np.clip(idx, 0, n_s - 1)
        coords = np.stack([ii, xx, idx_safe])
        sampled = map_coordinates(
            volume.astype(float, copy=False), coords, order=order,
            mode="constant", cval=0.0,
        ).astype(np.float32)
        stack[..., k][in_bounds] = sampled[in_bounds]

    with np.errstate(invalid="ignore"):
        if mode == "rms":
            agg = np.sqrt(np.nanmean(np.square(stack), axis=2))
        elif mode == "mean":
            agg = np.nanmean(stack, axis=2)
        elif mode == "max":
            agg = np.nanmax(np.abs(stack), axis=2)
        else:  # pragma: no cover - guarded by callers; keep a safe fallback
            raise ValueError(f"unknown aggregation mode: {mode!r}")
    agg = np.asarray(agg, dtype=np.float32)
    all_nan = np.all(~np.isfinite(stack), axis=2)
    out = np.where(all_nan, np.nan, agg).astype(np.float32)
    return out


def stratal_slice_volume(
    volume: np.ndarray,
    top: np.ndarray,
    bottom: np.ndarray,
    fractions: float | list[float] | np.ndarray = (0.25, 0.50, 0.75),
    *,
    window: int = 0,
    mode: Literal["rms", "mean", "max"] = "rms",
    order: int = 1,
    return_surfaces: bool = False,
) -> np.ndarray | tuple[np.ndarray, np.ndarray]:
    """End-to-end stratal slicing: build surfaces, then sample the volume.

    Convenience that pairs :func:`build_proportional_surfaces` with
    :func:`extract_stratal_slice` for every requested fraction. Inverted horizon
    pairs (``top > bottom``) and absent picks (NaN) are masked out once and
    propagated through every surface, so the returned attribute maps are
    internally consistent.

    Args:
        volume: ``(nI, nX, nS)`` seismic volume.
        top, bottom: ``(nI, nX)`` horizon grids in sample-index space.
        fractions: One fraction or a sequence (see
            :func:`build_proportional_surfaces`).
        window, mode, order: See :func:`extract_stratal_slice`.
        return_surfaces: When True, also return the ``(K, nI, nX)`` surface grid
            array (useful for positioning the GL planes / debugging).

    Returns:
        Attribute maps of shape ``(nI, nX)`` (single fraction) or
        ``(K, nI, nX)`` (multiple). If *return_surfaces*, returns
        ``(maps, surfaces)`` with surfaces shaped to match the fraction count.

    Example:
        >>> import numpy as np
        >>> vol = np.zeros((6, 6, 20), np.float32)
        >>> # a flat reflector at sample 10
        >>> vol[:, :, 10] = 1.0
        >>> top = np.full((6, 6), 5.0)   # sample index
        >>> bot = np.full((6, 6), 15.0)
        >>> amp = stratal_slice_volume(vol, top, bot, fractions=0.5)
        >>> bool(amp[0, 0] == 1.0)       # half-way surface hits sample 10
        True
    """
    volume = np.asarray(volume)
    top = np.asarray(top, dtype=float)
    bottom = np.asarray(bottom, dtype=float)
    if top.shape != volume.shape[:2] or bottom.shape != volume.shape[:2]:
        raise ValueError(
            f"horizon grids {top.shape}/{bottom.shape} must match volume "
            f"first-two-axes {volume.shape[:2]}"
        )

    # Enforce geometric sanity once: invert/absent cells become NaN everywhere.
    good = validate_horizon_pair(top, bottom, volume_shape=volume.shape)
    bad = ~good
    top_c = top.copy()
    bot_c = bottom.copy()
    top_c[bad] = np.nan
    bot_c[bad] = np.nan

    surfaces = build_proportional_surfaces(top_c, bot_c, fractions)
    multi = surfaces.ndim == 3
    if not multi:
        surfaces_for_loop = surfaces[np.newaxis, ...]
    else:
        surfaces_for_loop = surfaces

    maps = np.stack(
        [
            extract_stratal_slice(volume, s, window=window, mode=mode, order=order)
            for s in surfaces_for_loop
        ],
        axis=0,
    )
    if not multi:
        maps = maps[0]
    if return_surfaces:
        return maps, surfaces
    return maps
