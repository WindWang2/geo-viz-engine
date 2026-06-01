from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QSizeF, QSize, QPointF, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF, QImage, QPageSize, QMouseEvent
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
)

from .renderer.canvas import WellLogCanvas
from .renderer.depth_ruler import DepthRuler
from .renderer.interval_track import IntervalTrack
from .renderer.lithology_track import LithologyTrack
from .renderer.interaction import ZoomPanHandler
from .models import IntervalItem, CorrelationLink
from .connection_overlay import ConnectionOverlay
from .painter_sync_manager import QPainterSyncManager


class CrossWellWidget(QWidget):
    """Multi-well cross-section view using QPainter-rendered WellLogCanvas widgets."""

    canvas_depth_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvases: list[WellLogCanvas] = []
        self._well_names: list[str] = []
        self._wrappers: list[QWidget] = []
        self._sync_manager = QPainterSyncManager(self)
        self._manual_link_active = False
        self._manual_link_picks: list[tuple[str, IntervalItem]] = []
        self._formation_data: dict[str, list[IntervalItem]] = {}

        # Direct horizontal layout (no QScrollArea — avoids viewport backing-store
        # corruption when this widget lives inside a hidden QStackedWidget page).
        # Scrolling is handled by an outer QScrollArea in CrossWellPage.
        self._container_layout = QHBoxLayout(self)
        self._container_layout.setContentsMargins(20, 0, 20, 0)
        self._container_layout.setSpacing(150)
        self._container_layout.addStretch()
        self.setMinimumHeight(400)

        # Connection overlay on self
        self._overlay = ConnectionOverlay(self)
        self._overlay.setAutoFillBackground(False)

        # Depth ruler on right edge
        self._depth_ruler = DepthRuler(self)

    @property
    def canvas_count(self) -> int:
        return len(self._canvases)

    def add_canvas(self, canvas: WellLogCanvas, well_name: str):
        """Add a well canvas to the cross-well view."""
        self._canvases.append(canvas)
        self._well_names.append(well_name)

        # Wrap canvas in a VBox with a well name label above
        wrapper = QWidget()
        vbox = QVBoxLayout(wrapper)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        name_label = QLabel(well_name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1a202c;"
            "background: #f7fafc; border-bottom: 1px solid #e2e8f0;"
            "padding: 4px 8px;"
        )
        name_label.setFixedHeight(28)
        vbox.addWidget(name_label)
        vbox.addWidget(canvas, 1)
        self._wrappers.append(wrapper)

        # Insert wrapper before the stretch
        idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(idx, wrapper)
        self._sync_manager.add_canvas(canvas)
        canvas.setMouseTracking(True)
        # Set up crosshair overlay per canvas
        from .renderer.overlay import CrosshairOverlay
        overlay = CrosshairOverlay(canvas)
        canvas.crosshair = overlay
        # Set up zoom/pan handler
        if canvas.tracks:
            zh = ZoomPanHandler(canvas, self)
            zh.set_full_range(canvas.tracks[0].depth_top, canvas.tracks[0].depth_bottom)
            self._depth_ruler.set_depth_range(canvas.tracks[0].depth_top, canvas.tracks[0].depth_bottom)
        
        # Wire reactive signal connections to update overlays on zoom/pan depth scaling
        canvas.depth_range_changed.connect(self.canvas_depth_changed)
        canvas.depth_range_changed.connect(self._overlay.update)
        
        # Intercept child mouse events when manual well correlation is active
        canvas.installEventFilter(self)

        self._overlay.set_canvases(self._canvases, self._well_names)
        self._overlay.raise_()
        self._update_minimum_width()

    def remove_canvas(self, canvas: WellLogCanvas):
        """Remove a well canvas from the cross-well view."""
        if canvas in self._canvases:
            idx = self._canvases.index(canvas)
            self._sync_manager.remove_canvas(canvas)
            
            try:
                canvas.depth_range_changed.disconnect(self.canvas_depth_changed)
                canvas.depth_range_changed.disconnect(self._overlay.update)
            except RuntimeError:
                pass
            canvas.removeEventFilter(self)

            wrapper = self._wrappers[idx]
            self._container_layout.removeWidget(wrapper)
            wrapper.setParent(None)
            self._canvases.pop(idx)
            self._well_names.pop(idx)
            self._wrappers.pop(idx)
            self._overlay.set_canvases(self._canvases, self._well_names)
            self._update_minimum_width()

    def move_well(self, from_idx: int, to_idx: int):
        """Move a well canvas from one position to another."""
        if from_idx == to_idx:
            return
        canvas = self._canvases[from_idx]
        name = self._well_names[from_idx]
        wrapper = self._wrappers[from_idx]
        # Remove from lists and layout
        self._sync_manager.remove_canvas(canvas)
        self._container_layout.removeWidget(wrapper)
        self._canvases.pop(from_idx)
        self._well_names.pop(from_idx)
        self._wrappers.pop(from_idx)
        # Insert at new position (clamped, before stretch)
        insert_idx = min(to_idx, len(self._canvases))
        self._canvases.insert(insert_idx, canvas)
        self._well_names.insert(insert_idx, name)
        self._wrappers.insert(insert_idx, wrapper)
        # Re-add to layout at the correct position
        self._container_layout.insertWidget(insert_idx, wrapper)
        self._sync_manager.add_canvas(canvas)
        self._overlay.set_canvases(self._canvases, self._well_names)
        self._update_minimum_width()

    def clear_all(self):
        """Remove all wells and clear state."""
        for canvas in self._canvases[:]:
            self.remove_canvas(canvas)
        self._overlay.set_links([])
        self._overlay.set_canvases([], well_names=[])
        self._formation_data.clear()
        self._wrappers.clear()
        self._update_minimum_width()

    def set_formation_data(self, well_name: str, intervals: list[IntervalItem]):
        """Store formation intervals for correlation (decoupled from track visibility)."""
        self._formation_data[well_name] = intervals

    def set_track_visible(self, canvas: WellLogCanvas, track_index: int, visible: bool):
        """Show or hide a specific track on a canvas."""
        if 0 <= track_index < len(canvas.tracks):
            canvas.tracks[track_index]._visible = visible
            canvas.update()

    def _update_minimum_width(self):
        """Ensure widget is wide enough for all canvases."""
        if not self._canvases:
            self.setMinimumWidth(0)
            return
        spacing = self._container_layout.spacing()
        margins = self._container_layout.contentsMargins()
        total = margins.left() + margins.right()
        for c in self._canvases:
            total += c.minimumWidth()
        total += spacing * max(0, len(self._canvases) - 1)
        self.setMinimumWidth(total)

    def eventFilter(self, watched, event) -> bool:
        """Intercept child canvas clicks when manual linking is active."""
        if self._manual_link_active and watched in self._canvases:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                pos = watched.mapTo(self, event.position().toPoint())
                synthetic = QMouseEvent(
                    event.type(),
                    pos,
                    event.globalPosition(),
                    event.button(),
                    event.buttons(),
                    event.modifiers(),
                )
                self.mousePressEvent(synthetic)
                return True
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update overlay geometry to cover self and raise above canvas wrappers
        self._overlay.setGeometry(self.rect())
        self._overlay.raise_()
        # Position depth ruler
        ruler_w = self._depth_ruler.width()
        self._depth_ruler.setGeometry(self.width() - ruler_w, 0, ruler_w, self.height())

    # --- Auto-link and manual link ---

    def auto_link(self):
        """Auto-correlate intervals between adjacent wells by name matching."""
        links = []
        for i in range(len(self._canvases) - 1):
            name1 = self._well_names[i]
            name2 = self._well_names[i + 1]

            # Prefer formation data (reliable stratigraphic names like 万山组)
            # Fall back to collecting intervals from visible tracks
            ivs1 = self._formation_data.get(name1) or self._collect_intervals(self._canvases[i])
            ivs2 = self._formation_data.get(name2) or self._collect_intervals(self._canvases[i + 1])

            names1 = {iv.name: iv for iv in ivs1}
            names2 = {iv.name: iv for iv in ivs2}
            common = set(names1.keys()) & set(names2.keys())
            for iv_name in common:
                iv1 = names1[iv_name]
                iv2 = names2[iv_name]
                link = CorrelationLink(
                    source_well=name1, target_well=name2,
                    source_interval_id=f"{iv1.top}_{iv1.bottom}_{iv1.name}",
                    target_interval_id=f"{iv2.top}_{iv2.bottom}_{iv2.name}",
                    color="#f59e0b",
                )
                links.append(link)
        # Preserve manual links before replacing
        existing_manual = [l for l in self._overlay.links if getattr(l, 'is_manual', False)]
        self._overlay.set_links(links + existing_manual)

    def _collect_intervals(self, canvas: WellLogCanvas) -> list[IntervalItem]:
        """Collect interval-like objects from a canvas's tracks."""
        intervals = []
        for track in canvas.tracks:
            if isinstance(track, IntervalTrack):
                intervals.extend(track._intervals)
            elif isinstance(track, LithologyTrack):
                # Convert LithologyInterval → IntervalItem for correlation matching
                for iv in track._intervals:
                    intervals.append(IntervalItem(
                        top=iv.top, bottom=iv.bottom, name=iv.lithology,
                    ))
        return intervals

    def toggle_manual_link(self):
        """Toggle manual linking mode."""
        self._manual_link_active = not self._manual_link_active
        self._manual_link_picks.clear()

    def _finish_manual_link(self):
        """Complete a manual link from collected picks."""
        if len(self._manual_link_picks) < 2:
            return
        w1, iv1 = self._manual_link_picks[0]
        w2, iv2 = self._manual_link_picks[1]
        link = CorrelationLink(
            source_well=w1, target_well=w2,
            source_interval_id=f"{iv1.top}_{iv1.bottom}_{iv1.name}",
            target_interval_id=f"{iv2.top}_{iv2.bottom}_{iv2.name}",
            color="#ef4444", is_manual=True,
        )
        links = self._overlay.links + [link]
        self._overlay.set_links(links)
        self._manual_link_active = False
        self._manual_link_picks.clear()

    def mousePressEvent(self, event):
        """Handle clicks for manual linking: detect which canvas and interval."""
        if not self._manual_link_active:
            super().mousePressEvent(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        pos = event.pos()
        clicked_canvas = None
        well_idx = -1
        for i, canvas in enumerate(self._canvases):
            canvas_pos = canvas.mapTo(self, canvas.rect().topLeft())
            canvas_rect = canvas.rect().translated(canvas_pos)
            if canvas_rect.contains(pos):
                clicked_canvas = canvas
                well_idx = i
                break

        if clicked_canvas is None:
            super().mousePressEvent(event)
            return

        well_name = self._well_names[well_idx]
        local_pos = clicked_canvas.mapFrom(self, pos)
        # Convert click Y to depth
        clicked_depth = self._y_to_depth(clicked_canvas, local_pos.y())
        if clicked_depth is None:
            super().mousePressEvent(event)
            return

        # Find interval at clicked depth
        intervals = self._collect_intervals(clicked_canvas)
        best = None
        for iv in intervals:
            if iv.top <= clicked_depth <= iv.bottom:
                if best is None or (iv.bottom - iv.top) < (best.bottom - best.top):
                    best = iv
        if best is None:
            super().mousePressEvent(event)
            return

        self._manual_link_picks.append((well_name, best))
        if len(self._manual_link_picks) >= 2:
            self._finish_manual_link()
        self.update()

    @staticmethod
    def _y_to_depth(canvas: WellLogCanvas, y: float) -> float | None:
        """Convert a Y pixel coordinate to a depth value."""
        if not canvas.tracks:
            return None
        header_h = max((t.header_height for t in canvas.tracks), default=56)
        content_h = canvas.height() - header_h
        if content_h <= 0:
            return None
        track = canvas.tracks[0]
        span = track.depth_span
        if span <= 0:
            return None
        ratio = (y - header_h) / content_h
        return track.depth_top + ratio * span

    # --- Composite vector export ---

    def export_composite(self, path: str, fmt: str = "svg"):
        """Export all canvases + correlation polygons as a single file."""
        if not self._canvases:
            return

        spacing = 150
        total_w = sum(c.width() for c in self._canvases) + \
                  spacing * (len(self._canvases) - 1)
        total_h = max(c.height() for c in self._canvases)

        if fmt == "svg":
            self._export_svg(path, total_w, total_h)
        elif fmt == "pdf":
            self._export_pdf(path, total_w, total_h)
        elif fmt == "png":
            self._export_png(path, total_w, total_h)

    def _export_svg(self, path: str, w: int, h: int):
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(QSize(w, h))
        gen.setViewBox(QRectF(0, 0, w, h))
        painter = QPainter(gen)
        self._paint_composite(painter, w, h)
        painter.end()

    def _export_pdf(self, path: str, w: int, h: int):
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(path)
        mm_w = w * 25.4 / 96
        mm_h = h * 25.4 / 96
        printer.setPageSize(QPageSize(QSizeF(mm_w, mm_h), QPageSize.Unit.Millimeter))
        painter = QPainter(printer)
        self._paint_composite(painter, w, h)
        painter.end()

    def _export_png(self, path: str, w: int, h: int):
        img = QImage(w, h, QImage.Format.Format_ARGB32)
        img.fill(0xFFFFFFFF)
        painter = QPainter(img)
        self._paint_composite(painter, w, h)
        painter.end()
        img.save(path)

    def _paint_composite(self, painter: QPainter, total_w: int, total_h: int):
        """Paint all canvases at computed x-offsets, then overlay correlation polygons."""
        spacing = 150
        x_off = 0
        canvas_x_offsets: dict[int, float] = {}
        canvas_right_edges: dict[int, float] = {}

        for canvas in self._canvases:
            painter.save()
            painter.translate(x_off, 0)
            canvas.paint_all(painter)
            painter.restore()
            canvas_x_offsets[id(canvas)] = x_off
            canvas_right_edges[id(canvas)] = x_off + canvas.width()
            x_off += canvas.width() + spacing

        # Paint correlation polygons
        links = self._overlay.links
        if links:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

            name_to_canvas: dict[str, WellLogCanvas] = {}
            for i, c in enumerate(self._canvases):
                if i < len(self._well_names):
                    name_to_canvas[self._well_names[i]] = c

            for link in links:
                source = name_to_canvas.get(link.source_well)
                target = name_to_canvas.get(link.target_well)
                if source is None or target is None:
                    continue

                try:
                    src_parts = link.source_interval_id.split("_")
                    src_top = float(src_parts[0])
                    src_bot = float(src_parts[1])
                    tgt_parts = link.target_interval_id.split("_")
                    tgt_top = float(tgt_parts[0])
                    tgt_bot = float(tgt_parts[1])
                except (ValueError, IndexError):
                    continue

                sy1 = self._overlay.depth_to_y(source, src_top)
                sy2 = self._overlay.depth_to_y(source, src_bot)
                ty1 = self._overlay.depth_to_y(target, tgt_top)
                ty2 = self._overlay.depth_to_y(target, tgt_bot)

                src_right = canvas_right_edges[id(source)]
                tgt_left = canvas_x_offsets[id(target)]

                polygon = QPolygonF([
                    QPointF(src_right, sy1),
                    QPointF(tgt_left, ty1),
                    QPointF(tgt_left, ty2),
                    QPointF(src_right, sy2),
                ])

                color = QColor(link.color)
                color.setAlpha(120)
                painter.setPen(QPen(color.darker(120), 1))
                painter.setBrush(color)
                painter.drawPolygon(polygon)
