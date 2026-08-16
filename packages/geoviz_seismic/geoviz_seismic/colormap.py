"""Seismic colour-map generation and data-to-RGBA mapping."""

from __future__ import annotations

import numpy as np

# ---------------------------------------------------------------------------
# GPU acceleration (lazy cupy import — same pattern as gpu_ops.py)
# ---------------------------------------------------------------------------
try:
    import cupy as cp
    _CUPY_AVAILABLE = True
    try:
        _ = cp.cuda.Device().id
    except Exception:
        _CUPY_AVAILABLE = False
except ImportError:
    cp = None
    _CUPY_AVAILABLE = False

# Below this element count, GPU kernel-launch + D2H transfer overhead exceeds
# the compute benefit — defer to the NumPy path. ~256x256 is the breakeven on
# an RTX 3080 Laptop for a normalize+LUT-gather pipeline.
_GPU_MIN_ELEMENTS = 256 * 256

# Unified GPU LUT texture cache — keyed on "name:n_colors" for named colormaps
# (the same key ColormapManager.get_colormap uses), or id(lut) for raw LUT
# arrays. Replaces the scattered _gpu_lut_cache / _color_table_lut_id caches
# that previously lived in gpu_ops.py and profile_vd.py.
_gpu_lut_cache: dict[str | int, cp.ndarray] = {}


def _normalize_and_clip(
    data: np.ndarray,
    lut_size: int,
    value_range: tuple[float, float] | None = None,
) -> tuple[object, np.ndarray]:
    """Shared normalize+clip step for normalize_to_index / apply_colormap.

    Returns ``(xp, idx)`` where ``idx`` is an int32 array in ``[0, lut_size-1]``
    on whichever backend (numpy or cupy) ``data`` lives. The ``xp`` is the
    module (``np`` or ``cp``) so the caller knows whether to ``asnumpy``.

    Small cupy arrays fall back to host first: mixing ``np.*`` with cupy inputs
    can leave a cupy result while ``xp is np``, which then skips the D2H path
    in callers (breaks GL_R8 upload for preview planes ≤128²).
    """
    use_gpu = (
        _CUPY_AVAILABLE
        and cp is not None
        and isinstance(data, cp.ndarray)
        and data.size >= _GPU_MIN_ELEMENTS
    )
    if (
        not use_gpu
        and _CUPY_AVAILABLE
        and cp is not None
        and isinstance(data, cp.ndarray)
    ):
        data = cp.asnumpy(data)
    xp = cp if use_gpu else np

    if value_range is not None:
        dmin, dmax = value_range
    else:
        dmin, dmax = xp.nanmin(data), xp.nanmax(data)

    if dmax == dmin:
        idx = xp.zeros(data.shape, dtype=xp.int32)
    else:
        norm = (data - dmin) / (dmax - dmin)
        idx = xp.clip(
            (norm * (lut_size - 1)).astype(xp.int32), 0, lut_size - 1
        )
    return xp, idx


def _build_seismic(n: int) -> np.ndarray:
    t = np.linspace(0, 1, n)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    
    # Professional Petrel/OpendTect style smooth seismic colormap
    # Keypoints: Dark Blue -> Blue -> White -> Red -> Dark Red
    xp = [0.0, 0.25, 0.5, 0.75, 1.0]
    fp_r = [0, 0, 255, 255, 128]
    fp_g = [0, 0, 255, 0, 0]
    fp_b = [128, 255, 255, 0, 0]
    
    rgba[:, 0] = np.interp(t, xp, fp_r).astype(np.uint8)
    rgba[:, 1] = np.interp(t, xp, fp_g).astype(np.uint8)
    rgba[:, 2] = np.interp(t, xp, fp_b).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


def _build_seismic_r(n: int) -> np.ndarray:
    """Reversed seismic (red-negative / blue-positive) for red-white-blue."""
    return _build_seismic(n)[::-1].copy()

def _build_gray(n: int) -> np.ndarray:
    vals = np.linspace(0, 255, n, dtype=np.uint8)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, 0] = vals
    rgba[:, 1] = vals
    rgba[:, 2] = vals
    rgba[:, 3] = 255
    return rgba


def _build_jet(n: int) -> np.ndarray:
    t = np.linspace(0, 1, n)
    r = np.clip(1.5 - abs(4 * t - 3), 0, 1)
    g = np.clip(1.5 - abs(4 * t - 2), 0, 1)
    b = np.clip(1.5 - abs(4 * t - 1), 0, 1)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, 0] = (r * 255).astype(np.uint8)
    rgba[:, 1] = (g * 255).astype(np.uint8)
    rgba[:, 2] = (b * 255).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


