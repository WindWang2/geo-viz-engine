from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
)

from .renderer.canvas import WellLogCanvas
from .renderer.depth_ruler import DepthRuler
from .renderer.interval_track import IntervalTrack
from .models import IntervalItem
from .connection_overlay import ConnectionOverlay
from .painter_sync_manager import QPainterSyncManager
from .models import CorrelationLink


class CrossWellWidget(QWidget):
    """Multi-well cross-section view using QPainter-rendered WellLogCanvas widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvases: list[WellLogCanvas] = []
        self._well_names: list[str] = []
        self._sync_manager = QPainterSyncManager(self)
        self._manual_link_active = False
        self._manual_link_picks: list[tuple[str, IntervalItem]] = []

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area with horizontal layout
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(150)
        self._container_layout.addStretch()
        self._scroll.setWidget(self._container)
        main_layout.addWidget(self._scroll)

        # Connection overlay on container
        self._overlay = ConnectionOverlay(self._container)

        # Depth ruler on right edge of scroll viewport
        self._depth_ruler = DepthRuler(self._scroll.viewport())

    @property
    def canvas_count(self) -> int:
        return len(self._canvases)

    def add_canvas(self, canvas: WellLogCanvas, well_name: str):
        """Add a well canvas to the cross-well view."""
        self._canvases.append(canvas)
        self._well_names.append(well_name)
        # Insert before the stretch
        idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(idx, canvas)
        self._sync_manager.add_canvas(canvas)
        canvas.setMouseTracking(True)
        # Set up crosshair overlay per canvas
        from .renderer.overlay import CrosshairOverlay
        overlay = CrosshairOverlay(canvas)
        canvas.crosshair = overlay
        # Update depth ruler from first canvas's tracks
        if canvas.tracks:
            t = canvas.tracks[0]
            self._depth_ruler.set_depth_range(t.depth_top, t.depth_bottom)
        self._update_overlay_geometry()

    def remove_canvas(self, canvas: WellLogCanvas):
        """Remove a well canvas from the cross-well view."""
        if canvas in self._canvases:
            idx = self._canvases.index(canvas)
            self._sync_manager.remove_canvas(canvas)
            self._container_layout.removeWidget(canvas)
            canvas.setParent(None)
            self._canvases.pop(idx)
            self._well_names.pop(idx)
            self._update_overlay_geometry()

    def clear_all(self):
        """Remove all wells and clear state."""
        for canvas in self._canvases[:]:
            self.remove_canvas(canvas)
        self._overlay.set_links([])

    def _update_overlay_geometry(self):
        """Update overlay geometry to cover the container."""
        if self._overlay:
            self._overlay.setGeometry(self._container.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_geometry()
        # Position depth ruler
        vp = self._scroll.viewport().rect()
        ruler_w = self._depth_ruler.width()
        self._depth_ruler.setGeometry(vp.width() - ruler_w, 0, ruler_w, vp.height())

    # --- Auto-link and manual link ---

    def auto_link(self):
        """Auto-correlate intervals between adjacent wells by name matching."""
        links = []
        for i in range(len(self._canvases) - 1):
            c1 = self._canvases[i]
            c2 = self._canvases[i + 1]
            name1 = self._well_names[i]
            name2 = self._well_names[i + 1]
            ivs1 = self._collect_intervals(c1)
            ivs2 = self._collect_intervals(c2)
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
        self._overlay.set_links(links)

    def _collect_intervals(self, canvas: WellLogCanvas) -> list[IntervalItem]:
        """Collect all IntervalItem objects from a canvas's tracks."""
        intervals = []
        for track in canvas.tracks:
            if isinstance(track, IntervalTrack):
                intervals.extend(track._intervals)
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
        links = self._overlay._links + [link]
        self._overlay.set_links(links)
        self._manual_link_active = False
        self._manual_link_picks.clear()
