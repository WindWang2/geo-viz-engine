"""PaleoMapCanvas — composite QWidget that paints all paleo layers + chrome."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen, QResizeEvent, QWheelEvent, QContextMenuEvent, QAction
from PySide6.QtWidgets import QToolTip, QWidget, QMenu

from geoviz_well_log.renderer.pattern_engine import PatternEngine

from geoviz_paleo_map.hierarchy import FaciesHierarchy, FaciesNode, FaciesFeature
from geoviz_paleo_map.layers.background import BackgroundLayer
from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.layers.facies_polygons import FaciesPolygonsLayer
from geoviz_paleo_map.layers.legend import LegendLayer
from geoviz_paleo_map.layers.north_arrow import NorthArrowLayer
from geoviz_paleo_map.layers.region_labels import RegionLabelsLayer
from geoviz_paleo_map.layers.scale_bar import ScaleBarLayer
from geoviz_paleo_map.layers.title import TitleLayer
from geoviz_paleo_map.layers.wells_scatter import WellsScatterLayer
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport
from geoviz_paleo_map.zoom_pan import ZoomPanHandler
from geoviz_paleo_map.floating_slider import FloatingScaleSlider
from geoviz_paleo_map.locked_panel import LockedObjectsPanel


class PaleoMapCanvas(QWidget):
    polygon_hovered = Signal(str)  # facies name, "" when leave
    zoom_changed = Signal(float)   # current zoom level

    def __init__(self, pattern_engine: PatternEngine | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._press_pos: QPointF | None = None

        self._engine = pattern_engine or PatternEngine()
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

        self._layers: list[PaleoLayer] = [
            BackgroundLayer(),
            self._facies_layer,
            self._labels_layer,
            self._wells_layer,
            self._title_layer,
            NorthArrowLayer(),
            ScaleBarLayer(),
            self._legend_layer,
        ]
        self._current_hover: str | None = None
        self._hierarchy: FaciesHierarchy | None = None
        self._level_groups: dict[str, list[PaleoLayer]] = {}
        self._cached_level: str = ""
        self._cached_zoom: float = -1.0

        # State fields for dynamic layers and locking
        self._period_name = ""
        self._wells_data: list[dict] = []
        self._locked_ids: set[str] = set()
        self._current_active_level = ""

        # Floating interactive scale slider
        self._scale_slider = FloatingScaleSlider(self)
        self._scale_slider.zoom_changed.connect(self.set_zoom)

        # Floating interactive locked objects panel
        self._locked_panel = LockedObjectsPanel(self)
        self._locked_panel.unlock_requested.connect(self.toggle_lock)

    def load_features(self, features: list[dict],
                      period_name: str = "",
                      wells: list[dict] | None = None) -> None:
        """Rebuild the viewport contents from a list of GeoJSON features."""
        self._hierarchy = None
        self._level_groups = {}
        self._cached_level = ""
        self._cached_zoom = -1.0
        self._facies_layer = FaciesPolygonsLayer(features, self._resolver)
        self._labels_layer = RegionLabelsLayer(features, self._resolver)
        self._wells_layer = WellsScatterLayer(wells or [])

        seen = set()
        for f in features:
            props = f.get("properties") or {}
            name = props.get("facies") or props.get("name")
            if name:
                seen.add(name)
        self._legend_layer.set_facies(seen)
        self._title_layer.set_text(f"{period_name}岩相古地理图" if period_name else "")

        # Replace layer instances in the list
        self._layers = [
            BackgroundLayer(),
            self._facies_layer,
            self._labels_layer,
            self._wells_layer,
            self._title_layer,
            NorthArrowLayer(),
            ScaleBarLayer(),
            self._legend_layer,
        ]
        self._period_name = period_name
        self._wells_data = wells or []
        self._locked_ids = set()
        self._update_locked_panel()
        self.update()
        self._update_slider_params()

    def load_hierarchy(self, hierarchy: FaciesHierarchy,
                       period_name: str = "",
                       wells: list[dict] | None = None) -> None:
        """Rebuild layers from a hierarchical facies model.

        Builds per-level layer groups so that zoom determines which level is shown.
        """
        self._hierarchy = hierarchy

        pens = {
            "facies": QPen(QColor("#1a202c"), 2.0),
            "sub_facies": QPen(QColor("#4a5568"), 1.5),
            "micro_facies": QPen(QColor("#a0aec0"), 1.0),
        }
        font_sizes = {"facies": 11, "sub_facies": 8, "micro_facies": 7}

        title = f"{period_name}岩相古地理图" if period_name else ""
        self._level_groups = {}

        for level in ["facies", "sub_facies", "micro_facies"]:
            feats = [
                {"type": "Feature", "properties": {
                    "facies": ff.facies_name,
                    "name": ff.display_name,
                    "id": ff.id,
                    "boundary_type": None,
                }, "geometry": ff.geometry}
                for ff in hierarchy.get_features_at_level(level)
            ]
            if not feats:
                continue

            seen = {(f.get("properties") or {}).get("facies") for f in feats if (f.get("properties") or {}).get("facies")}
            poly = FaciesPolygonsLayer(feats, self._resolver, default_pen=pens[level])

            group: list[PaleoLayer] = [BackgroundLayer(), poly]
            group.append(RegionLabelsLayer(feats, self._resolver,
                                           font_size=font_sizes[level]))
            group.extend([
                WellsScatterLayer(wells or []),
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
        self.update()
        self._update_slider_params()

    # (outgoing_level, incoming_level, blend) — blend ∈ [0,1]
    _LEVEL_ORDER = ["facies", "sub_facies", "micro_facies"]
    _KM_THRESHOLDS = [1000.0, 500.0]  # 相→亚相 at 1000km, 亚相→微相 at 500km

    def _km_per_degree(self) -> float:
        lat = self._viewport.center_world[1]
        return 111.32 * math.cos(math.radians(lat))

    def _zoom_for_km(self, km: float) -> float:
        kpd = self._km_per_degree()
        return math.log2(self._viewport.width * kpd / km) + 1.0

    def get_threshold_zooms(self) -> list[float]:
        """Return the zoom levels at which hierarchy transitions occur."""
        return [self._zoom_for_km(km) for km in self._KM_THRESHOLDS]

    def _resolve_level(self) -> str:
        z = self._viewport.zoom
        if abs(z - self._cached_zoom) < 0.05 and self._cached_level:
            return self._cached_level
        for i, thr_km in enumerate(self._KM_THRESHOLDS):
            if z < self._zoom_for_km(thr_km):
                self._cached_level = self._LEVEL_ORDER[i]
                self._cached_zoom = z
                return self._cached_level
        last = self._LEVEL_ORDER[-1]
        self._cached_level = last
        self._cached_zoom = z
        return last

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            # Rebuild active layers if needed (e.g. if level changed)
            if self._hierarchy is not None:
                current_level = self._resolve_level_name()
                if current_level != self._current_active_level:
                    self._current_active_level = current_level
                    self._update_active_layers()

            for layer in self._layers:
                layer.paint(painter, self._viewport)
        finally:
            painter.end()

    def set_zoom(self, zoom: float) -> None:
        """Set zoom level programmatically (e.g. from slider)."""
        self._viewport.zoom = max(self._zoom_pan.min_zoom,
                                  min(self._zoom_pan.max_zoom, zoom))
        self._cached_level = ""
        self._cached_zoom = -1.0
        self.zoom_changed.emit(self._viewport.zoom)
        self.update()

    def _resolve_level_name(self) -> str:
        z = self._viewport.zoom
        for i, thr_km in enumerate(self._KM_THRESHOLDS):
            if z < self._zoom_for_km(thr_km):
                return self._LEVEL_ORDER[i]
        return self._LEVEL_ORDER[-1]

    def _collect_visible_features(self, node: FaciesNode, active_level: str, out: list[FaciesFeature]) -> None:
        if node.feature.id in self._locked_ids or node.feature.level == active_level:
            out.append(node.feature)
            return

        levels = ["facies", "sub_facies", "micro_facies"]
        node_depth = levels.index(node.feature.level) if node.feature.level in levels else 0
        active_depth = levels.index(active_level) if active_level in levels else 0

        if node_depth < active_depth:
            if node.children:
                for child in node.children:
                    self._collect_visible_features(child, active_level, out)
            else:
                out.append(node.feature)
        else:
            out.append(node.feature)

    def _update_active_layers(self) -> None:
        """Dynamically build layers for the current active level and locked features."""
        if not self._hierarchy:
            return

        active_level = self._resolve_level_name()
        visible_features = []
        for root in self._hierarchy.roots:
            self._collect_visible_features(root, active_level, visible_features)

        feats = [
            {"type": "Feature", "properties": {
                "facies": ff.facies_name,
                "name": ff.display_name,
                "id": ff.id,
                "boundary_type": None,
            }, "geometry": ff.geometry}
            for ff in visible_features
        ]

        pens = {
            "facies": QPen(QColor("#1a202c"), 2.0),
            "sub_facies": QPen(QColor("#4a5568"), 1.5),
            "micro_facies": QPen(QColor("#a0aec0"), 1.0),
        }
        font_sizes = {"facies": 11, "sub_facies": 8, "micro_facies": 7}

        level = active_level
        poly = FaciesPolygonsLayer(feats, self._resolver, default_pen=pens.get(level, pens["micro_facies"]))
        labels = RegionLabelsLayer(feats, self._resolver, font_size=font_sizes.get(level, 7))
        
        seen = {ff.facies_name for ff in visible_features if ff.facies_name}
        title = f"{self._period_name}岩相古地理图" if self._period_name else ""

        self._layers = [
            BackgroundLayer(),
            poly,
            labels,
            WellsScatterLayer(self._wells_data),
            TitleLayer(title),
            NorthArrowLayer(),
            ScaleBarLayer(),
            LegendLayer(seen, self._resolver),
        ]

    def _update_locked_panel(self) -> None:
        if not hasattr(self, "_locked_panel"):
            return
        
        level_labels = {"facies": "相", "sub_facies": "亚相", "micro_facies": "微相"}
        items = []
        if self._hierarchy is not None:
            for fid in sorted(self._locked_ids):
                node = self._hierarchy.get_node(fid)
                if node is not None:
                    lvl_lbl = level_labels.get(node.feature.level, node.feature.level)
                    items.append((fid, node.feature.display_name, lvl_lbl))
        
        self._locked_panel.update_items(items)

    def toggle_lock(self, feature_id: str) -> None:
        if feature_id in self._locked_ids:
            self._locked_ids.remove(feature_id)
        else:
            self._locked_ids.add(feature_id)
        
        if self._locked_ids and hasattr(self, "_locked_panel"):
            self._locked_panel.show()

        self._update_active_layers()
        self._update_locked_panel()
        self.update()

    def _toggle_locked_panel(self) -> None:
        if hasattr(self, "_locked_panel"):
            self._locked_panel.setVisible(not self._locked_panel.isVisible())

    def _update_slider_params(self) -> None:
        if hasattr(self, "_scale_slider"):
            vp = self._viewport
            kpd = self._km_per_degree()
            self._scale_slider.set_params(vp.width, kpd, self.get_threshold_zooms())
            self._scale_slider.set_zoom(vp.zoom)

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._viewport.resize(max(1, event.size().width()),
                              max(1, event.size().height()))
        if hasattr(self, "_scale_slider"):
            self._scale_slider.setGeometry(16, event.size().height() - 54 - 36, 320, 54)
            self._update_slider_params()
        if hasattr(self, "_locked_panel"):
            self._locked_panel.setGeometry(16, 16, 240, 180)
        super().resizeEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._zoom_pan.start_drag(QPointF(event.position()))
            self._press_pos = QPointF(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = QPointF(event.position())
        if self._zoom_pan.is_dragging():
            self._zoom_pan.update_drag(pos)
            self.update()
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
            self._zoom_pan.end_drag()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0
        if delta == 0:
            return
        # Multiply delta by 0.15 to make scrolling zoom smooth and precise
        self._zoom_pan.wheel_zoom(QPointF(event.position()), delta_steps=delta * 0.15)
        self.zoom_changed.emit(self._viewport.zoom)
        if hasattr(self, "_scale_slider"):
            self._scale_slider.set_zoom(self._viewport.zoom)
        self.update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        if self._hierarchy is None:
            return

        pos = QPointF(event.pos())
        feature_id = self._hierarchy_hit_test_id(pos)

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

        level_labels = {"facies": "相", "sub_facies": "亚相", "micro_facies": "微相"}

        if feature_id:
            node = self._hierarchy.get_node(feature_id)
            if node is not None:
                display_name = node.feature.display_name
                lvl_lbl = level_labels.get(node.feature.level, node.feature.level)

                if feature_id in self._locked_ids:
                    act_unlock = QAction(f"解除锁定: {display_name} ({lvl_lbl})", self)
                    act_unlock.triggered.connect(lambda: self.toggle_lock(feature_id))
                    menu.addAction(act_unlock)
                else:
                    act_lock = QAction(f"锁定层级: {display_name} ({lvl_lbl})", self)
                    act_lock.triggered.connect(lambda: self.toggle_lock(feature_id))
                    menu.addAction(act_lock)
                menu.addSeparator()

        panel_visible = self._locked_panel.isVisible()
        act_toggle = QAction("显示锁定层级面板" if not panel_visible else "隐藏锁定层级面板", self)
        act_toggle.triggered.connect(self._toggle_locked_panel)
        menu.addAction(act_toggle)

        menu.exec(event.globalPos())

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
