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
    import colorsys
    rgba = np.zeros((n, 4), dtype=np.uint8)
    for i in range(n):
        h = i / n
        r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        rgba[i] = [int(r * 255), int(g * 255), int(b * 255), 255]
    return rgba


class ColormapManager:
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

    @staticmethod
    def get_colormap(name: str, n_colors: int = 256) -> np.ndarray:
        builder = ColormapManager._COLORMAPS.get(name)
        if builder is None:
            raise ValueError(f"Unknown colormap: {name}")
        return builder(n_colors)

    @staticmethod
    def apply_to_data(data: np.ndarray, name: str) -> np.ndarray:
        dmin, dmax = np.nanmin(data), np.nanmax(data)
        if dmax == dmin:
            normalized = np.zeros_like(data, dtype=np.float32)
        else:
            normalized = (data - dmin) / (dmax - dmin)
        lut = ColormapManager.get_colormap(name)
        indices = (normalized * (len(lut) - 1)).astype(np.int32)
        indices = np.clip(indices, 0, len(lut) - 1)
        return lut[indices]
