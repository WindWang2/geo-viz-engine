from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QWheelEvent, QPainter
from PySide6.QtWidgets import QScrollArea, QApplication, QWidget

from geoviz_well_log import WellLogCanvas, ZoomPanHandler, CrosshairOverlay, DepthRuler
from geoviz_well_log.renderer.track_base import BaseTrack


class _CrosshairOverlayWidget(QWidget):
    """Transparent overlay that paints the crosshair on top of the canvas.

    Uses a deferred paint via QTimer.singleShot(0) so that Qt's normal
    child-painting cycle completes first, then we paint on top.
    """

    def __init__(self, overlay: CrosshairOverlay, parent=None):
        super().__init__(parent)
        self._overlay = overlay
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

    def paintEvent(self, event):
        if not self._overlay.visible:
            return
        painter = QPainter(self)
        self._overlay.paint_overlay(painter, QRectF(self.rect()))
        painter.end()

    def schedule_repaint(self):
        """Trigger a deferred repaint so crosshair draws after children."""
        QTimer.singleShot(0, self.update)


class QPainterWidget(QScrollArea):
    """Scroll area wrapping WellLogCanvas with zoom/pan and crosshair.

    The scrollbar controls the visible depth range (like Ctrl+drag panning),
    not physical canvas scrolling. Canvas height is fixed to viewport height.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_top = 0.0
        self._full_bottom = 100.0
        self._scrollbar_syncing = False  # guard against recursive sync

        self._canvas = WellLogCanvas(self)
        self._zoom_handler = ZoomPanHandler(self._canvas, self)
        self._crosshair = CrosshairOverlay(self._canvas)
        self._canvas.crosshair = self._crosshair

        self.setWidgetResizable(True)  # canvas fills viewport (no physical scroll)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setWidget(self._canvas)
        self._canvas.setMouseTracking(True)
        self._canvas.mouse_moved.connect(self._on_mouse_moved)
        self._canvas.depth_range_changed.connect(self._on_canvas_depth_range_changed)

        # Crosshair overlay — sits on top of the canvas in the viewport
        self._crosshair_widget = _CrosshairOverlayWidget(self._crosshair, self.viewport())
        self._crosshair_widget.setGeometry(self.viewport().rect())
        self._crosshair_widget.show()

        # Vertical scrollbar ↔ depth range sync (scrollbar controls depth, not canvas position)
        self.verticalScrollBar().valueChanged.connect(self._on_vscroll_changed)

        self._depth_ruler = DepthRuler(self)
        self.setCornerWidget(self._depth_ruler)

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

    def reset_view(self):
        self._canvas.set_depth_range(self._full_top, self._full_bottom)

    def _on_canvas_depth_range_changed(self, top: float, bottom: float):
        self._depth_ruler.set_depth_range(top, bottom)
        self._sync_scrollbar_range()
        self._sync_scrollbar_from_depth()

    def _sync_depth_ruler_geometry(self):
        if hasattr(self, "_depth_ruler"):
            self._depth_ruler.setFixedHeight(self.viewport().height())

    def _update_canvas_size(self):
        viewport_w = self.viewport().width()
        canvas_w = max(viewport_w, self._canvas.total_width)
        self._canvas.setMinimumWidth(canvas_w)
        self._canvas.resize(canvas_w, self.viewport().height())
        self._canvas.setFixedHeight(self.viewport().height())
        self._canvas.move(self._canvas.pos().x(), 0)

    def scrollContentsBy(self, dx: int, dy: int):
        if dx:
            super().scrollContentsBy(dx, 0)
        self._canvas.move(self._canvas.pos().x(), 0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_depth_ruler_geometry()
        self._update_canvas_size()
        # Keep crosshair overlay sized to viewport
        if hasattr(self, "_crosshair_widget"):
            self._crosshair_widget.setGeometry(self.viewport().rect())

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
        # Schedule deferred crosshair repaint so it draws after canvas children
        self._crosshair_widget.schedule_repaint()

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
        # Sync scrollbar after zoom (depth range may have changed)
        self._sync_scrollbar_range()
        self._sync_scrollbar_from_depth()

    # --- Vertical scrollbar ↔ depth sync ---
    # The scrollbar controls the center of the visible depth range,
    # like Ctrl+drag panning. No physical canvas scrolling.

    def _sync_scrollbar_range(self):
        """Configure vertical scrollbar range from full depth bounds.

        Thumb size represents visible_depth / total_depth ratio.
        """
        if not self._canvas.tracks:
            return
        track = self._canvas.tracks[0]
        full_span = self._full_bottom - self._full_top
        if full_span <= 0:
            return
        visible_span = track.depth_span
        scrollable_span = max(0.0, full_span - visible_span)
        total_range = 100000
        page_step = max(1, int(min(1.0, visible_span / full_span) * total_range))
        sb = self.verticalScrollBar()
        self._scrollbar_syncing = True
        sb.setRange(0, 0 if scrollable_span <= 0 else total_range)
        sb.setPageStep(page_step)
        sb.setSingleStep(max(1, page_step // 10))
        self._scrollbar_syncing = False

    def _sync_scrollbar_from_depth(self):
        """Update scrollbar position from current depth range top."""
        if self._scrollbar_syncing:
            return
        if not self._canvas.tracks:
            return
        track = self._canvas.tracks[0]
        scrollable_span = max(0.0, (self._full_bottom - self._full_top) - track.depth_span)
        if scrollable_span <= 0:
            return
        ratio = (track.depth_top - self._full_top) / scrollable_span
        self._scrollbar_syncing = True
        self.verticalScrollBar().setValue(int(max(0.0, min(1.0, ratio)) * 100000))
        self._scrollbar_syncing = False

    def _on_vscroll_changed(self, value: int):
        """Update depth range when scrollbar is dragged.

        The scrollbar thumb represents visible_depth / total_depth.
        Moving the scrollbar shifts the visible depth window.
        """
        if self._scrollbar_syncing:
            return
        if not self._canvas.tracks:
            return
        track = self._canvas.tracks[0]
        full_span = self._full_bottom - self._full_top
        if full_span <= 0:
            return
        visible_span = track.depth_span
        scrollable_span = max(0.0, full_span - visible_span)
        if scrollable_span <= 0:
            return
        ratio = max(0.0, min(1.0, value / 100000.0))
        new_top = self._full_top + ratio * scrollable_span
        new_bottom = new_top + visible_span
        self._canvas.set_depth_range(new_top, new_bottom)
