from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QTimer
from PySide6.QtGui import QPainter, QWheelEvent
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from .renderer.canvas import WellLogCanvas
from .renderer.depth_ruler import DepthRuler
from .renderer.interaction import ZoomPanHandler
from .renderer.overlay import CrosshairOverlay
from .renderer.track_base import BaseTrack


class _CrosshairOverlayWidget(QWidget):
    """Transparent overlay that paints the crosshair over the canvas."""

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
        """Trigger a deferred repaint after the canvas has been painted."""
        QTimer.singleShot(0, self.update)


class WellLogView(QScrollArea):
    """Interactive well-log view with zoom/pan, crosshair, and depth ruler.

    The scroll bar controls the visible depth range rather than physical canvas
    scrolling.  This is the installable counterpart of the historical page
    widget and is the widget preview backends must create.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_top = 0.0
        self._full_bottom = 100.0
        self._scrollbar_syncing = False

        self._canvas = WellLogCanvas(self)
        self._zoom_handler = ZoomPanHandler(self._canvas, self)
        self._crosshair = CrosshairOverlay(self._canvas)
        self._canvas.crosshair = self._crosshair

        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setWidget(self._canvas)
        self._canvas.setMouseTracking(True)
        self._canvas.mouse_moved.connect(self._on_mouse_moved)
        self._canvas.depth_range_changed.connect(self._on_canvas_depth_range_changed)

        self._crosshair_widget = _CrosshairOverlayWidget(self._crosshair, self.viewport())
        self._crosshair_widget.setGeometry(self.viewport().rect())
        self._crosshair_widget.show()

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
        self._crosshair_widget.setGeometry(self.viewport().rect())

    def _on_mouse_moved(self, canvas_y: float):
        if not self._canvas.tracks:
            return
        if canvas_y < 0:
            self._crosshair.set_cursor_y(None)
            self._depth_ruler.set_cursor_depth(None)
        else:
            self._crosshair.set_cursor_y(canvas_y)
            self._depth_ruler.set_cursor_depth(self._crosshair.depth_at_y(canvas_y))
        self._canvas.update()
        self._crosshair_widget.schedule_repaint()

    def wheelEvent(self, event):
        """Forward wheel events to the canvas-owned zoom handler."""
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
        self._sync_scrollbar_range()
        self._sync_scrollbar_from_depth()

    def _sync_scrollbar_range(self):
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
        scrollbar = self.verticalScrollBar()
        self._scrollbar_syncing = True
        scrollbar.setRange(0, 0 if scrollable_span <= 0 else total_range)
        scrollbar.setPageStep(page_step)
        scrollbar.setSingleStep(max(1, page_step // 10))
        self._scrollbar_syncing = False

    def _sync_scrollbar_from_depth(self):
        if self._scrollbar_syncing or not self._canvas.tracks:
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
        if self._scrollbar_syncing or not self._canvas.tracks:
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
        self._canvas.set_depth_range(new_top, new_top + visible_span)


__all__ = ["WellLogView"]
