"""PaleoMapCanvas — composite QWidget that paints all paleo layers + chrome."""
from __future__ import annotations

import math

import numpy as np

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QResizeEvent, QWheelEvent, QContextMenuEvent, QAction
from PySide6.QtWidgets import QToolTip, QWidget, QMenu

try:
    from geoviz_well_log.renderer.pattern_engine import PatternEngine
except ImportError:  # optional: geoviz-well-log patterns extra
    PatternEngine = None  # type: ignore[misc, assignment]

from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesNode, FaciesFeature
from geoviz_paleo_map.layers.background import BackgroundLayer
from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.layers.filled_contour import FilledContourLayer
from geoviz_paleo_map.layers.legend import LegendLayer
from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
from geoviz_paleo_map.layers.title import TitleLayer
from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.topology import TopologyModel, TopologyBuilder
from geoviz_paleo_map.edit_commands import UndoManager
from geoviz_paleo_map.edit_engine import EditEngine
from geoviz_paleo_map.edit_overlay import EditOverlayLayer
from geoviz_paleo_map.paint_scheduler import PaintScheduler, LayerPixmapCache
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_paleo_map.zoom_pan import ZoomPanHandler
from geoviz_paleo_map.floating_slider import FloatingScaleSlider
from geoviz_paleo_map.locked_panel import LockedObjectsPanel


