"""BaseZoomPanHandler — drag pan + cursor-anchored wheel zoom.

Shared by geoviz_map.ZoomPanHandler and geoviz_paleo_map.ZoomPanHandler;
subclasses only supply their viewport type and the zoom limits.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF


class BaseZoomPanHandler:
    """Mutates a viewport based on mouse drag and wheel events.

    Stateless wrt Qt events — call from widget event handlers.
    """

    def __init__(self, viewport, min_zoom: float, max_zoom: float):
        self.viewport = viewport
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self.enabled: bool = True
        self._drag_anchor: QPointF | None = None

    # Drag pan -----------------------------------------------------------
    def start_drag(self, pt: QPointF) -> None:
        if not self.enabled:
            return
        self._drag_anchor = QPointF(pt)

    def update_drag(self, pt: QPointF) -> None:
        if not self.enabled:
            return
        if self._drag_anchor is None:
            return
        dx = pt.x() - self._drag_anchor.x()
        dy = pt.y() - self._drag_anchor.y()
        self.viewport.pan_pixels(dx, dy)
        self._drag_anchor = QPointF(pt)

    def end_drag(self) -> None:
        self._drag_anchor = None

    def is_dragging(self) -> bool:
        return self._drag_anchor is not None

    # Wheel zoom ---------------------------------------------------------
    def wheel_zoom(self, cursor_screen: QPointF, delta_steps: float) -> None:
        """Zoom by `delta_steps` levels (positive = zoom in), anchored at cursor.

        The world point under `cursor_screen` is invariant before and after.
        """
        before_world = self.viewport.screen_to_world(cursor_screen)
        new_zoom = max(self.min_zoom,
                       min(self.max_zoom, self.viewport.zoom + delta_steps))
        if new_zoom == self.viewport.zoom:
            return
        self.viewport.zoom = new_zoom
        # Re-anchor: shift center so cursor stays over the same world point
        after_world = self.viewport.screen_to_world(cursor_screen)
        dx = before_world[0] - after_world[0]
        dy = before_world[1] - after_world[1]
        self.viewport.pan_world(dx, dy)
