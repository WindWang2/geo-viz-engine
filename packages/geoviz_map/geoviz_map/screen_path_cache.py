"""ScreenPathCache — caches screen-space QPainterPaths per zoom level."""
from __future__ import annotations

from PySide6.QtGui import QPainterPath, QTransform

from geoviz_map.viewport import MapViewport


class ScreenPathCache:
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25).

    Entries bake the viewport center and size into the transform. When the
    live center pans away (or the widget is resized) at the same zoom key,
    cached paths would draw offset from live-transformed overlays — so we
    invalidate by tracking ``_zoom_center`` and viewport dimensions.
    """

    def __init__(self, max_levels: int = 4):
        self._cache: dict[tuple[float, str], QPainterPath] = {}
        self._dirty: set[str] = set()
        self._max_levels = max_levels
        self._zoom_center: dict[float, tuple[float, float]] = {}
        self._vp_width: int = 0
        self._vp_height: int = 0

    def mark_dirty(self, feature_id: str) -> None:
        self._dirty.add(feature_id)

    def mark_all_dirty(self) -> None:
        for key in list(self._cache.keys()):
            self._dirty.add(key[1])

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: MapViewport) -> QPainterPath:
        if viewport.width != self._vp_width or viewport.height != self._vp_height:
            self._cache.clear()
            self._zoom_center.clear()
            self._vp_width = viewport.width
            self._vp_height = viewport.height

        zoom_key = round(viewport.zoom * 4) / 4
        cache_key = (zoom_key, feature_id)

        cached_center = self._zoom_center.get(zoom_key)
        center = viewport.center_world
        if cached_center is not None and cached_center != center:
            # Center moved at this zoom — invalidate every feature at this zoom.
            self._cache = {k: v for k, v in self._cache.items() if k[0] != zoom_key}

        if cache_key in self._cache and feature_id not in self._dirty:
            return self._cache[cache_key]

        screen_path = self._transform_path(world_path, viewport)
        self._cache[cache_key] = screen_path
        self._zoom_center[zoom_key] = center
        self._dirty.discard(feature_id)
        self._evict(zoom_key)
        return screen_path

    def _transform_path(self, world_path: QPainterPath,
                        vp: MapViewport) -> QPainterPath:
        s = vp.scale
        cx, cy = vp.center_world
        ox = vp.width / 2
        oy = vp.height / 2
        t = QTransform()
        t.translate(ox, oy)
        t.scale(s, -s)
        t.translate(-cx, -cy)
        return world_path * t

    def _evict(self, current_zoom: float) -> None:
        zooms = sorted(set(k[0] for k in self._cache))
        if len(zooms) <= self._max_levels:
            return
        keep = set(zooms[-self._max_levels:])
        self._cache = {k: v for k, v in self._cache.items() if k[0] in keep}
        self._zoom_center = {z: c for z, c in self._zoom_center.items() if z in keep}
