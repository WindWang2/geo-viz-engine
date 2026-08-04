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
``FaciesPolygonsLayer``.
"""
from __future__ import annotations

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

    def set_bands(self, bands: list[BandedFill] | None) -> None:
        self._bands = list(bands or [])

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
            painter.setClipPath(clip_screen, Qt.ClipOperation.IntersectClip)

        for band in self._bands:
            color = QColor(band.color)
            color.setAlpha(180)
            painter.setBrush(QBrush(color))

            for poly_coords, offset_arr in zip(band.polygons, band.offsets):
                path = QPainterPath()
                path.setFillRule(Qt.FillRule.OddEvenFill)

                for j in range(len(offset_arr) - 1):
                    start_idx = offset_arr[j]
                    end_idx = offset_arr[j + 1]
                    ring_pts = poly_coords[start_idx:end_idx]
                    if len(ring_pts) < 3:
                        continue

                    wx, wy = lnglat_to_world(ring_pts[0][0], ring_pts[0][1])
                    sp = viewport.world_to_screen(wx, wy)
                    path.moveTo(sp)
                    for pt in ring_pts[1:]:
                        wx, wy = lnglat_to_world(pt[0], pt[1])
                        path.lineTo(viewport.world_to_screen(wx, wy))
                    path.closeSubpath()

                painter.drawPath(path)

        painter.restore()
