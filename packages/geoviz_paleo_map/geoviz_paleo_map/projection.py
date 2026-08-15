"""Plate Carrée (equirectangular) identity projection.

PaleoMap uses ECharts geo's default coordinate system, which is direct
lng/lat → x/y. Suitable for paleogeographic data that lacks modern WGS84
reference; preserves angular spacing.

This module is an *identity* projection: ``lnglat_to_world`` maps
(lng, lat) → (x, y) 1:1 with no ellipsoid math, and ``world_to_lnglat`` is
its exact inverse. Input coordinates MUST already be in the project CRS —
callers are responsible for reprojecting well data with
``geoviz_plots.crs.coerce_to_project_crs`` (or setting the project CRS via
``geoviz_plots.crs.set_project_crs``) before calling ``lnglat_to_world``.

Scale-conversion helpers elsewhere in the codebase (``floating_slider``'s
``_kpd``, ``canvas._km_per_degree``, the scale-bar / export layers) turn
degrees into ground distance with the spherical approximation
``111.32 * cos(lat)`` km per degree of longitude. That approximation assumes
a sphere with ~111.32 km per equatorial degree, so it is only valid for
small areas at mid latitudes: it degrades toward the poles (where
``cos(lat) → 0``) and over large longitude spans where the scale distortion
of the Plate Carrée grid is no longer negligible.
"""


def lnglat_to_world(lng: float, lat: float) -> tuple[float, float]:
    """Direct identity: (lng, lat) → (x, y)."""
    return lng, lat


def world_to_lnglat(x: float, y: float) -> tuple[float, float]:
    """Identity inverse."""
    return x, y
