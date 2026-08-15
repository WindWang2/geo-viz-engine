"""ScreenPathCache — caches screen-space QPainterPaths per zoom level."""
from __future__ import annotations

import numpy as np
from geoviz_common.screen_path_cache import BaseScreenPathCache
from PySide6.QtGui import QPainterPath

from geoviz_paleo_map.viewport import PaleoMapViewport


class ScreenPathCache(BaseScreenPathCache):
    """Cache screen-space QPainterPaths per zoom level (rounded to 0.25).

    PaleoMap variant: when raw polygon rings are passed to ``get_or_build``,
    builds an RDP-simplified LOD path (0.5px tolerance in world space) for
    dense vector layers instead of transforming a pre-built world path.
    """

    def __init__(self, max_levels: int = 4):
        super().__init__(max_levels)
        self._lod_polygons: list[np.ndarray] | None = None

    def get_or_build(self, feature_id: str, world_path: QPainterPath,
                     viewport: PaleoMapViewport,
                     polygons: list[np.ndarray] | None = None) -> QPainterPath:
        """Return screen-space path, building if needed.
        If polygons are provided, applies RDP simplification based on zoom level."""
        self._lod_polygons = polygons
        return super().get_or_build(feature_id, world_path, viewport)

    def _build_screen_path(self, feature_id: str, world_path: QPainterPath,
                           viewport: PaleoMapViewport) -> QPainterPath:
        if self._lod_polygons is not None:
            return self._build_lod_path(self._lod_polygons, viewport)
        return super()._build_screen_path(feature_id, world_path, viewport)

    def _build_lod_path(self, polygons: list[np.ndarray],
                        vp: PaleoMapViewport) -> QPainterPath:
        from PySide6.QtCore import QPointF, Qt

        from geoviz_paleo_map.lod import rdp_simplify

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
