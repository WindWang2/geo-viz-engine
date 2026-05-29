"""PaintScheduler — debounces rapid update() calls into 60fps repaints.
LayerPixmapCache — per-layer oversized QPixmap buffer for pan headroom."""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QPixmap, QTransform

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.viewport import PaleoMapViewport


class PaintScheduler:
    """Coalesce rapid update() calls into ~60fps repaints."""

    def __init__(self, widget):
        self._widget = widget
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._do_update)
        self._pending = False

    def schedule(self) -> None:
        """Request a repaint. Multiple calls before timer fires = one repaint."""
        if not self._pending:
            self._pending = True
            self._timer.start()

    def _do_update(self) -> None:
        self._pending = False
        self._widget.update()


class LayerPixmapCache:
    """Per-layer pixmap cache with oversized buffer for pan headroom.

    Renders the layer into a 2x-viewport QPixmap. On pan, blit-shifts
    from the cached pixmap instead of re-rendering. Re-renders only on
    zoom change, data change (mark_dirty), or pan > 50% margin.
    """

    def __init__(self, layer):
        self._layer = layer
        self._pixmap: QPixmap | None = None
        self._vp_center: tuple[float, float] = (0.0, 0.0)
        self._vp_scale: float = 0.0
        self._dirty: bool = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if self._needs_rerender(viewport):
            self._rerender(viewport)
        self._blit(painter, viewport)

    def _needs_rerender(self, vp: PaleoMapViewport) -> bool:
        if self._dirty:
            return True
        if abs(vp.scale - self._vp_scale) > 1e-6:
            return True
        dx = abs(vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy = abs(vp.center_world[1] - self._vp_center[1]) * vp.scale
        return dx > vp.width * 0.5 or dy > vp.height * 0.5

    def _rerender(self, vp: PaleoMapViewport) -> None:
        buf_w = vp.width * 2
        buf_h = vp.height * 2
        self._pixmap = QPixmap(buf_w, buf_h)
        self._pixmap.fill(Qt.transparent)
        p = QPainter(self._pixmap)
        try:
            buf_vp = PaleoMapViewport(
                center_lng=vp.center_world[0],
                center_lat=vp.center_world[1],
                zoom=vp.zoom,
                width=buf_w,
                height=buf_h,
            )
            self._layer.paint(p, buf_vp)
        finally:
            p.end()
        self._vp_center = vp.center_world
        self._vp_scale = vp.scale
        self._dirty = False

    def _blit(self, painter: QPainter, vp: PaleoMapViewport) -> None:
        if self._pixmap is None:
            return
        dx_px = (vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy_px = (self._vp_center[1] - vp.center_world[1]) * vp.scale
        src_x = int(vp.width / 2 + dx_px)
        src_y = int(vp.height / 2 + dy_px)
        painter.drawPixmap(0, 0, self._pixmap, src_x, src_y, vp.width, vp.height)
