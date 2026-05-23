from __future__ import annotations

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QMouseEvent
from PySide6.QtWidgets import QScrollArea

from geoviz_well_log import (
    WellLogCanvas, ZoomPanHandler, CrosshairOverlay,
)
from geoviz_well_log.renderer.track_base import BaseTrack


class QPainterWidget(QScrollArea):
    """Scroll area wrapping WellLogCanvas with zoom/pan and crosshair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_top = 0.0
        self._full_bottom = 100.0

        self._canvas = WellLogCanvas(self)
        self._zoom_handler = ZoomPanHandler(self._canvas, self)
        self._crosshair = CrosshairOverlay(self._canvas)

        self.setWidget(self._canvas)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._canvas.setMouseTracking(True)
        self._canvas.installEventFilter(self)

    @property
    def canvas(self) -> WellLogCanvas:
        return self._canvas

    def set_tracks(self, tracks: list[BaseTrack]):
        self._canvas.set_tracks(tracks)
        if tracks:
            self._full_top = tracks[0].depth_top
            self._full_bottom = tracks[0].depth_bottom
            self._zoom_handler.set_full_range(self._full_top, self._full_bottom)
        self._update_canvas_size()

    def set_depth_range(self, top: float, bottom: float):
        self._canvas.set_depth_range(top, bottom)

    def reset_view(self):
        self._canvas.set_depth_range(self._full_top, self._full_bottom)

    def _update_canvas_size(self):
        w = self._canvas.total_width
        h = max(self.height(), 600)
        self._canvas.setFixedSize(w, h)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_canvas_size()

    def eventFilter(self, obj, event):
        if obj is self._canvas:
            if isinstance(event, QMouseEvent) and event.type() == event.Type.MouseMove:
                self._crosshair.set_cursor_y(event.position().y())
            elif isinstance(event, QMouseEvent) and event.type() == event.Type.Leave:
                self._crosshair.set_cursor_y(None)
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._crosshair.visible and self._canvas.tracks:
            painter = QPainter(self.viewport())
            self._crosshair.paint_overlay(painter, QRectF(self.viewport().rect()))
            painter.end()
