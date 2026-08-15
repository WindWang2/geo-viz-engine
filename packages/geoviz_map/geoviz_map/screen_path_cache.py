"""ScreenPathCache — caches screen-space QPainterPaths per zoom level."""
from __future__ import annotations

from geoviz_common.screen_path_cache import BaseScreenPathCache
from PySide6.QtGui import QPainterPath

from geoviz_map.viewport import MapViewport


class ScreenPathCache(BaseScreenPathCache):
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25).

    Entries bake the exact viewport scale and center into the transform; a
    hit is reused only when the live scale matches to within 1e-6 relative
    error, and entries are invalidated when the center pans away or the
    widget is resized (see BaseScreenPathCache).
    """

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: MapViewport) -> QPainterPath:
        return super().get_or_build(feature_id, world_path, viewport)
