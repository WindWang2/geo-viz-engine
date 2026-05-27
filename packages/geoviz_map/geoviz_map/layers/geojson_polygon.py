"""GeoJsonPolygonLayer — fill + stroke for Polygon / MultiPolygon features.

Builds a single QPainterPath per feature at init time (in world coords),
then transforms to screen at paint time. Skips features whose world bbox
is entirely outside the viewport.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.projection import lnglat_to_world
from geoviz_map.viewport import MapViewport


FeatureFilter = Callable[[dict], bool]


class GeoJsonPolygonLayer(MapLayer):
    def __init__(self, geojson: dict,
                 fill_color: str,
                 border_color: str,
                 border_width: float,
                 feature_filter: FeatureFilter | None = None):
        self.fill_color = QColor(fill_color)
        self.border_color = QColor(border_color)
        self.border_width = border_width
        # Per-feature: (world_path, world_bbox)
        self._features: list[tuple[QPainterPath, tuple[float, float, float, float]]] = []
        for feat in geojson.get("features", []):
            if feature_filter is not None and not feature_filter(feat.get("properties", {})):
                continue
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                rings = geom["coordinates"]
            else:
                continue
            for poly in rings:
                path, bbox = self._build_path(poly)
                if path is not None:
                    self._features.append((path, bbox))

    @staticmethod
    def _build_path(poly: list[list[list[float]]]) -> tuple[QPainterPath | None,
                                                            tuple[float, float, float, float]]:
        """Build a QPainterPath for one Polygon (outer ring + inner rings)."""
        path = QPainterPath()
        min_x = float("inf")
        min_y = float("inf")
        max_x = float("-inf")
        max_y = float("-inf")
        for ring in poly:
            if not ring:
                continue
            world_pts: list[QPointF] = []
            for lng, lat in ring:
                lat_c = max(-85.05112878, min(85.05112878, lat))
                x, y = lnglat_to_world(lng, lat_c)
                world_pts.append(QPointF(x, y))
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
            if not world_pts:
                continue
            path.moveTo(world_pts[0])
            for p in world_pts[1:]:
                path.lineTo(p)
            path.closeSubpath()
        if path.isEmpty():
            return None, (0, 0, 0, 0)
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return path, (min_x, min_y, max_x, max_y)

    @staticmethod
    def _bbox_overlaps(a: tuple[float, float, float, float],
                       b: tuple[float, float, float, float]) -> bool:
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        vp_bbox = viewport.world_bbox()
        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2
        oy = viewport.height / 2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()
        # Build a transform: world (x,y) → screen
        # sx = (x - cx) * s + ox
        # sy = (cy - y) * s + oy   (y flipped)
        # Equivalent: translate(ox, oy); scale(s, -s); translate(-cx, -cy)
        painter.translate(ox, oy)
        painter.scale(s, -s)
        painter.translate(-cx, -cy)

        pen = QPen(self.border_color, self.border_width)
        pen.setCosmetic(True)  # width stays constant in screen pixels
        painter.setPen(pen)
        painter.setBrush(self.fill_color)

        for path, bbox in self._features:
            if not self._bbox_overlaps(vp_bbox, bbox):
                continue
            painter.drawPath(path)

        painter.restore()
