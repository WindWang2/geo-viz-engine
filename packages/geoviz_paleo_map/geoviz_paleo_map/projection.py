"""Plate Carrée (equirectangular) projection.

PaleoMap uses ECharts geo's default coordinate system, which is direct
lng/lat → x/y. Suitable for paleogeographic data that lacks modern WGS84
reference; preserves angular spacing.
"""


def lnglat_to_world(lng: float, lat: float) -> tuple[float, float]:
    """Direct identity: (lng, lat) → (x, y)."""
    return lng, lat


def world_to_lnglat(x: float, y: float) -> tuple[float, float]:
    """Identity inverse."""
    return x, y
