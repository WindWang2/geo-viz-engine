"""PaleoMapViewport — center+zoom → screen-pixel mapping (Plate Carrée)."""

from PySide6.QtCore import QPointF

from geoviz_paleo_map.projection import lnglat_to_world, world_to_lnglat


class PaleoMapViewport:
    """Tracks the visible region.

    At zoom z the scale is 2^(z-1) pixels per degree (zoom=1 → 1 px/deg,
    zoom=2 → 2 px/deg, ...). Y axis flipped: screen y grows downward,
    lat grows upward.
    """

    def __init__(self, center_lng: float, center_lat: float, zoom: float,
                 width: int, height: int):
        self.center_world = lnglat_to_world(center_lng, center_lat)
        self.zoom = zoom
        self.width = width
        self.height = height

    @property
    def scale(self) -> float:
        """Pixels per world unit (degree)."""
        return 2.0 ** (self.zoom - 1.0)

    def world_to_screen(self, x: float, y: float) -> QPointF:
        s = self.scale
        sx = (x - self.center_world[0]) * s + self.width / 2
        sy = (self.center_world[1] - y) * s + self.height / 2
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
        cx, cy = self.center_world
        self.center_world = (cx + dx, cy + dy)

    def pan_pixels(self, dx_px: float, dy_px: float) -> None:
        s = self.scale
        self.pan_world(-dx_px / s, dy_px / s)

    def world_bbox(self) -> tuple[float, float, float, float]:
        s = self.scale
        half_w = self.width / 2 / s
        half_h = self.height / 2 / s
        cx, cy = self.center_world
        return (cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
