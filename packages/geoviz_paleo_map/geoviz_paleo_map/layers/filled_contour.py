"""FilledContourLayer - banded filled-contour polygons painted under the
facies polygons / labels / wells stack.

Phase-2, T3 / #247. Consumes ``list[BandedFill]`` produced by
``geoviz_plots.surface.marching_squares.extract_filled_contours`` (each band
carries its own resolved ``color`` and packed ``polygons``/``offsets``).
Bands are drawn in ascending level order with ``Qt.OddEvenFill`` so
holes/inner rings punch out correctly. When ``study_area_clip`` is provided
the painter is clipped to that polygon (the bands themselves are already
clipped by ``extract_filled_contours`` when shapely is available; this is a
belt-and-suspenders guard for the no-shapely fallback path).

Grid coordinates are mapped to world via the Plate Carrée identity
(``lnglat_to_world``) and then to screen pixels via the viewport, matching
``FaciesPolygonsLayer``. The world->screen transform is numpy-vectorized
over each ring and the resulting screen-space ``QPainterPath`` lists are
cached on the exact viewport key, so unchanged repaints reuse them instead
of re-transforming every vertex (Issue #53).
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush, QPolygonF

from geoviz_plots.surface.marching_squares import BandedFill
from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.projection import lnglat_to_world
from geoviz_paleo_map.viewport import PaleoMapViewport


class FilledContourLayer(PaleoLayer):
    """Paints ``list[BandedFill]`` as stacked, odd-even-filled color bands."""

    # Filled contours are data, not chrome - they go through LayerPixmapCache
    # like FaciesPolygonsLayer.
    is_chrome: bool = False

    def __init__(
        self,
        bands: list[BandedFill] | None = None,
        study_area_clip: list[tuple[float, float]] | None = None,
    ) -> None:
        self._bands: list[BandedFill] = list(bands or [])
        # Clip polygon in world (lng/lat) coordinates. Stored as a QPointF
        # list so paint() can build a QPolygonF without re-converting.
        self._study_area_clip: list[QPointF] | None = None
        if study_area_clip:
            self._study_area_clip = [
                QPointF(*lnglat_to_world(lng, lat))
                for lng, lat in study_area_clip
            ]
        # Single-entry screen-path cache; see _screen_paths(). The key bakes
        # in id(self._bands), so set_bands() must reset it (Issue #53).
        self._cache_key: tuple | None = None
        self._cache_bands: list[BandedFill] | None = None
        self._cache_items: list[tuple[BandedFill, list[QPainterPath]]] | None = None

    def set_bands(self, bands: list[BandedFill] | None) -> None:
        self._bands = list(bands or [])
        # Bands replaced: invalidate the cached screen paths.
        self._cache_key = None
        self._cache_bands = None
        self._cache_items = None

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if not self._bands:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        # Optional clip to study area (world coords -> screen).
        if self._study_area_clip:
            clip_screen = QPolygonF([viewport.world_to_screen(p.x(), p.y())
                                     for p in self._study_area_clip])
            # setClipPath only accepts a QPainterPath; a bare QPolygonF has no
            # implicit conversion and the first paint raised a TypeError (#853).
            clip_path = QPainterPath()
            clip_path.addPolygon(clip_screen)
            painter.setClipPath(clip_path, Qt.ClipOperation.IntersectClip)

        for band, paths in self._screen_paths(viewport):
            color = QColor(band.color)
            color.setAlpha(180)
            painter.setBrush(QBrush(color))

            for path in paths:
                painter.drawPath(path)

        painter.restore()

    def _screen_paths(self, viewport: PaleoMapViewport
                      ) -> list[tuple[BandedFill, list[QPainterPath]]]:
        """Bands with ready-to-draw screen-space paths for ``viewport``.

        Exact-match cache keyed on ``(id(self._bands), viewport.scale,
        viewport.center_world, viewport.width, viewport.height)`` - those five
        values fully determine the world->screen transform, so a hit reuses
        the very same QPainterPath objects instead of re-transforming every
        vertex. ``set_bands()`` replaces the list (new id) and clears the
        entry; the bands list is also retained by reference so an id collision
        after garbage collection can never serve a stale hit. Bands whose
        world-space bbox misses ``viewport.world_bbox()`` are culled before
        any path building.
        """
        key = (id(self._bands), viewport.scale, viewport.center_world,
               viewport.width, viewport.height)
        if (self._cache_key == key and self._cache_bands is self._bands
                and self._cache_items is not None):
            return self._cache_items

        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2.0
        oy = viewport.height / 2.0
        w_min_x, w_min_y, w_max_x, w_max_y = viewport.world_bbox()

        items: list[tuple[BandedFill, list[QPainterPath]]] = []
        for band in self._bands:
            # Coarse band-level culling: nothing of the band can be on screen
            # when its world bbox does not intersect the visible rect.
            band_min = np.array([np.inf, np.inf])
            band_max = np.array([-np.inf, -np.inf])
            for coords in band.polygons:
                if coords.size:
                    band_min = np.minimum(band_min, coords.min(axis=0))
                    band_max = np.maximum(band_max, coords.max(axis=0))
            if (band_max[0] < w_min_x or band_min[0] > w_max_x
                    or band_max[1] < w_min_y or band_min[1] > w_max_y):
                continue

            paths: list[QPainterPath] = []
            for poly_coords, offset_arr in zip(band.polygons, band.offsets):
                # Vectorized world->screen transform (Plate Carrée identity,
                # so this one pass subsumes lnglat_to_world + world_to_screen).
                screen = np.empty_like(poly_coords, dtype=np.float64)
                screen[:, 0] = (poly_coords[:, 0] - cx) * s + ox
                screen[:, 1] = (cy - poly_coords[:, 1]) * s + oy

                path = QPainterPath()
                path.setFillRule(Qt.FillRule.OddEvenFill)
                for j in range(len(offset_arr) - 1):
                    ring = screen[offset_arr[j]:offset_arr[j + 1]]
                    if len(ring) < 3:
                        continue
                    path.addPolygon(QPolygonF(
                        [QPointF(x, y) for x, y in ring]))
                if not path.isEmpty():
                    paths.append(path)
            if paths:
                items.append((band, paths))

        self._cache_key = key
        self._cache_bands = self._bands
        self._cache_items = items
        return items
