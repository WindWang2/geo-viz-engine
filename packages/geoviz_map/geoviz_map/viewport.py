"""MapViewport — center + zoom + screen-pixel mapping (MapLibre-compatible)."""
import math

from PySide6.QtCore import QPointF

from geoviz_map.projection import R_EARTH, lnglat_to_world, world_to_lnglat


class MapViewport:
    """Tracks the visible world region.

    Coordinate systems:
      lng/lat   — geographic (WGS84 degrees)
      world     — Web Mercator meters (continuous)
      screen    — widget pixels (origin top-left, y-down)

    Zoom convention matches MapLibre GL: at zoom z, the world is rendered
    at 256 * 2^z pixels per world circumference (2π * R).
    """

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

    def world_to_screen(self, x: float, y: float) -> QPointF:
        s = self.scale
        sx = (x - self.center_world[0]) * s + self.width / 2
        sy = (self.center_world[1] - y) * s + self.height / 2  # y flipped
        return QPointF(sx, sy)

    def screen_to_world(self, pt: QPointF) -> tuple[float, float]:
        s = self.scale
        x = (pt.x() - self.width / 2) / s + self.center_world[0]
        y = self.center_world[1] - (pt.y() - self.height / 2) / s
        return x, y

    def lnglat_to_screen(self, lng: float, lat: float) -> QPointF:
        return self.world_to_screen(*lnglat_to_world(lng, lat))

    def screen_to_lnglat(self, pt: QPointF) -> tuple[float, float]:
        x, y = self.screen_to_world(pt)
        return world_to_lnglat(x, y)

    def pan_world(self, dx: float, dy: float) -> None:
        """Shift the center by world-meter delta."""
        cx, cy = self.center_world
        self.center_world = (cx + dx, cy + dy)

    def pan_pixels(self, dx_px: float, dy_px: float) -> None:
        """Shift the center by screen-pixel delta (drag-pan)."""
        s = self.scale
        self.pan_world(-dx_px / s, dy_px / s)  # drag right → world left

    def world_bbox(self) -> tuple[float, float, float, float]:
        """(min_x, min_y, max_x, max_y) of currently visible world region."""
        s = self.scale
        half_w = self.width / 2 / s
        half_h = self.height / 2 / s
        cx, cy = self.center_world
        return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
