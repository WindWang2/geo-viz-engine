from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal, QPointF, QSizeF, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QImage
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QGraphicsScene

from .well_item import WellItem
from .correlation_band import CorrelationBand
from .annotation_item import AnnotationItem
from .depth_ruler_item import DepthRulerItem
from ..models import IntervalItem, CorrelationLink
from ..renderer.interval_track import IntervalTrack
from ..renderer.lithology_track import LithologyTrack


class CrossWellScene(QGraphicsScene):
    """Manages all items in the cross-well canvas: wells, bands, ruler.

    Global depth_scale (px/depth-unit) is shared across all wells.
    Each well has its own display depth range (top/bottom).
    """

    band_color_changed = Signal(object, str)  # band, new_color

    def __init__(self, parent=None):
        super().__init__(parent)
        self._depth_scale = 0.8  # pixels per depth unit (global)
        self._well_items: dict[str, WellItem] = {}
        self._well_order: list[str] = []
        self._bands: list[CorrelationBand] = []
        self._ruler = DepthRulerItem()
        self.addItem(self._ruler)
        self._ruler.setPos(0, 0)

        self._formation_data: dict[str, list[IntervalItem]] = {}

        # Manual link state
        self._manual_link_active = False
        self._manual_link_picks: list[tuple[str, IntervalItem]] = []

    # --- Depth scale (global, pixels per depth unit) ---

    def set_depth_scale(self, scale: float):
        self._depth_scale = scale
        for item in self._well_items.values():
            item.set_depth_scale(scale)
        self._update_ruler()
        self._layout_wells()
        self._update_band_geometry()
        self._update_scene_rect()

    def depth_scale(self) -> float:
        return self._depth_scale

    # --- Per-well depth range ---

    def set_well_depth_range(self, well_name: str, top: float, bottom: float):
        item = self._well_items.get(well_name)
        if item:
            item.set_depth_range(top, bottom)
            self._update_ruler()
            self._update_band_geometry()
            self._update_scene_rect()

    def set_all_well_depth_range(self, top: float, bottom: float):
        for item in self._well_items.values():
            item.set_depth_range(top, bottom)
        self._update_ruler()
        self._update_band_geometry()
        self._update_scene_rect()

    # --- Well management ---

    def add_well(self, well_name: str, tracks: list,
                 formation_data: list[IntervalItem] | None = None) -> WellItem:
        item = WellItem(well_name, tracks, depth_scale=self._depth_scale)
        # Default: show full data range
        if tracks:
            item.set_depth_range(tracks[0].depth_top, tracks[0].depth_bottom)
        else:
            item.set_depth_range(0, 1000)

        item.well_moved.connect(self._on_well_moved)

        self.addItem(item)
        self._well_items[well_name] = item
        self._well_order.append(well_name)

        if formation_data:
            self._formation_data[well_name] = formation_data

        self._update_ruler()
        self._layout_wells()
        self._update_scene_rect()
        return item

    def remove_well(self, well_name: str):
        item = self._well_items.pop(well_name, None)
        if item is None:
            return
        self._well_order.remove(well_name)
        bands_to_remove = [b for b in self._bands
                          if b.source_well is item or b.target_well is item]
        for b in bands_to_remove:
            self._bands.remove(b)
            self.removeItem(b)
        self.removeItem(item)
        self._formation_data.pop(well_name, None)
        self._update_ruler()
        self._layout_wells()
        self._update_scene_rect()

    def wells(self) -> list[WellItem]:
        return [self._well_items[n] for n in self._well_order if n in self._well_items]

    def well_by_name(self, name: str) -> WellItem | None:
        return self._well_items.get(name)

    def well_count(self) -> int:
        return len(self._well_items)

    def clear_all(self):
        """Clear all wells, correlation bands, and temporary data from the scene."""
        # Use QGraphicsScene.clear() to properly delete all QGraphicsItem objects
        super().clear()
        
        self._well_items.clear()
        self._well_order.clear()
        self._bands.clear()
        self._formation_data.clear()
        self._manual_link_picks.clear()
        self._manual_link_active = False
        
        # Re-add persistent items
        self._ruler = DepthRulerItem()
        self.addItem(self._ruler)
        self._ruler.setPos(0, 0)
        
        self.update()
        self._update_scene_rect()

    def update_well_tracks(self, well_name: str, tracks: list):
        item = self._well_items.get(well_name)
        if item:
            item.set_tracks(tracks)
            item.update()

    # --- Correlation ---

    def auto_link(self):
        links = []
        for i in range(len(self._well_order) - 1):
            name1 = self._well_order[i]
            name2 = self._well_order[i + 1]
            item1 = self._well_items.get(name1)
            item2 = self._well_items.get(name2)
            if item1 is None or item2 is None:
                continue

            ivs1 = self._formation_data.get(name1) or self._collect_intervals(name1)
            ivs2 = self._formation_data.get(name2) or self._collect_intervals(name2)
            if not ivs1 or not ivs2:
                continue

            # Filter to intervals overlapping current display depth range
            ivs1 = [iv for iv in ivs1 if iv.top < item1.depth_bottom and iv.bottom > item1.depth_top]
            ivs2 = [iv for iv in ivs2 if iv.top < item2.depth_bottom and iv.bottom > item2.depth_top]

            names1 = {iv.name: iv for iv in ivs1}
            names2 = {iv.name: iv for iv in ivs2}
            common = set(names1.keys()) & set(names2.keys())
            for iv_name in common:
                iv1 = names1[iv_name]
                iv2 = names2[iv_name]
                links.append(CorrelationLink(
                    source_well=name1, target_well=name2,
                    source_interval_id=f"{iv1.top}_{iv1.bottom}_{iv1.name}",
                    target_interval_id=f"{iv2.top}_{iv2.bottom}_{iv2.name}",
                    color="#f59e0b",
                ))

        for b in self._bands[:]:
            if not b.is_manual:
                self._bands.remove(b)
                self.removeItem(b)

        for link in links:
            src = self._well_items.get(link.source_well)
            tgt = self._well_items.get(link.target_well)
            if src and tgt:
                band = CorrelationBand(
                    src, tgt,
                    link.source_interval_id, link.target_interval_id,
                    color=link.color,
                )
                self.addItem(band)
                self._bands.append(band)

    def _collect_intervals(self, well_name: str) -> list[IntervalItem]:
        item = self._well_items.get(well_name)
        if item is None:
            return []
        intervals = []
        for track in item.tracks:
            if isinstance(track, IntervalTrack):
                intervals.extend(track._intervals)
            elif isinstance(track, LithologyTrack):
                for iv in track._intervals:
                    intervals.append(IntervalItem(
                        top=iv.top, bottom=iv.bottom, name=iv.lithology,
                    ))
        return intervals

    def clear_bands(self):
        for b in self._bands[:]:
            self.removeItem(b)
        self._bands.clear()

    def bands(self) -> list[CorrelationBand]:
        return list(self._bands)

    # --- Manual linking ---

    def set_manual_link_mode(self, active: bool):
        self._manual_link_active = active
        self._manual_link_picks.clear()

    def manual_link_mode(self) -> bool:
        return self._manual_link_active

    def handle_well_click(self, well_name: str, local_pos: QPointF) -> bool:
        if not self._manual_link_active:
            return False
        item = self._well_items.get(well_name)
        if item is None:
            return False
        interval = item.interval_at(local_pos)
        if interval is None:
            return False
        self._manual_link_picks.append((well_name, interval))
        if len(self._manual_link_picks) >= 2:
            self._finish_manual_link()
        return True

    def _finish_manual_link(self):
        if len(self._manual_link_picks) < 2:
            return
        w1, iv1 = self._manual_link_picks[0]
        w2, iv2 = self._manual_link_picks[1]
        src = self._well_items.get(w1)
        tgt = self._well_items.get(w2)
        if src and tgt:
            band = CorrelationBand(
                src, tgt,
                f"{iv1.top}_{iv1.bottom}_{iv1.name}",
                f"{iv2.top}_{iv2.bottom}_{iv2.name}",
                color="#ef4444", is_manual=True,
            )
            self.addItem(band)
            self._bands.append(band)
        self._manual_link_active = False
        self._manual_link_picks.clear()

    # --- Layout ---

    def _layout_wells(self):
        ruler_w = DepthRulerItem._WIDTH
        spacing = 150
        x = ruler_w + 20
        for name in self._well_order:
            item = self._well_items.get(name)
            if item:
                item.setPos(x, 28)
                x += item.column_width + spacing

    def _update_ruler(self):
        # Ruler covers the union of all well depth ranges
        if not self._well_items:
            self._ruler.set_depth_range(0, 1000)
            self._ruler.set_height(800)
            return
        tops = [item.depth_top for item in self._well_items.values()]
        bottoms = [item.depth_bottom for item in self._well_items.values()]
        self._ruler.set_depth_range(min(tops), max(bottoms))
        max_h = max(item.column_height for item in self._well_items.values())
        self._ruler.set_height(max_h)

    def _update_scene_rect(self):
        rect = self.itemsBoundingRect().adjusted(-10, -40, 60, 40)
        if rect.isEmpty():
            rect = QRectF(0, 0, 800, 600)
        self.setSceneRect(rect)

    def _on_well_moved(self):
        self._update_band_geometry()
        self._update_scene_rect()

    def _update_band_geometry(self):
        for band in self._bands:
            band.update_geometry()

    # --- Annotations ---

    def add_annotation(self, text: str, x: float, depth: float,
                       color: str = "#1a202c") -> AnnotationItem:
        """Add a text annotation at the given scene x and depth position."""
        y = self._depth_scale * (depth - self._ruler._depth_top) + 28
        item = AnnotationItem(text, x, y, color=color)
        self.addItem(item)
        self._update_scene_rect()
        return item

    def remove_annotation(self, annotation: AnnotationItem):
        """Remove an annotation item from the scene."""
        if annotation in self.items():
            self.removeItem(annotation)
            self._update_scene_rect()

    # --- Export ---

    def export_to_file(self, path: str, fmt: str = "svg"):
        rect = self.itemsBoundingRect().adjusted(-20, -40, 60, 40)

        if fmt == "svg":
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(QSize(int(rect.width()), int(rect.height())))
            gen.setViewBox(rect)
            painter = QPainter(gen)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self.render(painter, rect, rect)
            painter.end()
        elif fmt == "pdf":
            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            from PySide6.QtGui import QPageSize
            mm_w = rect.width() * 25.4 / 96
            mm_h = rect.height() * 25.4 / 96
            printer.setPageSize(QPageSize(QSizeF(mm_w, mm_h), QPageSize.Unit.Millimeter))
            painter = QPainter(printer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self.render(painter, rect, rect)
            painter.end()
        elif fmt == "png":
            w = int(rect.width())
            h = int(rect.height())
            if w <= 0 or h <= 0:
                return
            img = QImage(w, h, QImage.Format.Format_ARGB32)
            img.fill(0xFFFFFFFF)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self.render(painter, rect, rect)
            painter.end()
            img.save(path)
