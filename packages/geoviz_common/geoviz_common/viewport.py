"""BaseViewport — shared center+zoom → screen-pixel mapping geometry.

geoviz_map (Web Mercator) and geoviz_paleo_map (Plate Carrée identity)
viewport classes share the world↔screen geometry but differ in the ``scale``
property and their projection functions, so both inherit from this base and
bind their own ``lnglat_to_world`` / ``world_to_lnglat``.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF


class BaseViewport:
    """Tracks the visible world region.

    Coordinate systems:
      lng/lat   — geographic degrees
      world     — projected coordinates (subclass projection)
      screen    — widget pixels (origin top-left, y-down)

    Subclasses must provide a ``scale`` property (pixels per world unit) and
    initialize ``center_world``, ``zoom``, ``width`` and ``height``; they may
    override the bound ``lnglat_to_world`` / ``world_to_lnglat`` projections.
    """

    #: (lng, lat) → (x, y) projection; subclasses bind their module's version
    #: (MapViewport: Web Mercator, PaleoMapViewport: Plate Carrée identity).
    lnglat_to_world = staticmethod(lambda lng, lat: (lng, lat))
    #: (x, y) → (lng, lat) inverse projection.
    world_to_lnglat = staticmethod(lambda x, y: (x, y))

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
        return self.world_to_screen(*self.lnglat_to_world(lng, lat))

    def screen_to_lnglat(self, pt: QPointF) -> tuple[float, float]:
        x, y = self.screen_to_world(pt)
        return self.world_to_lnglat(x, y)

    def pan_world(self, dx: float, dy: float) -> None:
        """Shift the center by world-unit delta."""
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