class PaleoMapCanvas(QWidget):
    polygon_hovered = Signal(str)  # facies name, "" when leave
    zoom_changed = Signal(float)   # current zoom level
    edit_mode_changed = Signal(bool)
    selection_changed = Signal(str)  # feature_id or ""

    def __init__(self, pattern_engine=None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._press_pos: QPointF | None = None

        if pattern_engine is not None:
            self._engine = pattern_engine
        elif PatternEngine is not None:
            self._engine = PatternEngine(tile_size=10)
        else:
            self._engine = None
        self._resolver = FaciesStyleResolver(self._engine)

        self._viewport = PaleoMapViewport(
            center_lng=115.0, center_lat=30.0, zoom=2.0,
            width=max(1, self.width()), height=max(1, self.height()),
        )
        self._zoom_pan = ZoomPanHandler(self._viewport)

        self._facies_layer = FaciesPolygonsLayer([], self._resolver)
        self._labels_layer = RegionLabelsLayer([], self._resolver)
        self._wells_layer = WellsScatterLayer([])
        self._title_layer = TitleLayer("")
        self._legend_layer = LegendLayer(set(), self._resolver)
        # Filled-contour overlay (Phase-2 T3). None until a caller passes
        # filled_bands to load_features / load_hierarchy; absent from the
        # layer list when None so the cache rebuild stays consistent.
        self._filled_contour_layer: FilledContourLayer | None = None

        self._layers: list[PaleoLayer] = self._compose_layers()
        self._rebuild_layer_caches()
        self._current_hover: str | None = None
        self._hierarchy: FaciesHierarchy | None = None
        self._level_groups: dict[str, list[PaleoLayer]] = {}
        self._cached_level: str = ""
        self._cached_zoom: float = -1.0

        # State fields for dynamic layers and locking
        self._period_name = ""
        self._loaded_features: list[dict] = []
        self._fit_bounds: tuple[float, float, float, float] | None = None
        self._viewport_fitted = False
        self._user_has_interacted = False
        self._wells_data: list[dict] = []
        self._locked_ids: dict[str, str] = {}
        self._current_active_level = ""

        # Floating interactive scale slider
        self._scale_slider = FloatingScaleSlider(self)
        self._scale_slider.zoom_changed.connect(self.set_zoom)

        # Floating interactive locked objects panel
        self._locked_panel = LockedObjectsPanel(self)
        self._locked_panel.unlock_requested.connect(self.toggle_lock)
        self._locked_panel.level_changed.connect(self.update_lock_level)

        # Edit mode
        self._edit_mode = False
        self._topology_model: TopologyModel | None = None
        self._edit_overlay = EditOverlayLayer()
        self._undo_mgr = UndoManager()
        self._edit_engine = EditEngine(self._edit_overlay, self._undo_mgr)

        self._scheduler = PaintScheduler(self)
        self._layer_caches: list[LayerPixmapCache] = []
        self._locked_level: str = ""

    @property
    def layers(self) -> list[PaleoLayer]:
        """Public read-only access to the composite layer list."""
        return list(self._layers)

    def _compose_layers(self) -> list[PaleoLayer]:
        """Build the ordered layer list with the filled-contour overlay.

        The filled-contour layer (if any) sits directly after the background
        so facies polygons, labels, wells, and chrome paint on top of it.
        Kept as one helper so all three composition sites (__init__,
        load_features, load_hierarchy, _update_active_layers) agree on the
        slot position - a structural gap (T3 / #247) that a per-site
        add_layer would paper over rather than fix.
        """
        stack: list[PaleoLayer] = [BackgroundLayer()]
        if self._filled_contour_layer is not None:
            stack.append(self._filled_contour_layer)
        stack.extend([
            self._facies_layer,
            self._labels_layer,
            self._wells_layer,
            self._title_layer,
            NorthArrowLayer(),
            ScaleBarLayer(),
            self._legend_layer,
        ])
        return stack

    def _rebuild_layer_caches(self) -> None:
        """Rebuild LayerPixmapCache wrappers for current layer list.

        Chrome layers (title/north-arrow/scale-bar/legend) anchor to viewport
        edges and must paint against the real viewport size; we paint them
        directly each frame instead of caching them.
        """
        self._layer_caches = [
            None if getattr(layer, "is_chrome", False) else LayerPixmapCache(layer)
            for layer in self._layers
        ]

    # --- Edit mode properties ---

    @property
    def edit_mode(self) -> bool:
        return self._edit_mode

    @edit_mode.setter
    def edit_mode(self, value: bool) -> None:
        if value == self._edit_mode:
            return
        self._edit_mode = value
        self._zoom_pan.enabled = not value
        if not value:
            self._edit_engine.select(None)
        if value and self._edit_overlay not in self._layers:
            self._layers.append(self._edit_overlay)
        elif not value and self._edit_overlay in self._layers:
            self._layers.remove(self._edit_overlay)
        self.edit_mode_changed.emit(value)
        self._scheduler.schedule()

    @property
    def topology_model(self) -> TopologyModel | None:
        return self._topology_model

    @property
    def undo_manager(self) -> UndoManager:
        return self._undo_mgr

    @property
    def edit_engine(self) -> EditEngine:
        return self._edit_engine

    def load_features(self, features: list[dict],
                      period_name: str = "",
                      wells: list[dict] | None = None,
                      filled_bands: list | None = None,
                      study_area_clip: list[tuple[float, float]] | None = None) -> None:
        """Rebuild the viewport contents from a list of GeoJSON features."""
        self._hierarchy = None
        self._level_groups = {}
        self._cached_level = ""
        self._cached_zoom = -1.0
        self._facies_layer = FaciesPolygonsLayer(features, self._resolver)
        self._labels_layer = RegionLabelsLayer(features, self._resolver)
        self._wells_layer = WellsScatterLayer(wells or [])
        # Phase-2 T3: filled-contour overlay. None when no bands are supplied,
        # which keeps it out of the layer stack entirely.
        self._filled_contour_layer = (
            FilledContourLayer(filled_bands, study_area_clip)
            if filled_bands else None
        )

        seen = set()
        for f in features:
            props = f.get("properties") or {}
            name = props.get("facies") or props.get("name")
            if name:
                seen.add(name)
        self._legend_layer.set_facies(seen)
        self._title_layer.set_text(f"{period_name}岩相古地理图" if period_name else "")

        # Replace layer instances in the list
        self._layers = self._compose_layers()
        self._period_name = period_name
        self._wells_data = wells or []
        self._locked_ids = {}
        # Build topology model for editing
        self._topology_model = TopologyBuilder.from_features(features)
        self._edit_engine.set_model(self._topology_model)
        self._update_locked_panel()
        self._rebuild_layer_caches()

        self._loaded_features = features
        self._fit_bounds = self._compute_fit_bounds()
        self._viewport_fitted = False
        self._user_has_interacted = False
        self.fit_viewport_to_data()

        self._scheduler.schedule()
        self._update_slider_params()

    def load_hierarchy(self, hierarchy: FaciesHierarchy,
                       period_name: str = "",
                       wells: list[dict] | None = None,
                       filled_bands: list | None = None,
                       study_area_clip: list[tuple[float, float]] | None = None) -> None:
        """Rebuild layers from a hierarchical facies model.

        Builds per-level layer groups so that zoom determines which level is shown.
        """
        self._hierarchy = hierarchy
        # Phase-2 T3: a single filled-contour overlay shared across all level
        # groups (bands are level-independent; re-clipping per level would
        # be wasted work). When supplied, it slots after the background in
        # every group.
        filled_layer = FilledContourLayer(filled_bands, study_area_clip) if filled_bands else None
        self._filled_contour_layer = filled_layer

        pens = {
            "facies": QPen(QColor("#1a202c"), 2.0),
            "sub_facies": QPen(QColor("#4a5568"), 1.5),
            "micro_facies": QPen(QColor("#a0aec0"), 1.0),
        }
        font_sizes = {"facies": 11, "sub_facies": 8, "micro_facies": 7}

        title = f"{period_name}岩相古地理图" if period_name else ""
        self._level_groups = {}
        all_seen: set[str] = set()

        for level in ["facies", "sub_facies", "micro_facies"]:
            feats = [
                {"type": "Feature", "properties": {
                    "facies": ff.facies_name,
                    "name": ff.display_name,
                    "id": ff.id,
                    "boundary_type": None,
                    "level": ff.level,
                }, "geometry": ff.geometry}
                for ff in hierarchy.get_features_at_level(level)
            ]
            if not feats:
                continue

            seen = {(f.get("properties") or {}).get("facies") for f in feats if (f.get("properties") or {}).get("facies")}
            all_seen.update(seen)
            poly = FaciesPolygonsLayer(feats, self._resolver, default_pen=pens[level], hierarchy=hierarchy, active_level=level, locked_ids=self._locked_ids)

            group: list[PaleoLayer] = [BackgroundLayer()]
            if filled_layer is not None:
                group.append(filled_layer)
            group.append(poly)
            group.append(RegionLabelsLayer(feats, self._resolver,
                                           font_size=font_sizes[level],
                                           locked_ids=set(self._locked_ids.keys())))
            group.append(WellsScatterLayer(wells or []))
            group.extend([
                TitleLayer(title),
                NorthArrowLayer(),
                ScaleBarLayer(),
                LegendLayer(seen, self._resolver),
            ])
            self._level_groups[level] = group

        self._cached_level = ""
        self._cached_zoom = -1.0
        level = self._resolve_level()
        self._layers = self._level_groups.get(level, [])
        self._legend_layer.set_facies(all_seen)
        self._title_layer.set_text(title)
        # Build topology model for editing
        self._topology_model = TopologyBuilder.from_hierarchy(hierarchy)
        self._edit_engine.set_model(self._topology_model)
        self._rebuild_layer_caches()

        self._loaded_features = []
        for level in ["facies", "sub_facies", "micro_facies"]:
            self._loaded_features.extend([
                {"geometry": ff.geometry}
                for ff in hierarchy.get_features_at_level(level)
            ])
        self._fit_bounds = self._compute_fit_bounds()
        self._viewport_fitted = False
        self._user_has_interacted = False
        self.fit_viewport_to_data()

        self._scheduler.schedule()
        self._update_slider_params()

    # (outgoing_level, incoming_level, blend) — blend ∈ [0,1]
    _LEVEL_ORDER = ["facies", "sub_facies", "micro_facies"]
    _SCALE_THRESHOLDS = [8_000_000.0, 4_000_000.0]  # 相→亚相 at 1:800万, 亚相→微相 at 1:400万

    def _km_per_degree(self) -> float:
        lat = self._viewport.center_world[1]
        return 111.32 * math.cos(math.radians(lat))

    def _zoom_for_scale_den(self, den: float) -> float:
        km_per_px = (den * 0.02646) / 1e5
        kpd = self._km_per_degree()
        return math.log2(kpd / km_per_px) + 1.0

    def get_threshold_zooms(self) -> list[float]:
        """Return the zoom levels at which hierarchy transitions occur."""
        return [self._zoom_for_scale_den(den) for den in self._SCALE_THRESHOLDS]

    def _resolve_level(self) -> str:
        if self._locked_level:
            return self._locked_level
        z = self._viewport.zoom
        if abs(z - self._cached_zoom) < 0.05 and self._cached_level:
            return self._cached_level
        thresholds = self.get_threshold_zooms()
        for i, thr_zoom in enumerate(thresholds):
            if z < thr_zoom:
                self._cached_level = self._LEVEL_ORDER[i]
                self._cached_zoom = z
                return self._cached_level
        last = self._LEVEL_ORDER[-1]
        self._cached_level = last
        self._cached_zoom = z
        return last

    def _sync_chrome_rects(self, viewport) -> None:
        """Feed chrome (legend/arrow/scale bar) footprints to region-label layers
        so labels avoid drawing under decorations."""
        rects = []
        for layer in self._layers:
            if getattr(layer, "is_chrome", False):
                r = layer.reserved_rect(viewport)
                if r is not None:
                    rects.append(r)
        for layer in self._layers:
            if isinstance(layer, RegionLabelsLayer):
                layer.chrome_rects = rects

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            if self._hierarchy is not None:
                current_level = self._resolve_level()
                if current_level != self._current_active_level:
                    self._current_active_level = current_level
                    self._update_active_layers()

            self._sync_chrome_rects(self._viewport)
            for layer, cache in zip(self._layers, self._layer_caches):
                if cache is None:
                    layer.paint(painter, self._viewport)
                else:
                    cache.paint(painter, self._viewport)
        finally:
            painter.end()

    @property
    def zoom(self) -> float:
        return self._viewport.zoom

    def set_zoom(self, zoom: float) -> None:
        """Set zoom level programmatically (e.g. from slider)."""
        self._user_has_interacted = True
        self._viewport.zoom = max(self._zoom_pan.min_zoom,
                                  min(self._zoom_pan.max_zoom, zoom))
        self._cached_level = ""
        self._cached_zoom = -1.0
        self.zoom_changed.emit(self._viewport.zoom)
        self._scheduler.schedule()

    def set_locked_level(self, level: str) -> None:
        """Set the global locked level ('', 'facies', 'sub_facies', 'micro_facies')."""
        if level == self._locked_level:
            return
        self._locked_level = level
        self._cached_level = ""
        self._cached_zoom = -1.0
        self._update_active_layers()
        self._scheduler.schedule()

    def _resolve_level_name(self) -> str:
        """Compatibility alias for the hysteresis-backed _resolve_level."""
        return self._resolve_level()

    def _find_active_lock_in_subtree(self, node: FaciesNode) -> tuple[str, str] | None:
        if node.feature.id in self._locked_ids:
            return node.feature.id, self._locked_ids[node.feature.id]
        for child in node.children:
            res = self._find_active_lock_in_subtree(child)
            if res is not None:
                return res
        return None

    def _find_root_node(self, feature_id: str) -> FaciesNode | None:
        if self._hierarchy is None:
            return None
        node = self._hierarchy.get_node(feature_id)
        if node is None:
            return None
        ancestors = self._hierarchy.get_ancestors(feature_id)
        if ancestors:
            root_id = ancestors[0].id
            return self._hierarchy.get_node(root_id)
        return node

    def _collect_visible_features(self, node: FaciesNode, active_level: str, out: list[FaciesFeature], effective_level: str | None = None, is_branch_locked: bool = False, active_locked_ids: set[str] | None = None) -> None:
        if effective_level is None:
            # We are at a root node. Find if there is an active lock in this root's subtree.
            lock_res = self._find_active_lock_in_subtree(node)
            if lock_res is not None:
                locked_id, lock_level = lock_res
                effective_level = lock_level
                is_branch_locked = True
            else:
                effective_level = active_level
                is_branch_locked = False

        levels = ["facies", "sub_facies", "micro_facies"]
        node_depth = levels.index(node.feature.level) if node.feature.level in levels else 0
        target_depth = levels.index(effective_level) if effective_level in levels else 0

        if node_depth < target_depth:
            if node.children:
                for child in node.children:
                    self._collect_visible_features(child, active_level, out, effective_level, is_branch_locked, active_locked_ids)
            else:
                out.append(node.feature)
                if is_branch_locked and active_locked_ids is not None:
                    active_locked_ids.add(node.feature.id)
        else:
            out.append(node.feature)
            if is_branch_locked and active_locked_ids is not None:
                active_locked_ids.add(node.feature.id)

    def _update_active_layers(self) -> None:
        """Dynamically build layers for the current active level and locked features."""
        if not self._hierarchy:
            return

        active_level = self._resolve_level()
        visible_features = []
        active_locked_ids = set()
        for root in self._hierarchy.roots:
            self._collect_visible_features(root, active_level, visible_features, active_locked_ids=active_locked_ids)

        polygon_features = list(visible_features)
        visible_ids = {feature.id for feature in polygon_features}
        for fid in self._locked_ids:
            node = self._hierarchy.get_node(fid)
            if node is not None and node.feature.level == "facies" and fid not in visible_ids:
                polygon_features.append(node.feature)
                visible_ids.add(fid)

        feats = [
            {"type": "Feature", "properties": {
                "facies": ff.facies_name,
                "name": ff.display_name,
                "id": ff.id,
                "boundary_type": None,
                "level": ff.level,
            }, "geometry": ff.geometry}
            for ff in polygon_features
        ]

        pens = {
            "facies": QPen(QColor("#1a202c"), 2.0),
            "sub_facies": QPen(QColor("#4a5568"), 1.5),
            "micro_facies": QPen(QColor("#a0aec0"), 1.0),
        }
        font_sizes = {"facies": 11, "sub_facies": 8, "micro_facies": 7}

        level = active_level
        poly = FaciesPolygonsLayer(feats, self._resolver, default_pen=pens.get(level, pens["micro_facies"]), hierarchy=self._hierarchy, active_level=active_level, locked_ids=self._locked_ids)
        labels = RegionLabelsLayer(feats, self._resolver, font_size=font_sizes.get(level, 7), locked_ids=active_locked_ids)
        
        seen = {ff.facies_name for ff in visible_features if ff.facies_name}
        title = f"{self._period_name}岩相古地理图" if self._period_name else ""
        self._legend_layer.set_facies(seen)
        self._title_layer.set_text(title)

        # Preserve the existing filled-contour overlay across level switches.
        self._facies_layer = poly
        self._labels_layer = labels
        self._wells_layer = WellsScatterLayer(self._wells_data)
        self._title_layer = TitleLayer(title)
        self._legend_layer = LegendLayer(seen, self._resolver)
        self._layers = self._compose_layers()
        self._rebuild_layer_caches()

    def _update_locked_panel(self) -> None:
        if not hasattr(self, "_locked_panel"):
            return
        
        items = []
        if self._hierarchy is not None:
            for fid in sorted(self._locked_ids.keys()):
                node = self._hierarchy.get_node(fid)
                if node is not None:
                    current_lock = self._locked_ids[fid]
                    items.append((fid, node.feature.display_name, current_lock))
        
        self._locked_panel.update_items(items)

    def toggle_lock(self, feature_id: str, lock_level: str | None = None) -> None:
        if feature_id in self._locked_ids:
            del self._locked_ids[feature_id]
        else:
            if lock_level is None:
                node = self._hierarchy.get_node(feature_id) if self._hierarchy else None
                lock_level = node.feature.level if node else "facies"
            self._locked_ids[feature_id] = lock_level
        
        if self._locked_ids and hasattr(self, "_locked_panel"):
            self._locked_panel.show()

        self._update_active_layers()
        self._update_locked_panel()
        self._scheduler.schedule()

    def update_lock_level(self, feature_id: str, new_level: str) -> None:
        if feature_id in self._locked_ids:
            self._locked_ids[feature_id] = new_level
            self._update_active_layers()
            self._update_locked_panel()
            self._scheduler.schedule()

    def _toggle_locked_panel(self) -> None:
        if hasattr(self, "_locked_panel"):
            self._locked_panel.setVisible(not self._locked_panel.isVisible())

    def _update_slider_params(self) -> None:
        if hasattr(self, "_scale_slider"):
            vp = self._viewport
            kpd = self._km_per_degree()
            self._scale_slider.set_params(vp.width, kpd, self.get_threshold_zooms())
            self._scale_slider.set_zoom(vp.zoom)

    def _compute_fit_bounds(self) -> tuple[float, float, float, float] | None:
        """Bounding box (min_lng, max_lng, min_lat, max_lat) of all vertices.

        Computed once at load time (load_features / load_hierarchy) with numpy
        and cached in ``_fit_bounds``, so fit_viewport_to_data — which runs on
        every resize — never re-walks the full vertex lists in Python.
        """
        pts: list[tuple[float, float]] = []
        for feat in self._loaded_features:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            coords = geom.get("coordinates")
            if not coords:
                continue
            if gtype == "Polygon":
                rings = coords
            elif gtype == "MultiPolygon":
                rings = [ring for poly in coords for ring in poly]
            else:
                continue
            for ring in rings:
                for pt in ring:
                    if len(pt) >= 2:
                        pts.append((pt[0], pt[1]))
        if not pts:
            return None
        arr = np.asarray(pts, dtype=float)
        lngs = arr[:, 0]
        lats = arr[:, 1]
        return (float(lngs.min()), float(lngs.max()),
                float(lats.min()), float(lats.max()))

    def fit_viewport_to_data(self) -> None:
        """Fit the viewport center and zoom to the bounding box of the loaded data."""
        if not hasattr(self, "_loaded_features") or not self._loaded_features:
            return

        w = self._viewport.width
        h = self._viewport.height
        if w <= 100 or h <= 100:
            return  # Wait for a proper resize event

        bounds = getattr(self, "_fit_bounds", None)
        if bounds is None:
            return

        from geoviz_paleo_map.projection import lnglat_to_world

        min_lng, max_lng, min_lat, max_lat = bounds

        # Add a tiny margin if range is zero
        if max_lng - min_lng < 0.01:
            max_lng += 0.005
            min_lng -= 0.005
        if max_lat - min_lat < 0.01:
            max_lat += 0.005
            min_lat -= 0.005

        center_lng = (min_lng + max_lng) / 2
        center_lat = (min_lat + max_lat) / 2

        # We want the map to completely fill the panel with no blank spaces on any side
        scale_x = w / (max_lng - min_lng)
        scale_y = h / (max_lat - min_lat)
        scale = max(scale_x, scale_y)

        # scale = 2.0 ** (zoom - 1.0)
        # zoom = log2(scale) + 1.0
        zoom = math.log2(scale) + 1.0

        # Clamp zoom to the slider/viewport limits
        zoom = max(0.1, min(10.0, zoom))

        self._viewport.center_world = lnglat_to_world(center_lng, center_lat)
        self._viewport.zoom = zoom
        self._viewport.data_bounds = (min_lng, max_lng, min_lat, max_lat)
        self._viewport_fitted = True

        self.zoom_changed.emit(zoom)
        self._update_slider_params()
        self._scheduler.schedule()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._viewport.resize(max(1, event.size().width()),
                              max(1, event.size().height()))
        if hasattr(self, "_scale_slider"):
            self._scale_slider.setGeometry(16, event.size().height() - 54 - 36, 320, 54)
            self._update_slider_params()
        if hasattr(self, "_locked_panel"):
            self._locked_panel.setGeometry(16, 16, 240, 180)

        # Only auto-fit while the user has not yet zoomed/panned; once they
        # have interacted, the viewport is theirs and a resize must not clobber it.
        if not self._user_has_interacted:
            self.fit_viewport_to_data()

        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._user_has_interacted = True
            if self._edit_mode:
                consumed = self._edit_engine.handle_mouse_press(
                    QPointF(event.position()), self._viewport, event.button())
                if consumed:
                    self.selection_changed.emit(self._edit_engine.selected_id or "")
                    self._scheduler.schedule()
                    return
            self._zoom_pan.start_drag(QPointF(event.position()))
            self._press_pos = QPointF(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = QPointF(event.position())
        if self._edit_mode:
            consumed = self._edit_engine.handle_mouse_move(pos, self._viewport)
            if consumed:
                self._scheduler.schedule()
                return
        if self._zoom_pan.is_dragging():
            self._zoom_pan.update_drag(pos)
            self._scheduler.schedule()
            return
        # Hover hit-test
        if self._hierarchy is not None:
            label = self._hierarchy_hit_test(pos)
        else:
            label = self._facies_layer.hit_test_polygon(pos, self._viewport)
        if label != self._current_hover:
            self._current_hover = label
            self.polygon_hovered.emit(label or "")
        if label:
            QToolTip.showText(event.globalPosition().toPoint(), label, self)
        else:
            QToolTip.hideText()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._edit_mode:
                cmd = self._edit_engine.handle_mouse_release(
                    QPointF(event.position()), self._viewport, event.button())
                if cmd is not None:
                    self._undo_mgr.execute(cmd, self._topology_model)
                    self._rebuild_topology_paths()
                    self._scheduler.schedule()
                return
            self._zoom_pan.end_drag()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._edit_mode and event.button() == Qt.MouseButton.LeftButton:
            cmd = self._edit_engine.handle_double_click(
                QPointF(event.position()), self._viewport)
            if cmd is not None:
                self._undo_mgr.execute(cmd, self._topology_model)
                self._rebuild_topology_paths()
                self._scheduler.schedule()

    def wheelEvent(self, event: QWheelEvent) -> None:
        self._user_has_interacted = True
        delta = event.angleDelta().y() / 120.0
        if delta == 0:
            return
        # Multiply delta by 0.15 to make scrolling zoom smooth and precise
        self._zoom_pan.wheel_zoom(QPointF(event.position()), delta_steps=delta * 0.15)
        self.zoom_changed.emit(self._viewport.zoom)
        if hasattr(self, "_scale_slider"):
            self._scale_slider.set_zoom(self._viewport.zoom)
        self._scheduler.schedule()

    def keyPressEvent(self, event) -> None:
        from PySide6.QtGui import QKeySequence
        if event.matches(QKeySequence.StandardKey.Undo):
            if self._topology_model and self._undo_mgr.undo(self._topology_model):
                self._rebuild_topology_paths()
                self._scheduler.schedule()
            return
        if event.matches(QKeySequence.StandardKey.Redo):
            if self._topology_model and self._redo():
                self._rebuild_topology_paths()
                self._scheduler.schedule()
            return
        if event.key() == Qt.Key.Key_E and not event.modifiers():
            self.edit_mode = not self.edit_mode
            return
        if event.key() == Qt.Key.Key_Delete and self._edit_mode:
            cmd = self._edit_engine.delete_selected_vertex(
                self._edit_overlay._hovered_vertex_id) if self._edit_overlay._hovered_vertex_id else None
            if cmd:
                self._undo_mgr.execute(cmd, self._topology_model)
                self._rebuild_topology_paths()
                self._scheduler.schedule()
            return
        super().keyPressEvent(event)

    def _redo(self) -> bool:
        return self._undo_mgr.redo(self._topology_model)

    def _rebuild_topology_paths(self) -> None:
        if self._topology_model is None:
            return
        dirty = self._topology_model.get_dirty_ids()
        if not dirty:
            return
        for layer in self._layers:
            if isinstance(layer, FaciesPolygonsLayer):
                layer.set_topology_model(self._topology_model)
                layer.rebuild_dirty_paths(dirty)
        self._topology_model.clear_dirty()
        # Mark affected layer caches dirty
        for i, layer in enumerate(self._layers):
            if isinstance(layer, FaciesPolygonsLayer) and i < len(self._layer_caches):
                cache = self._layer_caches[i]
                if cache is not None:
                    cache.mark_dirty()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        pos = QPointF(event.pos())
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 11px;
                color: #334155;
            }
            QMenu::item:selected {
                background-color: #f1f5f9;
                color: #0f172a;
            }
        """)

        if self._edit_mode and self._topology_model is not None:
            # Edit mode context menu
            vid = self._edit_overlay.hit_test_vertex(pos, self._viewport)
            if vid is not None:
                act_del_v = QAction("删除节点", self)
                act_del_v.triggered.connect(lambda: self._context_delete_vertex(vid))
                menu.addAction(act_del_v)
                menu.addSeparator()

            selected = self._edit_engine.selected_id
            if selected:
                act_del_p = QAction("删除多边形", self)
                act_del_p.triggered.connect(self._context_delete_polygon)
                menu.addAction(act_del_p)

                act_edit_attr = QAction("编辑属性...", self)
                act_edit_attr.triggered.connect(lambda: self._context_edit_attributes(selected))
                menu.addAction(act_edit_attr)
        else:
            # View mode context menu (existing hierarchy lock behavior)
            if self._hierarchy is None:
                menu.exec(event.globalPos())
                return

            feature_id = self._hierarchy_hit_test_id(pos)
            level_labels = {"facies": "相", "sub_facies": "亚相", "micro_facies": "微相"}

            if feature_id:
                node = self._hierarchy.get_node(feature_id)
                if node is not None:
                    root_node = self._find_root_node(feature_id)
                    active_lock_res = self._find_active_lock_in_subtree(root_node) if root_node is not None else None

                    if active_lock_res is not None:
                        locked_fid, lock_lvl = active_lock_res
                        locked_node = self._hierarchy.get_node(locked_fid)
                        if locked_node is not None:
                            display_name = locked_node.feature.display_name
                            lvl_lbl = level_labels.get(locked_node.feature.level, locked_node.feature.level)
                            act_unlock = QAction(f"解除锁定: {display_name} ({lvl_lbl})", self)
                            act_unlock.triggered.connect(lambda: self.toggle_lock(locked_fid))
                            menu.addAction(act_unlock)
                    else:
                        display_name = node.feature.display_name
                        lvl_lbl = level_labels.get(node.feature.level, node.feature.level)
                        act_lock = QAction(f"锁定层级: {display_name} ({lvl_lbl})", self)
                        act_lock.triggered.connect(lambda: self.toggle_lock(feature_id))
                        menu.addAction(act_lock)
                    menu.addSeparator()

            panel_visible = self._locked_panel.isVisible()
            act_toggle = QAction("显示锁定层级面板" if not panel_visible else "隐藏锁定层级面板", self)
            act_toggle.triggered.connect(self._toggle_locked_panel)
            menu.addAction(act_toggle)

        menu.exec(event.globalPos())

    def _context_delete_vertex(self, vid: int) -> None:
        cmd = self._edit_engine.delete_selected_vertex(vid)
        if cmd:
            self._undo_mgr.execute(cmd, self._topology_model)
            self._rebuild_topology_paths()
            self._scheduler.schedule()

    def _context_delete_polygon(self) -> None:
        cmd = self._edit_engine.delete_selected_polygon()
        if cmd:
            self._undo_mgr.execute(cmd, self._topology_model)
            self._rebuild_topology_paths()
            self.selection_changed.emit("")
            self._scheduler.schedule()

    def _context_edit_attributes(self, feature_id: str) -> None:
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox
        ref = self._topology_model.get_feature(feature_id) if self._topology_model else None
        if ref is None:
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑属性")
        form = QFormLayout(dlg)
        facies_input = QLineEdit(ref.properties.get("facies", ""))
        name_input = QLineEdit(ref.properties.get("name", ""))
        boundary_combo = QComboBox()
        boundary_combo.addItems(["无", "实测界线", "推测界线", "断层"])
        bt = ref.properties.get("boundary_type")
        boundary_combo.setCurrentText({"confirmed": "实测界线", "inferred": "推测界线", "fault": "断层"}.get(bt, "无"))
        form.addRow("相名:", facies_input)
        form.addRow("显示名:", name_input)
        form.addRow("界线类型:", boundary_combo)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        old_props = dict(ref.properties)
        new_props = dict(ref.properties)
        new_props["facies"] = facies_input.text()
        new_props["name"] = name_input.text()
        bt_map = {"实测界线": "confirmed", "推测界线": "inferred", "断层": "fault"}
        new_props["boundary_type"] = bt_map.get(boundary_combo.currentText())
        from geoviz_paleo_map.edit_commands import EditAttributesCmd
        cmd = EditAttributesCmd(feature_id, old_props, new_props)
        self._undo_mgr.execute(cmd, self._topology_model)
        self._scheduler.schedule()

    def _hierarchy_hit_test(self, pos: QPointF) -> str | None:
        """Hit-test the active level's polygon layer, return hierarchy label."""
        if not self._hierarchy or not self._layers:
            return None
        for layer in reversed(self._layers):
            if isinstance(layer, FaciesPolygonsLayer):
                feature_id = layer.hit_test_polygon(pos, self._viewport)
                if feature_id:
                    return self._hierarchy.get_hierarchy_label(feature_id)
        return None

    def _hierarchy_hit_test_id(self, pos: QPointF) -> str | None:
        """Hit-test the active level's polygon layer, return feature_id."""
        if not self._hierarchy or not self._layers:
            return None
        for layer in reversed(self._layers):
            if isinstance(layer, FaciesPolygonsLayer):
                feature_id = layer.hit_test_polygon(pos, self._viewport)
                if feature_id:
                    return feature_id
        return None
