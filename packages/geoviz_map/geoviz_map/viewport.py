"""MapViewport — center + zoom + screen-pixel mapping (MapLibre-compatible)."""
import math

from geoviz_common.viewport import BaseViewport

from geoviz_map.projection import R_EARTH, lnglat_to_world, world_to_lnglat


class MapViewport(BaseViewport):
    """Tracks the visible world region.

    Coordinate systems:
      lng/lat   — geographic (WGS84 degrees)
      world     — Web Mercator meters (continuous)
      screen    — widget pixels (origin top-left, y-down)

    Zoom convention matches MapLibre GL: at zoom z, the world is rendered
    at 256 * 2^z pixels per world circumference (2π * R).
    """

    lnglat_to_world = staticmethod(lnglat_to_world)
    world_to_lnglat = staticmethod(world_to_lnglat)

    def __init__(self, center_lng: float, center_lat: float, zoom: float,
                 width: int, height: int):
        self.center_world = lnglat_to_world(center_lng, center_lat)
        self.zoom = zoom
        self.width = width
        self.height = height

    @property
    def scale(self) -> float:
        """Pixels per world meter."""
        return 256.0 * (2 ** self.zoom) / (2 * math.pi * R_EARTH)
