"""PaintScheduler — debounces rapid update() calls into 60fps repaints.
LayerPixmapCache — per-layer oversized QPixmap buffer for pan headroom."""
from __future__ import annotations

from geoviz_common.paint_scheduler import (
    BaseLayerPixmapCache,
    PaintScheduler,
)

from geoviz_paleo_map.viewport import PaleoMapViewport


class LayerPixmapCache(BaseLayerPixmapCache):
    """Per-layer pixmap cache with oversized buffer for pan headroom.

    Renders the layer into a 2x-viewport QPixmap. On pan, blit-shifts
    from the cached pixmap instead of re-rendering. Re-renders only on
    zoom change, data change (mark_dirty), or pan > 50% margin.

    Respects ``devicePixelRatio`` so text and lines render at native
    screen density on HiDPI displays — the pixmap is allocated at physical
    pixels and ``setDevicePixelRatio`` is set so the layer paints in
    logical coordinates.
    """

    def _make_buf_viewport(self, vp: PaleoMapViewport, buf_w: int, buf_h: int):
        return PaleoMapViewport(
            center_lng=vp.center_world[0],
            center_lat=vp.center_world[1],
            zoom=vp.zoom,
            width=buf_w,
            height=buf_h,
        )


__all__ = ["LayerPixmapCache", "PaintScheduler"]
