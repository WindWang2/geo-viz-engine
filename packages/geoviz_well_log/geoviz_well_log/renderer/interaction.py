from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QPointF, QObject
from PySide6.QtGui import QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canvas import WellLogCanvas


class ZoomPanHandler(QObject):
    """Event filter for zoom (wheel) and pan (middle-drag / Ctrl+left-drag) on WellLogCanvas."""

    _ZOOM_FACTOR = 0.2

    def __init__(self, canvas: WellLogCanvas, parent=None):
        super().__init__(parent)
        self._canvas = canvas
        self._full_top = 0.0
        self._full_bottom = 100.0
        self._dragging = False
        self._last_y = 0.0
        canvas.installEventFilter(self)

    def set_full_range(self, top: float, bottom: float):
        """Set the data bounds for clamping zoom/pan."""
        self._full_top = top
        self._full_bottom = bottom

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if obj is not self._canvas:
            return False

        if event.type() == QEvent.Type.Wheel:
            return self._handle_wheel(event)
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            return self._handle_double_click(event)
        elif event.type() == QEvent.Type.MouseButtonPress:
            return self._handle_press(event)
        elif event.type() == QEvent.Type.MouseMove:
            return self._handle_move(event)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            return self._handle_release(event)

        return False

    def _handle_wheel(self, event: QWheelEvent) -> bool:
        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None:
            return False

        top = track.depth_top
        bottom = track.depth_bottom
        span = bottom - top
        if span <= 0:
            return False

        header_h = max((getattr(t, "header_height", 56) for t in self._canvas.tracks), default=56)
        if callable(header_h):
            try:
                header_h = max((t.header_height() for t in self._canvas.tracks), default=56)
            except Exception:
                header_h = 56

        canvas_h = self._canvas.height()
        content_h = max(canvas_h - header_h, 1)
        mouse_y = event.position().y()
        y_ratio = max(0.0, min(1.0, (mouse_y - header_h) / content_h))
        cursor_depth = top + y_ratio * span

        delta = event.angleDelta().y()
        if delta > 0:
            factor = self._ZOOM_FACTOR
        else:
            factor = -self._ZOOM_FACTOR

        new_span = span * (1 - factor)
        new_top = cursor_depth - y_ratio * new_span
        new_bottom = new_top + new_span

        new_top = max(new_top, self._full_top)
        new_bottom = min(new_bottom, self._full_bottom)
        if new_bottom - new_top < 1.0:
            new_bottom = new_top + 1.0

        self._canvas.set_depth_range(new_top, new_bottom)
        return True

    def _handle_double_click(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            self._canvas.set_depth_range(self._full_top, self._full_bottom)
            return True
        return False

    def _handle_press(self, event: QMouseEvent) -> bool:
        is_pan = (event.button() == Qt.MouseButton.MiddleButton or
                  (event.button() == Qt.MouseButton.LeftButton and
                   event.modifiers() & Qt.KeyboardModifier.ControlModifier))
        if is_pan:
            self._dragging = True
            self._last_y = event.position().y()
            return True
        return False

    def _handle_move(self, event: QMouseEvent) -> bool:
        if not self._dragging:
            return False

        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None:
            return False

        dy = event.position().y() - self._last_y
        self._last_y = event.position().y()

        span = track.depth_span
        depth_per_pixel = span / self._canvas.height() if self._canvas.height() > 0 else 0
        delta = -dy * depth_per_pixel

        new_top = track.depth_top + delta
        new_bottom = track.depth_bottom + delta

        if new_top < self._full_top:
            new_bottom += self._full_top - new_top
            new_top = self._full_top
        if new_bottom > self._full_bottom:
            new_top -= new_bottom - self._full_bottom
            new_bottom = self._full_bottom

        if new_bottom - new_top >= 1.0:
            self._canvas.set_depth_range(new_top, new_bottom)
        return True

    def _handle_release(self, event: QMouseEvent) -> bool:
        if self._dragging:
            self._dragging = False
            return True
        return False
