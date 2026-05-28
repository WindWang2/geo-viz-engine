"""FaciesPolygonsLayer — per-feature filled polygons with composite brush
and boundary pen, viewport-culled, point-in-polygon hit-test."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainter, QPainterPath, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.projection import lnglat_to_world
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_paleo_map.viewport import PaleoMapViewport


@dataclass
class _Item:
    facies_name: str
    feature_id: str
    path: QPainterPath
    bbox: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    boundary_kind: str | None


class QuadtreeNode:
    """A spatial index tree node to query items overlapping a viewport bounding box."""

    def __init__(self, bbox: tuple[float, float, float, float], depth: int = 0, max_depth: int = 6):
        self.bbox = bbox  # (min_x, min_y, max_x, max_y)
        self.depth = depth
        self.max_depth = max_depth
        self.items: list[_Item] = []
        self.children: list[QuadtreeNode] | None = None

    def subdivide(self) -> None:
        min_x, min_y, max_x, max_y = self.bbox
        mid_x = (min_x + max_x) / 2
        mid_y = (min_y + max_y) / 2
        self.children = [
            QuadtreeNode((min_x, min_y, mid_x, mid_y), self.depth + 1, self.max_depth),  # SW
            QuadtreeNode((mid_x, min_y, max_x, mid_y), self.depth + 1, self.max_depth),  # SE
            QuadtreeNode((min_x, mid_y, mid_x, max_y), self.depth + 1, self.max_depth),  # NW
            QuadtreeNode((mid_x, mid_y, max_x, max_y), self.depth + 1, self.max_depth),  # NE
        ]
        # Distribute current items into child nodes if they fit entirely
        remaining_items = []
        for item in self.items:
            if not self._insert_into_children(item):
                remaining_items.append(item)
        self.items = remaining_items

    def _insert_into_children(self, item: _Item) -> bool:
        if self.children is None:
            return False
        for child in self.children:
            if child._contains_bbox(item.bbox):
                child.insert(item)
                return True
        return False

    def _contains_bbox(self, other: tuple[float, float, float, float]) -> bool:
        return (self.bbox[0] <= other[0] and other[2] <= self.bbox[2] and
                self.bbox[1] <= other[1] and other[3] <= self.bbox[3])

    def insert(self, item: _Item) -> None:
        if self.children is not None:
            if self._insert_into_children(item):
                return
            self.items.append(item)
            return

        self.items.append(item)
        # Split node if threshold exceeded and max depth not reached
        if len(self.items) > 32 and self.depth < self.max_depth:
            self.subdivide()

    def query(self, vp_bbox: tuple[float, float, float, float], out: list[_Item]) -> None:
        if not self._overlaps_bbox(vp_bbox):
            return

        # Check items in this node
        for item in self.items:
            if self._overlaps(vp_bbox, item.bbox):
                out.append(item)

        # Recurse children
        if self.children is not None:
            for child in self.children:
                child.query(vp_bbox, out)

    def _overlaps_bbox(self, other: tuple[float, float, float, float]) -> bool:
        return self._overlaps(self.bbox, other)

    @staticmethod
    def _overlaps(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


class FaciesPolygonsLayer(PaleoLayer):
    def __init__(self, features: list[dict], style_resolver: FaciesStyleResolver,
                 default_pen: QPen | None = None):
        self._resolver = style_resolver
        self._default_pen = default_pen
        self._items: list[_Item] = []
        for feat in features:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                rings = geom["coordinates"]
            else:
                continue
            props = feat.get("properties") or {}
            facies = props.get("facies") or props.get("name") or ""
            feature_id = props.get("id", "")
            boundary_kind = props.get("boundary_type")
            for poly in rings:
                item = self._build_item(poly, facies, feature_id, boundary_kind)
                if item is not None:
                    self._items.append(item)

        # Build Quadtree Spatial Index for fast viewport culling
        if self._items:
            min_x = min(item.bbox[0] for item in self._items)
            min_y = min(item.bbox[1] for item in self._items)
            max_x = max(item.bbox[2] for item in self._items)
            max_y = max(item.bbox[3] for item in self._items)
            self._quadtree_root: QuadtreeNode | None = QuadtreeNode((min_x, min_y, max_x, max_y))
            for item in self._items:
                self._quadtree_root.insert(item)
        else:
            self._quadtree_root = None

    @staticmethod
    def _build_item(poly: list[list[list[float]]],
                    facies_name: str,
                    feature_id: str,
                    boundary_kind: str | None) -> _Item | None:
        path = QPainterPath()
        min_x = float("inf"); min_y = float("inf")
        max_x = float("-inf"); max_y = float("-inf")
        for ring in poly:
            if not ring:
                continue
            pts: list[QPointF] = []
            for lng, lat in ring:
                x, y = lnglat_to_world(lng, lat)
                pts.append(QPointF(x, y))
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
            if not pts:
                continue
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
            path.closeSubpath()
        if path.isEmpty():
            return None
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return _Item(facies_name=facies_name, feature_id=feature_id, path=path,
                      bbox=(min_x, min_y, max_x, max_y),
                      boundary_kind=boundary_kind)

    @staticmethod
    def _bbox_overlaps(a, b) -> bool:
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        vp_bbox = viewport.world_bbox()
        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2
        oy = viewport.height / 2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()
        painter.translate(ox, oy)
        painter.scale(s, -s)
        painter.translate(-cx, -cy)

        # 1. Spatial Index query for visible items
        visible_items: list[_Item] = []
        if self._quadtree_root is not None:
            self._quadtree_root.query(vp_bbox, visible_items)
        else:
            visible_items = [item for item in self._items if self._bbox_overlaps(vp_bbox, item.bbox)]

        # 2. Style Batching grouping
        groups: dict[tuple[str, str | None], list[_Item]] = {}
        for item in visible_items:
            key = (item.facies_name, item.boundary_kind)
            groups.setdefault(key, []).append(item)

        # 3. Draw visible polygons sorted by styles to minimize painter context changes
        for (facies_name, boundary_kind), items in groups.items():
            style = self._resolver.resolve(facies_name)
            if self._default_pen is not None:
                pen = QPen(self._default_pen)
            else:
                pen = boundary_pen(boundary_kind)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.setBrush(style.brush)
            for item in items:
                painter.drawPath(item.path)

        painter.restore()

    def hit_test_polygon(self, screen_pt: QPointF,
                          viewport: PaleoMapViewport) -> str | None:
        """Returns the feature_id of the first polygon containing the point."""
        wx, wy = viewport.screen_to_world(screen_pt)
        world_pt = QPointF(wx, wy)
        pt_bbox = (wx, wy, wx, wy)

        # Spatial query candidate polygons
        candidates: list[_Item] = []
        if self._quadtree_root is not None:
            self._quadtree_root.query(pt_bbox, candidates)
        else:
            candidates = self._items

        for item in candidates:
            # BBox overlap pre-check is extremely cheap
            if not (item.bbox[0] <= wx <= item.bbox[2] and item.bbox[1] <= wy <= item.bbox[3]):
                continue
            if item.path.contains(world_pt):
                return item.feature_id or item.facies_name
        return None
