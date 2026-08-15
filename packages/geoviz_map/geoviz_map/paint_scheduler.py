"""PaintScheduler — debounces rapid update() calls into 60fps repaints.
LayerPixmapCache — per-layer oversized QPixmap buffer for pan headroom."""
from __future__ import annotations

from geoviz_common.paint_scheduler import (
    BaseLayerPixmapCache,
    PaintScheduler,
)

from geoviz_map.viewport import MapViewport


class LayerPixmapCache(BaseLayerPixmapCache):
    """Per-layer pixmap cache with oversized buffer for pan headroom.

    Renders the layer into a 2x-viewport QPixmap. On pan, blit-shifts
    from the cached pixmap instead of re-rendering. Re-renders only on
    zoom change, data change (mark_dirty), or pan > 50% margin.

    Respects ``devicePixelRatio`` so text and lines render at native
    screen density on HiDPI displays.
    """

    def _make_buf_viewport(self, vp: MapViewport, buf_w: int, buf_h: int):
        from geoviz_map.projection import world_to_lnglat
        lng, lat = world_to_lnglat(*vp.center_world)
        return MapViewport(
            center_lng=lng, center_lat=lat,
            zoom=vp.zoom, width=buf_w, height=buf_h,
        )


__all__ = ["LayerPixmapCache", "PaintScheduler"]
