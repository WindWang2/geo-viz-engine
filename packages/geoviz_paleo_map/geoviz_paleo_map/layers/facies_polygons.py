"""FaciesPolygonsLayer — per-feature filled polygons with composite brush
and boundary pen, viewport-culled, point-in-polygon hit-test."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QPixmapCache

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.models import VectorPattern
from geoviz_paleo_map.projection import lnglat_to_world
from geoviz_paleo_map.style import FaciesStyleResolver, boundary_pen
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_paleo_map.hierarchy import FaciesHierarchy
from geoviz_paleo_map.screen_path_cache import ScreenPathCache


@dataclass
class _Item:
    facies_name: str
    feature_id: str
    path: QPainterPath
    bbox: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    boundary_kind: str | None
    cache_key: str = ""
    polygons: list = None  # list[np.ndarray] of ring coords in world space (for RDP simplify)

    def __post_init__(self):
        if not self.cache_key:
            self.cache_key = self.feature_id


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
                 default_pen: QPen | None = None,
                 hierarchy: FaciesHierarchy | None = None,
                 active_level: str | None = None,
                 locked_ids: dict[str, str] | None = None):
        self._resolver = style_resolver
        self._default_pen = default_pen
        self._hierarchy = hierarchy
        self._active_level = active_level
        self._locked_ids = locked_ids or {}
        # Cache of resolved per-feature lock state: feature_id ->
        # (active_lock, locked_geometry, locked_feature_id). The resolution
        # walks the hierarchy ancestor chain (get_node + get_ancestors), which
        # is O(depth) per feature — previously recomputed for every visible
        # border on every paint tick. Keyed on id(self._locked_ids) so the
        # cache invalidates if the locked-ids dict is replaced.
        self._lock_state_cache: dict[str, tuple] = {}
        self._lock_state_key: frozenset | None = None
        self._selected_id: str | None = None
        self._topology_model = None  # set externally when edit mode is active
        self._screen_cache = ScreenPathCache()
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
            for poly_idx, poly in enumerate(rings):
                item = self._build_item(poly, facies, feature_id, boundary_kind)
                if item is not None:
                    if poly_idx > 0:
                        item.cache_key = f"{feature_id}#{poly_idx}"
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

        # Build quadtrees for each hierarchy level for borders drawing
        self._level_quadtrees: dict[str, QuadtreeNode | None] = {}
        if self._hierarchy is not None:
            for lvl in ["facies", "sub_facies", "micro_facies"]:
                lvl_items = []
                lvl_features = self._hierarchy.get_features_at_level(lvl)
                for ff in lvl_features:
                    geom = ff.geometry or {}
                    gtype = geom.get("type")
                    if gtype == "Polygon":
                        rings = [geom["coordinates"]]
                    elif gtype == "MultiPolygon":
                        rings = geom["coordinates"]
                    else:
                        continue
                    for poly_idx, poly in enumerate(rings):
                        item = self._build_item(poly, ff.facies_name, ff.id, None)
                        if item is not None:
                            if poly_idx > 0:
                                item.cache_key = f"{ff.id}#{poly_idx}"
                            lvl_items.append(item)

                if lvl_items:
                    min_x = min(item.bbox[0] for item in lvl_items)
                    min_y = min(item.bbox[1] for item in lvl_items)
                    max_x = max(item.bbox[2] for item in lvl_items)
                    max_y = max(item.bbox[3] for item in lvl_items)
                    root_node = QuadtreeNode((min_x, min_y, max_x, max_y))
                    for item in lvl_items:
                        root_node.insert(item)
                    self._level_quadtrees[lvl] = root_node
                else:
                    self._level_quadtrees[lvl] = None

    def set_selected(self, feature_id: str | None) -> None:
        self._selected_id = feature_id

    def set_topology_model(self, model) -> None:
        self._topology_model = model

    def rebuild_dirty_paths(self, feature_ids: set[str]) -> None:
        """Rebuild QPainterPaths for features whose topology has changed.

        Also refreshes the raw ring arrays the screen-path LOD builder reads
        (get_or_build ignores ``item.path`` whenever ``item.polygons`` is not
        None) and the hierarchy level-quadtree border items, so the rendered
        geometry follows the edited topology instead of the pre-edit snapshot
        (#544). Style keys (facies name / boundary kind) are refreshed from
        the model so attribute edits re-render too (#549). MultiPolygon
        parts are dispatched per part item — the whole-feature path is no
        longer stamped onto every part (#118).
        """
        if self._topology_model is None:
            return
        for fid in feature_ids:
            new_path = self._topology_model.build_path(fid)
            if new_path is None:
                continue
            ref = self._topology_model.get_feature(fid)
            facies = (
                (ref.properties.get("facies") or ref.properties.get("name") or "")
                if ref is not None
                else ""
            )
            boundary_kind = (
                ref.properties.get("boundary_type")
                if ref is not None
                else None
            )
            # Dispatch per MultiPolygon part (#118): fill/border items are
            # created one per part (constructor order), so each part item
            # must receive only its own part's rings. Stamping the
            # whole-feature path onto every part item drew the feature N
            # times (selection fade stacking 0.6^N per part) and degenerated
            # the quadtree bboxes to the whole-feature extent.
            part_artifacts = self._topology_part_artifacts(ref)
            fallback_polygons: list | None = None

            def _assign(items: list) -> None:
                nonlocal fallback_polygons
                per_part = len(items) == len(part_artifacts) and part_artifacts
                artifact_iter = iter(part_artifacts) if per_part else None
                for item in items:
                    if artifact_iter is not None:
                        item_path, item_polygons = next(artifact_iter)
                    else:
                        if fallback_polygons is None:
                            fallback_polygons = self._polygons_from_path(new_path)
                        item_path, item_polygons = new_path, fallback_polygons
                    item.path = item_path
                    item.polygons = item_polygons
                    item.facies_name = facies
                    item.boundary_kind = boundary_kind
                    br = item_path.boundingRect()
                    item.bbox = (br.left(), br.top(), br.right(), br.bottom())
                    self._screen_cache.mark_dirty(item.cache_key)

            _assign([item for item in self._items if item.feature_id == fid])
            # Hierarchy border items hold separate copies: rebuild those too.
            for tree in (self._level_quadtrees or {}).values():
                if tree is None:
                    continue
                _assign(
                    [item for item in self._walk_items(tree) if item.feature_id == fid]
                )
        has_level_items = any(
            t is not None for t in (self._level_quadtrees or {}).values()
        )
        if feature_ids and (self._items or has_level_items):
            if self._items:
                min_x = min(item.bbox[0] for item in self._items)
                min_y = min(item.bbox[1] for item in self._items)
                max_x = max(item.bbox[2] for item in self._items)
                max_y = max(item.bbox[3] for item in self._items)
                self._quadtree_root = QuadtreeNode((min_x, min_y, max_x, max_y))
                for item in self._items:
                    self._quadtree_root.insert(item)
            # Hierarchy level trees keep their pre-edit spatial partitioning:
            # items were refreshed in place above, but their bboxes moved, so
            # the old nodes cull them wrongly after pan/zoom (#853). Rebuild
            # each level tree from the (updated) items, like the fill tree.
            for lvl in list(self._level_quadtrees):
                old_tree = self._level_quadtrees[lvl]
                lvl_items = (
                    list(self._walk_items(old_tree)) if old_tree is not None else []
                )
                if not lvl_items:
                    self._level_quadtrees[lvl] = None
                    continue
                lx0 = min(item.bbox[0] for item in lvl_items)
                ly0 = min(item.bbox[1] for item in lvl_items)
                lx1 = max(item.bbox[2] for item in lvl_items)
                ly1 = max(item.bbox[3] for item in lvl_items)
                node = QuadtreeNode((lx0, ly0, lx1, ly1))
                for item in lvl_items:
                    node.insert(item)
                self._level_quadtrees[lvl] = node

    @staticmethod
    def _walk_items(node: QuadtreeNode):
        """Yield every _Item in a quadtree (used to refresh border items)."""
        yield from node.items
        for child in node.children or ():
            yield from FaciesPolygonsLayer._walk_items(child)

    def _topology_part_artifacts(self, ref) -> list[tuple[QPainterPath, list]]:
        """Build one (path, LOD rings) artifact per MultiPolygon part (#118).

        Rings are grouped by ``polygon_ring_counts`` in feature order — the
        same order the constructor creates one item per part — mirroring
        ``TopologyModel.build_path`` construction so a single-part feature's
        artifact matches the whole-feature path exactly. Rings are extracted
        via ``toSubpathPolygons`` so holes/parts stay standalone (#837).
        Empty parts are skipped; callers fall back to the whole-feature path
        when the artifact count does not match the item count.
        """
        if ref is None or self._topology_model is None:
            return []
        rings = ref.rings
        counts = list(getattr(ref, "polygon_ring_counts", None) or [])
        if (
            getattr(ref, "geometry_type", "Polygon") != "MultiPolygon"
            or not counts
            or sum(counts) != len(rings)
            or any(c <= 0 for c in counts)
        ):
            counts = [len(rings)]
        artifacts: list[tuple[QPainterPath, list]] = []
        offset = 0
        for count in counts:
            path = QPainterPath()
            for ring in rings[offset:offset + count]:
                ids = ring.vertex_ids
                if len(ids) < 3:
                    continue
                first = self._topology_model.get_vertex(ids[0])
                if first is None:
                    continue
                path.moveTo(QPointF(first.x, first.y))
                for vid in ids[1:]:
                    v = self._topology_model.get_vertex(vid)
                    if v is not None:
                        path.lineTo(QPointF(v.x, v.y))
                path.closeSubpath()
            offset += count
            if path.isEmpty():
                continue
            path.setFillRule(Qt.FillRule.OddEvenFill)
            artifacts.append((path, self._polygons_from_path(path)))
        return artifacts

    @staticmethod
    def _polygons_from_path(path: QPainterPath) -> list:
        """Extract standalone rings (one per subpath) as world-space arrays.

        ``toSubpathPolygons`` keeps one polygon per ring — unlike
        ``toFillPolygons``, which would join holes/parts with fake
        connector edges (#837).
        """
        polygons = []
        for ring in path.toSubpathPolygons():
            pts = np.array([(pt.x(), pt.y()) for pt in ring], dtype=np.float64)
            if len(pts) >= 2:
                polygons.append(pts)
        return polygons

    @staticmethod
    def _build_item(poly: list[list[list[float]]],
                    facies_name: str,
                    feature_id: str,
                    boundary_kind: str | None) -> _Item | None:
        import numpy as np
        from geoviz_paleo_map.projection import lnglat_to_world
        path = QPainterPath()
        min_x = float("inf"); min_y = float("inf")
        max_x = float("-inf"); max_y = float("-inf")
        pts_array: list = []
        for ring in poly:
            if not ring:
                continue
            ring_world = np.array([lnglat_to_world(p[0], p[1]) for p in ring])
            pts_array.append(ring_world)
            xs = ring_world[:, 0]; ys = ring_world[:, 1]
            min_x = min(min_x, xs.min()); max_x = max(max_x, xs.max())
            min_y = min(min_y, ys.min()); max_y = max(max_y, ys.max())
            path.moveTo(QPointF(ring_world[0, 0], ring_world[0, 1]))
            for i in range(1, len(ring_world)):
                path.lineTo(QPointF(ring_world[i, 0], ring_world[i, 1]))
            path.closeSubpath()
        if path.isEmpty():
            return None
        path.setFillRule(Qt.FillRule.OddEvenFill)
        return _Item(facies_name=facies_name, feature_id=feature_id, path=path,
                      bbox=(min_x, min_y, max_x, max_y),
                      boundary_kind=boundary_kind,
                      polygons=pts_array)

    @staticmethod
    def _bbox_overlaps(a, b) -> bool:
        return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])

    @staticmethod
    def _vector_tile_pixmap(vp: VectorPattern, tile: float, dpr: float) -> QPixmap:
        """Pre-render the vector pattern QPicture into a square QPixmap tile.

        The picture records a 32×32 viewBox; played at ``tile / 32`` it spans
        ``tile`` logical pixels, of which the pixmap keeps the integer part
        (matching the old per-cell playback, which effectively clipped at the
        cell boundary). Rendered once per (picture, tile, dpr) and cached in
        the app-global QPixmapCache so painting never replays the QPicture.
        """
        tile_px = int(tile)
        # Keyed on the stable pattern_id (never id(picture)): a canvas rebuild
        # constructs a fresh QPicture that can reuse a freed id, so an id-based
        # key would return the previous pattern's tile from the process-global
        # QPixmapCache (#853). tile_px/tile/dpr fully determine the rendered
        # pixmap; pattern_id disambiguates the picture content.
        pattern_key = vp.pattern_id if vp.pattern_id is not None else "none"
        key = f"geoviz_facies_tile:{pattern_key}:{tile_px}:{round(tile, 2)}:{dpr}"
        pm = QPixmap()
        if QPixmapCache.find(key, pm):
            return pm
        size = max(1, round(tile_px * dpr))
        pm = QPixmap(size, size)
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.scale(tile / 32, tile / 32)
        vp.picture.play(p)
        p.end()
        QPixmapCache.insert(key, pm)
        return pm

    def _draw_vector_fill(self, painter: QPainter, screen_path: QPainterPath,
                          vp: VectorPattern, viewport_scale: float,
                          opacity: float = 1.0) -> None:
        """Fill a screen-space path with a tiled vector pattern.

        The tile grows with the square root of the viewport scale so the grain
        stays visually stable across zoom levels, clipped to the path. The
        QPicture is pre-rendered once into a cached QPixmap tile and the fill
        is a single ``drawTiledPixmap`` call (instead of replaying the picture
        per tile cell, which was a double loop over every visible polygon).
        """
        import math
        painter.fillPath(screen_path, vp.base_color)
        painter.save()
        painter.setClipPath(screen_path, Qt.ClipOperation.IntersectClip)
        grain_scale = math.sqrt(max(1e-06, viewport_scale))
        tile = max(2, vp.tile_size * grain_scale)
        dpr = painter.device().devicePixelRatioF()
        tile_pm = self._vector_tile_pixmap(vp, tile, dpr)
        painter.setOpacity(vp.alpha * opacity)
        bbox = screen_path.boundingRect()
        # Keep the old grid phase: first cell at int(bbox.topLeft() / tile) * tile.
        start_x = int(int(bbox.left() / tile) * tile)
        start_y = int(int(bbox.top() / tile) * tile)
        # drawTiledPixmap anchors the tile grid at rect.topLeft() - offset.
        offset = QPointF(bbox.left() - start_x, bbox.top() - start_y)
        painter.drawTiledPixmap(bbox, tile_pm, offset)
        painter.restore()

    def _resolve_lock_state(self, feature_id: str) -> tuple:
        """Resolve the lock state for a feature, using a per-frame cache.

        Returns ``(active_lock, locked_geometry, locked_feature_id)``. The
        ancestor-chain walk (get_node + get_ancestors) is O(depth) and was
        previously executed for every visible border on every paint tick;
        cached here keyed on a snapshot of the locked-ids dict so it
        recomputes only when the lock state actually changes. Keying on
        id(self._locked_ids) was unsafe — canvas mutates the dict in place
        (del/[fid]=), which doesn't change the id, so the cache never
        invalidated.
        """
        lock_snapshot = frozenset(self._locked_ids.items())
        if self._lock_state_key != lock_snapshot:
            self._lock_state_cache.clear()
            self._lock_state_key = lock_snapshot
        cached = self._lock_state_cache.get(feature_id)
        if cached is not None:
            return cached
        active_lock = None
        locked_geometry = False
        locked_feature_id = None
        if self._hierarchy is not None and self._locked_ids:
            node = self._hierarchy.get_node(feature_id)
            if node is not None:
                ancestors = self._hierarchy.get_ancestors(feature_id)
                chain = ancestors + [node.feature]
                for f in chain:
                    if f.id in self._locked_ids:
                        active_lock = self._locked_ids[f.id]
                        locked_geometry = True
                        locked_feature_id = f.id
                        break
        result = (active_lock, locked_geometry, locked_feature_id)
        self._lock_state_cache[feature_id] = result
        return result

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        vp_bbox = viewport.world_bbox()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.save()

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

        # 3. Draw visible polygons FILLS ONLY (screen-space paths)
        has_selection = self._selected_id is not None
        for (facies_name, boundary_kind), items in groups.items():
            vp = self._resolver.get_vector_pattern(facies_name)
            if vp is not None:
                # Tiled vector-pattern fill (grain stable across zoom)
                for item in items:
                    screen_path = self._screen_cache.get_or_build(
                        item.cache_key, item.path, viewport, item.polygons)
                    if has_selection and item.feature_id != self._selected_id:
                        opacity = 0.6
                    else:
                        opacity = 1.0
                    self._draw_vector_fill(painter, screen_path, vp, viewport.scale, opacity)
            else:
                # Flat / composite brush fill
                brush = self._resolver.get_adaptive_brush(facies_name, viewport.scale)
                painter.setPen(QPen(Qt.PenStyle.NoPen))
                painter.setBrush(brush)
                for item in items:
                    screen_path = self._screen_cache.get_or_build(
                        item.cache_key, item.path, viewport, item.polygons)
                    if has_selection and item.feature_id != self._selected_id:
                        painter.setOpacity(0.6)
                        painter.drawPath(screen_path)
                        painter.setOpacity(1.0)
                    else:
                        painter.drawPath(screen_path)

        # 3b. Draw selection glow
        if has_selection:
            for item in visible_items:
                if item.feature_id == self._selected_id:
                    glow_pen = QPen(QColor("#3182ce"), 3.0)
                    glow_pen.setCosmetic(True)
                    painter.setPen(glow_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    screen_path = self._screen_cache.get_or_build(
                        item.cache_key, item.path, viewport, item.polygons)
                    painter.drawPath(screen_path)
                    break

        # 4. Draw hierarchical borders
        if self._hierarchy is not None and self._active_level is not None:
            levels_order = ["facies", "sub_facies", "micro_facies"]
            max_depth = levels_order.index(self._active_level) if self._active_level in levels_order else 0

            for locked_lvl in self._locked_ids.values():
                if locked_lvl in levels_order:
                    depth = levels_order.index(locked_lvl)
                    if depth > max_depth:
                        max_depth = depth

            all_levels = levels_order[:max_depth + 1]
            draw_levels = [lvl for lvl in ["micro_facies", "sub_facies", "facies"] if lvl in all_levels]

            border_pens = {
                "facies": QPen(QColor("#1a202c"), 2.0),
                "sub_facies": QPen(QColor("#4a5568"), 1.5),
                "micro_facies": QPen(QColor("#a0aec0"), 1.0),
            }

            for lvl in draw_levels:
                pen = border_pens[lvl]
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)

                visible_borders = []
                root_node = self._level_quadtrees.get(lvl)
                if root_node is not None:
                    root_node.query(vp_bbox, visible_borders)
                else:
                    visible_borders = []

                for border_item in visible_borders:
                    active_lock, locked_geometry, locked_feature_id = self._resolve_lock_state(
                        border_item.feature_id
                    )
                    active_lock_depth = 0

                    levels = ["facies", "sub_facies", "micro_facies"]
                    active_depth = levels.index(self._active_level) if self._active_level in levels else 0
                    lvl_depth = levels.index(lvl) if lvl in levels else 0

                    if active_lock is not None:
                        active_lock_depth = levels.index(active_lock) if active_lock in levels else 0

                    if lvl_depth > active_depth:
                        if active_lock is None or lvl_depth > active_lock_depth:
                            continue

                    is_faded = False
                    if active_lock is not None and lvl_depth > active_lock_depth:
                        is_faded = True

                    screen_border = self._screen_cache.get_or_build(
                        border_item.cache_key, border_item.path, viewport)
                    # Highlight the locked feature's OWN boundary (bold + red),
                    # whatever its level (相/亚相/微相) — match the border drawn
                    # for the locked feature itself, not only the top facies level.
                    is_locked_border = (locked_geometry
                                        and border_item.feature_id == locked_feature_id
                                        and not is_faded)
                    if is_locked_border:
                        painter.drawPath(screen_border)
                        locked_pen = QPen(QColor("#dc2626"), max(3.0, pen.widthF() + 1.4))
                        locked_pen.setCosmetic(True)
                        painter.setPen(locked_pen)
                        painter.drawPath(screen_border)
                        painter.setPen(pen)
                    elif is_faded:
                        faded_pen = QPen(pen)
                        color = faded_pen.color()
                        color.setAlpha(45)
                        faded_pen.setColor(color)
                        faded_pen.setWidthF(0.7)
                        painter.setPen(faded_pen)
                        painter.drawPath(screen_border)
                        painter.setPen(pen)
                    else:
                        painter.drawPath(screen_border)
        else:
            # Simple fallback (non-hierarchical)
            for (facies_name, boundary_kind), items in groups.items():
                style = self._resolver.resolve(facies_name)
                if self._default_pen is not None:
                    pen = QPen(self._default_pen)
                else:
                    pen = boundary_pen(boundary_kind)
                pen.setCosmetic(True)
                painter.setPen(pen)
                vp = self._resolver.get_vector_pattern(facies_name)
                if vp is not None:
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    for item in items:
                        screen_path = self._screen_cache.get_or_build(
                            item.cache_key, item.path, viewport)
                        self._draw_vector_fill(painter, screen_path, vp, viewport.scale)
                        painter.setPen(pen)
                        painter.drawPath(screen_path)
                else:
                    painter.setBrush(style.brush)
                    for item in items:
                        screen_path = self._screen_cache.get_or_build(
                            item.cache_key, item.path, viewport)
                        painter.drawPath(screen_path)

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
