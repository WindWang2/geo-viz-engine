"""Seismic colour-map generation and data-to-RGBA mapping."""

import numpy as np


def _build_seismic(n: int) -> np.ndarray:
    t = np.linspace(0, 1, n)
    rgba = np.zeros((n, 4), dtype=np.uint8)
    mid = n // 2
    rgba[:mid, 0] = np.clip(t[:mid] * 2 * 255, 0, 255).astype(np.uint8)
    rgba[:mid, 1] = np.clip(t[:mid] * 2 * 255, 0, 255).astype(np.uint8)
    rgba[:mid, 2] = 255
    rgba[mid:, 0] = 255
    rgba[mid:, 1] = np.clip((1 - (t[mid:] - 0.5) * 2) * 255, 0, 255).astype(np.uint8)
    rgba[mid:, 2] = np.clip((1 - (t[mid:] - 0.5) * 2) * 255, 0, 255).astype(np.uint8)
    rgba[:, 3] = 255
    return rgba


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


class ColormapManager:
    """Registry of seismic colour maps with LUT caching.

    Built-in colormaps: ``seismic`` (red-blue diverging), ``gray``,
    ``jet``, ``hsv``. Lookup tables are built once and cached per name.
    """

    SEISMIC = "seismic"
    GRAY = "gray"
    JET = "jet"
    HSV = "hsv"

    _COLORMAPS = {
        "seismic": _build_seismic,
        "gray": _build_gray,
        "jet": _build_jet,
        "hsv": _build_hsv,
    }

    _LUT_CACHE: dict[str, np.ndarray] = {}

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
        """Clear all cached LUTs (useful for testing or memory-constrained scenarios)."""
        ColormapManager._LUT_CACHE.clear()

    @staticmethod
    def apply_to_data(data: np.ndarray, name: str) -> np.ndarray:
        """Map float32 data through a colour LUT to RGBA (min-max normalised)."""
        dmin, dmax = np.nanmin(data), np.nanmax(data)
        if dmax == dmin:
            normalized = np.zeros_like(data, dtype=np.float32)
        else:
            normalized = (data - dmin) / (dmax - dmin)
        lut = ColormapManager.get_colormap(name)
        indices = (normalized * (len(lut) - 1)).astype(np.int32)
        indices = np.clip(indices, 0, len(lut) - 1)
        return lut[indices]