def _build_hsv(n: int) -> np.ndarray:
    h = np.linspace(0, 1, n, endpoint=False)
    # Vectorised HSV→RGB for S=1, V=1
    i = (h * 6).astype(int) % 6
    f = h * 6 - np.floor(h * 6)
    rgb = np.zeros((n, 3), dtype=np.uint8)
    for idx, (r, g, b) in enumerate([(1, f, 0), (1 - f, 1, 0), (0, 1, f),
                                      (0, 1 - f, 1), (f, 0, 1), (1, 0, 1 - f)]):
        mask = i == idx
        rgb[mask, 0] = (np.broadcast_to(np.asarray(r), mask.shape) * 255)[mask].astype(np.uint8)
        rgb[mask, 1] = (np.broadcast_to(np.asarray(g), mask.shape) * 255)[mask].astype(np.uint8)
        rgb[mask, 2] = (np.broadcast_to(np.asarray(b), mask.shape) * 255)[mask].astype(np.uint8)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, :3] = rgb
    rgba[:, 3] = 255
    return rgba


def _build_viridis(n: int) -> np.ndarray:
    """Perceptually uniform sequential colormap (viridis-like)."""
    t = np.linspace(0, 1, n)
    # Viridis keypoints
    xp = [0.0, 0.25, 0.5, 0.75, 1.0]
    fp_r = [68, 59, 33, 95, 253]
    fp_g = [1, 82, 145, 180, 231]
    fp_b = [84, 139, 140, 86, 37]
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, 0] = np.interp(t, xp, fp_r).astype(np.uint8)
    rgba[:, 1] = np.interp(t, xp, fp_g).astype(np.uint8)
    rgba[:, 2] = np.interp(t, xp, fp_b).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


def _build_phase_wheel(n: int) -> np.ndarray:
    """Circular colormap for phase data (wraps around)."""
    t = np.linspace(0, 1, n, endpoint=False)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    rgba[:, 0] = ((0.5 + 0.5 * np.cos(2 * np.pi * t)) * 255).astype(np.uint8)
    rgba[:, 1] = ((0.5 + 0.5 * np.cos(2 * np.pi * t - 2 * np.pi / 3)) * 255).astype(np.uint8)
    rgba[:, 2] = ((0.5 + 0.5 * np.cos(2 * np.pi * t - 4 * np.pi / 3)) * 255).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


