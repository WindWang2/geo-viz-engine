"""PaleoMapViewport — center+zoom → screen-pixel mapping (Plate Carrée)."""

import math
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
        self._center_world = lnglat_to_world(center_lng, center_lat)
        self._zoom = zoom
        self.width = width
        self.height = height
        self._data_bounds: tuple[float, float, float, float] | None = None
        self.clamp_to_bounds: bool = True

    @property
    def zoom(self) -> float:
        return self._zoom

    @zoom.setter
    def zoom(self, val: float) -> None:
        self._zoom = val
        self.clamp_viewport()

    @property
    def center_world(self) -> tuple[float, float]:
        return self._center_world

    @center_world.setter
    def center_world(self, val: tuple[float, float]) -> None:
        self._center_world = val
        self.clamp_viewport()

    @property
    def data_bounds(self) -> tuple[float, float, float, float] | None:
        return self._data_bounds

    @data_bounds.setter
    def data_bounds(self, val: tuple[float, float, float, float] | None) -> None:
        self._data_bounds = val
        self.clamp_viewport()

    def clamp_viewport(self) -> None:
        """Clamp viewport center and zoom to guarantee that the map data fills the entire viewport."""
        if not self.clamp_to_bounds or self._data_bounds is None:
            return

        min_lng, max_lng, min_lat, max_lat = self._data_bounds
        W = max_lng - min_lng
        H = max_lat - min_lat
        if W <= 0 or H <= 0 or self.width <= 0 or self.height <= 0:
            return

        # 1. Clamp zoom level to prevent zooming out too far, but allow the map to be smaller than the canvas.
        # min(scale_x, scale_y) * 0.8 ensures the entire map fits inside the viewport with comfortable margins.
        scale_x = self.width / W
        scale_y = self.height / H
        min_scale = min(scale_x, scale_y) * 0.8
        min_zoom = math.log2(min_scale) + 1.0

        # We set min_zoom limit. max_zoom is 10.0.
        self._zoom = max(min_zoom, min(10.0, self._zoom))

        # 2. Clamp center so that the viewport remains fully inside data bounds
        s = self.scale
        half_w = self.width / 2 / s
        half_h = self.height / 2 / s

        cx, cy = self._center_world
        if W <= half_w * 2:
            cx = (min_lng + max_lng) / 2
        else:
            cx = max(min_lng + half_w, min(max_lng - half_w, cx))

        if H <= half_h * 2:
            cy = (min_lat + max_lat) / 2
        else:
            cy = max(min_lat + half_h, min(max_lat - half_h, cy))

        self._center_world = (cx, cy)

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
        self.clamp_viewport()
