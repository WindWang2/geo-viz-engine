"""BaseScreenPathCache — caches screen-space QPainterPaths per zoom level.

Shared by geoviz_map.ScreenPathCache and geoviz_paleo_map.ScreenPathCache;
the paleo subclass additionally builds RDP-simplified LOD paths from raw
polygon rings via the ``_build_screen_path`` hook.
"""
from __future__ import annotations

from PySide6.QtGui import QPainterPath, QTransform


class BaseScreenPathCache:
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25).

    Entries bake the exact viewport scale and center into the transform. The
    zoom key is only quantized to 0.25 for grouping/eviction, so each entry
    also records the scale it was built at; a hit is reused only when the live
    scale matches to within 1e-6 relative error, otherwise the path is rebuilt
    at the current scale. When the live center pans away (or the widget is
    resized) at the same zoom key, cached paths would draw offset from
    live-transformed overlays — so we invalidate by tracking ``_zoom_center``
    and viewport dimensions.
    """

    def __init__(self, max_levels: int = 4):
        self._cache: dict[tuple[float, str], tuple[QPainterPath, float]] = {}
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
                     viewport) -> QPainterPath:
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

        cached = self._cache.get(cache_key)
        if cached is not None and feature_id not in self._dirty:
            path, cached_scale = cached
            # The zoom key is quantized to 0.25, but the path bakes in the
            # exact viewport scale — reusing it at another scale within the
            # same bucket (max ±0.125 zoom, ~9% size error) would misalign
            # the polygon against live-transformed overlays (Issue #48).
            if abs(viewport.scale - cached_scale) < 1e-6 * viewport.scale:
                return path

        screen_path = self._build_screen_path(feature_id, world_path, viewport)
        self._cache[cache_key] = (screen_path, viewport.scale)
        self._zoom_center[zoom_key] = center
        self._dirty.discard(feature_id)
        self._evict(zoom_key)
        return screen_path

    def _build_screen_path(self, feature_id: str, world_path: QPainterPath,
                           viewport) -> QPainterPath:
        """Build the screen-space path on a cache miss. Subclasses may override
        to substitute a different builder (e.g. RDP-simplified LOD paths)."""
        return self._transform_path(world_path, viewport)

    def _transform_path(self, world_path: QPainterPath, vp) -> QPainterPath:
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
        zooms = sorted({k[0] for k in self._cache})
        if len(zooms) <= self._max_levels:
            return
        keep = set(zooms[-self._max_levels:])
        self._cache = {k: v for k, v in self._cache.items() if k[0] in keep}
        self._zoom_center = {z: c for z, c in self._zoom_center.items() if z in keep}
