"""MapCanvas — composite QWidget that paints all layers and dispatches input."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QWidget

from geoviz_map.layers.background import BackgroundLayer
from geoviz_map.layers.base import MapLayer
from geoviz_map.layers.geojson_polygon import GeoJsonPolygonLayer
from geoviz_map.layers.graticule import GraticuleLayer
from geoviz_map.layers.reference import ReferenceLabelsLayer
from geoviz_map.layers.wells import WellsLayer
from geoviz_map.models import ReferenceLabel, WellMarker
from geoviz_map.paint_scheduler import PaintScheduler, LayerPixmapCache
from geoviz_map.viewport import MapViewport
from geoviz_map.zoom_pan import ZoomPanHandler


class MapCanvas(QWidget):
    well_clicked = Signal(str)
    well_hovered = Signal(str)  # emits empty string when hover leaves
    section_selected = Signal(list)  # emits list of well names in the box selection

    def __init__(self,
                 wells: list[WellMarker],
                 world_geojson: dict,
                 china_geojson: dict,
                 reference_labels: list[ReferenceLabel] | None = None,
                 initial_center: tuple[float, float] | None = None,
                 initial_zoom: float = 7.5,
                 background_color: str = "#cbebfb",
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._press_pos: QPointF | None = None
        self._box_start: QPointF | None = None
        self._box_current: QPointF | None = None
        self._box_selecting: bool = False

        if initial_center is None:
            if wells:
                avg_lng = sum(w.lng for w in wells) / len(wells)
                avg_lat = sum(w.lat for w in wells) / len(wells)
                initial_center = (avg_lng, avg_lat)
            else:
                initial_center = (117.0, 38.0)
        self._viewport = MapViewport(initial_center[0], initial_center[1],
                                     zoom=initial_zoom,
                                     width=max(1, self.width()),
                                     height=max(1, self.height()))
        self._zoom_pan = ZoomPanHandler(self._viewport)

        self._wells_layer = WellsLayer(wells)

        self._layers: list[MapLayer] = [
            BackgroundLayer(background_color),
            GraticuleLayer(),
            GeoJsonPolygonLayer(
                world_geojson,
                fill_color="#f3f1ec",
                border_color="#cbd5e1",
                border_width=0.8,
                feature_filter=lambda p: p.get("ISO_A3") not in ("CHN", "TWN"),
            ),
            GeoJsonPolygonLayer(
                china_geojson,
                fill_color="#f3f1ec",
                border_color="#cbd5e1",
                border_width=0.8,
            ),
            ReferenceLabelsLayer(reference_labels or []),
            self._wells_layer,
        ]

        self._scheduler = PaintScheduler(self)
        self._layer_caches = [LayerPixmapCache(layer) for layer in self._layers]

    # Painting -----------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            for cache in self._layer_caches:
                cache.paint(painter, self._viewport)

            # Draw selection box if actively selecting
            if self._box_selecting and self._box_start and self._box_current:
                from PySide6.QtGui import QColor, QPen
                from PySide6.QtCore import QRectF
                rect = QRectF(self._box_start, self._box_current)
                # Semi-transparent blue fill
                painter.fillRect(rect, QColor(59, 130, 246, 50))
                # Dashed blue border
                pen = QPen(QColor(59, 130, 246), 1.5, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(rect)
        finally:
            painter.end()

    def resizeEvent(self, event: QResizeEvent) -> None:
        self._viewport.resize(max(1, event.size().width()),
                              max(1, event.size().height()))
        super().resizeEvent(event)

    # Input --------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Start box selection
                self._box_start = QPointF(event.position())
                self._box_current = QPointF(event.position())
                self._box_selecting = True
            else:
                self._zoom_pan.start_drag(QPointF(event.position()))
                self._press_pos = QPointF(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = QPointF(event.position())
        if self._box_selecting:
            self._box_current = pos
            self.update()
        elif self._zoom_pan.is_dragging():
            self._zoom_pan.update_drag(pos)
            self._scheduler.schedule()
        else:
            # Hover hit-test
            name = self._wells_layer.hit_test(pos, self._viewport)
            if name != self._wells_layer.hovered_name:
                self._wells_layer.set_hovered(name)
                self.well_hovered.emit(name or "")
                self._scheduler.schedule()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        
        if self._box_selecting:
            self._box_selecting = False
            release_pos = QPointF(event.position())
            if self._box_start is not None:
                from PySide6.QtCore import QRectF
                rect = QRectF(self._box_start, release_pos)
                selected_well_names = []
                for well in self._wells_layer.wells:
                    if well.has_data:
                        well_screen_pos = self._viewport.lnglat_to_screen(well.lng, well.lat)
                        if rect.contains(well_screen_pos):
                            selected_well_names.append(well.name)
                
                if selected_well_names:
                    self.section_selected.emit(selected_well_names)
            
            self._box_start = None
            self._box_current = None
            self.update()
            return

        release_pos = QPointF(event.position())
        # Distinguish click vs drag: if total drag is small, treat as click
        drag_distance = 0.0
        if self._press_pos is not None:
            dx = release_pos.x() - self._press_pos.x()
            dy = release_pos.y() - self._press_pos.y()
            drag_distance = (dx * dx + dy * dy) ** 0.5
        self._zoom_pan.end_drag()
        if drag_distance < 4.0:
            name = self._wells_layer.hit_test(release_pos, self._viewport)
            if name:
                self.well_clicked.emit(name)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y() / 120.0  # one notch = 1.0
        if delta == 0:
            return
        # Multiply delta by 0.15 to make scrolling zoom smooth and precise
        self._zoom_pan.wheel_zoom(QPointF(event.position()), delta_steps=delta * 0.15)
        self._scheduler.schedule()
