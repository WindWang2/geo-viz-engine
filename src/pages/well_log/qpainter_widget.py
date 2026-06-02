from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QScrollArea, QApplication

from geoviz_well_log import WellLogCanvas, ZoomPanHandler, CrosshairOverlay, DepthRuler
from geoviz_well_log.renderer.track_base import BaseTrack


class QPainterWidget(QScrollArea):
    """Scroll area wrapping WellLogCanvas with zoom/pan and crosshair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_top = 0.0
        self._full_bottom = 100.0
        self._scrollbar_syncing = False  # guard against recursive sync

        self._canvas = WellLogCanvas(self)
        self._zoom_handler = ZoomPanHandler(self._canvas, self)
        self._crosshair = CrosshairOverlay(self._canvas)
        self._canvas.crosshair = self._crosshair

        self.setWidget(self._canvas)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._canvas.setMouseTracking(True)
        self._canvas.mouse_moved.connect(self._on_mouse_moved)

        # Vertical scrollbar ↔ depth range sync
        self.verticalScrollBar().valueChanged.connect(self._on_vscroll_changed)

        # Depth ruler on right edge
        self._depth_ruler = DepthRuler(self.viewport())

    @property
    def canvas(self) -> WellLogCanvas:
        return self._canvas

    def set_tracks(self, tracks: list[BaseTrack]):
        self._canvas.set_tracks(tracks)
        if tracks:
            self._full_top = tracks[0].depth_top
            self._full_bottom = tracks[0].depth_bottom
            self._zoom_handler.set_full_range(self._full_top, self._full_bottom)
        self._depth_ruler.set_depth_range(self._full_top, self._full_bottom)
        self._sync_depth_ruler_geometry()
        self._update_canvas_size()
        self._sync_scrollbar_range()
        self._sync_scrollbar_from_depth()

    def set_depth_range(self, top: float, bottom: float):
        self._canvas.set_depth_range(top, bottom)
        self._sync_scrollbar_from_depth()

    def reset_view(self):
        self._canvas.set_depth_range(self._full_top, self._full_bottom)
        self._sync_scrollbar_from_depth()

    def _sync_depth_ruler_geometry(self):
        if hasattr(self, "_depth_ruler"):
            vp = self.viewport().rect()
            ruler_w = self._depth_ruler.width()
            self._depth_ruler.setGeometry(vp.width() - ruler_w, 0, ruler_w, vp.height())

    def _update_canvas_size(self):
        viewport_w = self.viewport().width()
        total_w = self._canvas.total_width
        self._canvas.setMinimumWidth(max(total_w, viewport_w))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_depth_ruler_geometry()
        self._update_canvas_size()

    def _on_mouse_moved(self, canvas_y: float):
        if not self._canvas.tracks:
            return
        if canvas_y < 0:
            self._crosshair.set_cursor_y(None)
            self._depth_ruler.set_cursor_depth(None)
        else:
            self._crosshair.set_cursor_y(canvas_y)
            depth = self._crosshair.depth_at_y(canvas_y)
            self._depth_ruler.set_cursor_depth(depth)
        self._canvas.update()

    def wheelEvent(self, event):
        """Forward wheel events to canvas so ZoomPanHandler handles zoom."""
        canvas_pos = self._canvas.mapFrom(self.viewport(), event.position().toPoint())
        canvas_global = event.globalPosition().toPoint() - event.position().toPoint() + canvas_pos
        new_event = QWheelEvent(
            canvas_pos,
            canvas_global,
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
        )
        QApplication.sendEvent(self._canvas, new_event)
        # Sync scrollbar after zoom
        self._sync_scrollbar_from_depth()

    # --- Vertical scrollbar ↔ depth sync ---

    def _sync_scrollbar_range(self):
        """Configure vertical scrollbar range from full depth bounds."""
        sb = self.verticalScrollBar()
        # Use 0..10000 range for smooth scrolling
        sb.setRange(0, 10000)
        sb.setPageStep(1000)
        sb.setSingleStep(100)

    def _sync_scrollbar_from_depth(self):
        """Update scrollbar position from current depth range."""
        if self._scrollbar_syncing:
            return
        if not self._canvas.tracks:
            return
        track = self._canvas.tracks[0]
        full_span = self._full_bottom - self._full_top
        if full_span <= 0:
            return
        # Map current center depth to scrollbar range 0..10000
        center = (track.depth_top + track.depth_bottom) / 2
        ratio = (center - self._full_top) / full_span
        self._scrollbar_syncing = True
        self.verticalScrollBar().setValue(int(ratio * 10000))
        self._scrollbar_syncing = False

    def _on_vscroll_changed(self, value: int):
        """Update depth range when scrollbar is dragged."""
        if self._scrollbar_syncing:
            return
        if not self._canvas.tracks:
            return
        track = self._canvas.tracks[0]
        full_span = self._full_bottom - self._full_top
        if full_span <= 0:
            return
        # Map scrollbar value to center depth
        ratio = value / 10000.0
        center = self._full_top + ratio * full_span
        half_span = track.depth_span / 2
        new_top = center - half_span
        new_bottom = center + half_span
        # Clamp
        if new_top < self._full_top:
            new_top = self._full_top
            new_bottom = new_top + track.depth_span
        if new_bottom > self._full_bottom:
            new_bottom = self._full_bottom
            new_top = new_bottom - track.depth_span
        self._scrollbar_syncing = True
        self._canvas.set_depth_range(new_top, new_bottom)
        self._scrollbar_syncing = False