class ColormapManager:
    """Registry of seismic colour maps with LUT caching.

    Built-in colormaps: ``seismic`` (red-blue diverging), ``gray``,
    ``jet``, ``hsv``. Lookup tables are built once and cached per name.
    """

    SEISMIC = "seismic"
    GRAY = "gray"
    JET = "jet"
    HSV = "hsv"
    VIRIDIS = "viridis"
    PHASE_WHEEL = "phase_wheel"

    _COLORMAPS = {
        "seismic": _build_seismic,
        "seismic_r": _build_seismic_r,
        "gray": _build_gray,
        "jet": _build_jet,
        "hsv": _build_hsv,
        "viridis": _build_viridis,
        "phase_wheel": _build_phase_wheel,
    }

    _LUT_CACHE: dict[str, np.ndarray] = {}
    _COLOR_TABLE_CACHE: dict[str, list[int]] = {}

    @staticmethod
    def get_colormap(name: str, n_colors: int = 256) -> np.ndarray:
        """Return an ``(n_colors, 4)`` RGBA look-up table. Results are cached."""
        cache_key = f"{name}:{n_colors}"
        cached = ColormapManager._LUT_CACHE.get(cache_key)
        if cached is not None:
            return cached
        builder = ColormapManager._COLORMAPS.get(name)
        if builder is None:
            raise ValueError(
                f"Unknown colormap: {name!r}. "
                f"Available: {sorted(ColormapManager._COLORMAPS)}"
            )
        lut = builder(n_colors)
        ColormapManager._LUT_CACHE[cache_key] = lut
        return lut

    @staticmethod
    def clear_cache() -> None:
        """Clear all cached LUTs and GPU textures (testing / memory-constrained)."""
        ColormapManager._LUT_CACHE.clear()
        _gpu_lut_cache.clear()
        ColormapManager._COLOR_TABLE_CACHE.clear()

    @staticmethod
    def get_color_table(name: str) -> list[int]:
        """Return a 256-entry Qt ``qRgb`` colour table for ``QImage.Format_Indexed8``.

        Cached per colormap name — the table is rebuilt only when the colormap
        actually changes. This replaces the per-widget ``_color_table`` /
        ``_color_table_lut_id`` (``id(lut)``) caches that previously lived in
        ``profile_vd.py``.
        """
        cached = ColormapManager._COLOR_TABLE_CACHE.get(name)
        if cached is not None:
            return cached
        from PySide6.QtGui import qRgb
        lut = ColormapManager.get_colormap(name)
        table = [qRgb(int(r), int(g), int(b)) for r, g, b, _ in lut[:256]]
        ColormapManager._COLOR_TABLE_CACHE[name] = table
        return table

    @staticmethod
    def normalize_to_index(
        data: np.ndarray,
        lut_size: int = 256,
        value_range: tuple[float, float] | None = None,
    ) -> np.ndarray:
        """Normalize data to a uint8 LUT-index array in ``[0, lut_size-1]``.

        Fuses min-max normalization + clip into a single pass, returning a
        uint8 array on CPU. GPU acceleration is used automatically when cupy
        is available, the input is a cupy array, and the array is large enough
        to amortize kernel-launch overhead (``_GPU_MIN_ELEMENTS``).

        Note: the index values are identical to ``gpu_ops._normalize_to_lut_index``
        but the return dtype is uint8 (not int32) — the Indexed8/GL_R8 texture
        path needs a single-byte index.

        Args:
            data: Input array (numpy or cupy).
            lut_size: Number of LUT entries (default 256 for Indexed8/GL_R8).
                Must be ≤ 256 (uint8 range).
            value_range: Optional ``(vmin, vmax)`` override. When ``None``,
                ``nanmin``/``nanmax`` of the data is used.

        Returns:
            ``np.ndarray`` of dtype ``uint8``, same shape as ``data``.
        """
        if lut_size < 1 or lut_size > 256:
            raise ValueError(f"lut_size must be in [1, 256], got {lut_size}")
        xp, idx = _normalize_and_clip(data, lut_size, value_range)
        # Always return host uint8 (contract for Indexed8 / GL_R8). Prefer
        # isinstance over ``xp is cp`` so partial GPU fall-through cannot leak.
        if _CUPY_AVAILABLE and cp is not None and isinstance(idx, cp.ndarray):
            idx = cp.asnumpy(idx)
        return np.asarray(idx, dtype=np.uint8)

    @staticmethod
    def apply_colormap(
        data: np.ndarray,
        name: str | None = None,
        lut: np.ndarray | None = None,
        value_range: tuple[float, float] | None = None,
    ) -> np.ndarray:
        """Normalize data and gather through a colour LUT → RGBA image.

        One-stop colour application: normalizes to ``[0, lut_len-1]``, then
        gathers through the LUT to produce an ``(H, W, 4)`` uint8 RGBA array.
        GPU acceleration is used automatically when beneficial (same guard
        as :meth:`normalize_to_index`).

        Either ``name`` (a registered colormap name) or ``lut`` (a raw
        ``(N, 4)`` uint8 array) must be provided. When ``name`` is given,
        the LUT is fetched from :meth:`get_colormap` and the GPU texture
        cache is keyed on ``name:len(lut)`` — no ``id(lut)`` for named
        colormaps. When ``lut`` is passed directly, the cache falls back to
        ``id(lut)`` to avoid per-call re-upload.

        Args:
            data: Input array (numpy or cupy).
            name: Colormap name (e.g. ``"seismic"``, ``"gray"``).
            lut: Raw ``(N, 4)`` uint8 RGBA array. Used when ``name`` is ``None``.
            value_range: Optional ``(vmin, vmax)`` override.

        Returns:
            ``np.ndarray`` of dtype ``uint8``, shape ``(*data.shape, 4)``.
        """
        if lut is None:
            if name is None:
                raise ValueError("apply_colormap requires either name or lut")
            lut = ColormapManager.get_colormap(name)

        xp, idx = _normalize_and_clip(data, len(lut), value_range)

        if xp is cp or (
            _CUPY_AVAILABLE and cp is not None and isinstance(idx, cp.ndarray)
        ):
            # GPU path: gather through a cached GPU LUT texture.
            # Named colormaps key on "name:len(lut)"; raw LUTs key on id(lut)
            # to avoid the per-call cp.asarray(lut) that made GPU 200x slower.
            cache_key = f"{name}:{len(lut)}" if name is not None else id(lut)
            gpu_lut = _gpu_lut_cache.get(cache_key)
            if gpu_lut is None:
                gpu_lut = cp.asarray(lut)
                _gpu_lut_cache[cache_key] = gpu_lut
            if not isinstance(idx, cp.ndarray):
                idx = cp.asarray(idx)
            rgba = gpu_lut[idx]
            return cp.asnumpy(rgba)

        # CPU path: numpy fancy-index gather through the LUT.
        return lut[idx]
