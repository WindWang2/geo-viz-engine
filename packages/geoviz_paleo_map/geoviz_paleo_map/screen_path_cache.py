"""ScreenPathCache — caches screen-space QPainterPaths per zoom level."""
from __future__ import annotations

from PySide6.QtGui import QPainterPath, QTransform

from geoviz_paleo_map.viewport import PaleoMapViewport


class ScreenPathCache:
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25)."""

    def __init__(self, max_levels: int = 4):
        self._cache: dict[tuple[float, str], QPainterPath] = {}
        self._dirty: set[str] = set()
        self._max_levels = max_levels
        # Center baked into entries at each zoom level. When the live viewport
        # center moves away from this, all entries at that zoom are stale —
        # the cached screen path was transformed with the old center and would
        # draw at the wrong offset, separating polygons from live-transformed
        # overlays (e.g. RegionLabels).
        self._zoom_center: dict[float, tuple[float, float]] = {}
        self._vp_width: int = 0
        self._vp_height: int = 0

    def mark_dirty(self, feature_id: str) -> None:
        self._dirty.add(feature_id)

    def mark_all_dirty(self) -> None:
        for key in list(self._cache.keys()):
            self._dirty.add(key[1])

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: PaleoMapViewport,
                     polygons: list[np.ndarray] | None = None) -> QPainterPath:
        """Return screen-space path, building if needed.
        If polygons are provided, applies RDP simplification based on zoom level."""
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

        if polygons is not None:
            screen_path = self._build_lod_path(polygons, viewport)
        else:
            screen_path = self._transform_path(world_path, viewport)
            
        self._cache[cache_key] = screen_path
        self._zoom_center[zoom_key] = center
        self._dirty.discard(feature_id)
        self._evict(zoom_key)
        return screen_path

    def _build_lod_path(self, polygons: list[np.ndarray], 
                        vp: PaleoMapViewport) -> QPainterPath:
        from geoviz_paleo_map.lod import rdp_simplify
        from PySide6.QtCore import QPointF, Qt
        
        # 0.5 pixel tolerance in world space
        epsilon = 0.5 / max(1e-6, vp.scale)
        
        # Build transform once
        s = vp.scale
        cx, cy = vp.center_world
        ox = vp.width / 2
        oy = vp.height / 2
        
        path = QPainterPath()
        for ring in polygons:
            if len(ring) < 2:
                continue
            
            # Apply RDP simplification
            # Only simplify if many points
            if len(ring) > 50:
                simplified = rdp_simplify(ring, epsilon)
            else:
                simplified = ring
                
            if len(simplified) < 2:
                continue
                
            # Transform to screen coords: (x-cx)*s + ox, (cy-y)*s + oy
            # Note: Screen Y is flipped
            pts_screen = simplified.copy()
            pts_screen[:, 0] = (pts_screen[:, 0] - cx) * s + ox
            pts_screen[:, 1] = (cy - pts_screen[:, 1]) * s + oy
            
            path.moveTo(QPointF(pts_screen[0, 0], pts_screen[0, 1]))
            for i in range(1, len(pts_screen)):
                path.lineTo(QPointF(pts_screen[i, 0], pts_screen[i, 1]))
            path.closeSubpath()
            
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return path

    def _transform_path(self, world_path: QPainterPath,
                        vp: PaleoMapViewport) -> QPainterPath:
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
