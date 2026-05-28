"""ZoomPanHandler — drag pan + cursor-anchored wheel zoom for PaleoMap."""
from __future__ import annotations

from PySide6.QtCore import QPointF

from geoviz_paleo_map.viewport import PaleoMapViewport


class ZoomPanHandler:
    """Mutates a PaleoMapViewport based on mouse drag and wheel events."""

    def __init__(self, viewport: PaleoMapViewport,
                 min_zoom: float = 0.5, max_zoom: float = 10.0):
        self.viewport = viewport
        self.min_zoom = min_zoom
        self.max_zoom = max_zoom
        self._drag_anchor: QPointF | None = None

    def start_drag(self, pt: QPointF) -> None:
        self._drag_anchor = QPointF(pt)

    def update_drag(self, pt: QPointF) -> None:
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

    def wheel_zoom(self, cursor_screen: QPointF, delta_steps: float) -> None:
        before = self.viewport.screen_to_world(cursor_screen)
        new_zoom = max(self.min_zoom,
                       min(self.max_zoom, self.viewport.zoom + delta_steps))
        if new_zoom == self.viewport.zoom:
            return
        self.viewport.zoom = new_zoom
        after = self.viewport.screen_to_world(cursor_screen)
        self.viewport.pan_world(before[0] - after[0], before[1] - after[1])
