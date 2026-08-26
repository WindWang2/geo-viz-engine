"""PaintScheduler — debounces rapid update() calls into ~60fps repaints.
BaseLayerPixmapCache — per-layer oversized QPixmap buffer for pan headroom."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap


class PaintScheduler:
    """Coalesce rapid QWidget.update() calls into one repaint per frame."""

    def __init__(self, widget):
        self._widget = widget
        # Parent the timer to the widget so it is destroyed (and its pending
        # timeout cancelled) with the widget. A parentless timer that outlives
        # its widget keeps firing into a deleted QWidget — the exact
        # activateTimers→notifyInternal2-on-dead-object SIGSEGV signature of
        # paleo-workbench #951.
        self._timer = QTimer(widget)
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._do_update)
        self._pending = False

    def schedule(self) -> None:
        if not self._pending:
            self._pending = True
            self._timer.start()

    def _do_update(self) -> None:
        self._pending = False
        try:
            self._widget.update()
        except RuntimeError:
            pass


class BaseLayerPixmapCache:
    """Per-layer pixmap cache with oversized buffer for pan headroom.

    Renders the layer into a 2x-viewport QPixmap. On pan, blit-shifts
    from the cached pixmap instead of re-rendering. Re-renders only on
    zoom change, data change (mark_dirty), or pan > 50% margin.

    Respects ``devicePixelRatio`` so text and lines render at native
    screen density on HiDPI displays — the pixmap is allocated at physical
    pixels and ``setDevicePixelRatio`` is set so the layer paints in
    logical coordinates.

    Subclasses implement ``_make_buf_viewport(vp, buf_w, buf_h)`` to build
    the enlarged buffer viewport for their concrete viewport type.
    """

    def __init__(self, layer):
        self._layer = layer
        self._pixmap: QPixmap | None = None
        self._vp_center: tuple[float, float] = (0.0, 0.0)
        self._vp_scale: float = 0.0
        self._vp_width: int = 0
        self._vp_height: int = 0
        self._dpr: float = 1.0
        self._dirty: bool = True
        self._last_visible: bool = True

    def mark_dirty(self) -> None:
        self._dirty = True

    def paint(self, painter: QPainter, viewport) -> None:
        # Honor the layer's visibility on EVERY paint, not just rerenders:
        # a pan blit of a stale pixmap would otherwise keep a just-hidden
        # layer on screen, and screen/export would disagree (#546).
        visible = bool(getattr(self._layer, "visible", True))
        if visible != self._last_visible:
            self._dirty = True
        self._last_visible = visible
        if not visible:
            self._pixmap = None
            return
        dpr = painter.device().devicePixelRatioF() if painter.device() else 1.0
        if dpr <= 0:
            dpr = 1.0
        if self._needs_rerender(viewport, dpr):
            self._rerender(viewport, dpr)
        self._blit(painter, viewport)

    def _needs_rerender(self, vp, dpr: float) -> bool:
        if self._dirty:
            return True
        if abs(dpr - self._dpr) > 1e-3:
            return True
        if abs(vp.scale - self._vp_scale) > 1e-6:
            return True
        # Viewport resize invalidates the cached pixmap: the cache was rendered
        # for a (buf_w, buf_h) sized buffer matched to the old vp dimensions,
        # and _blit reads a (vp.width, vp.height) rect from it. If the live
        # viewport size changed, rerender to ensure correct centering and
        # blitting coordinates.
        if vp.width != self._vp_width or vp.height != self._vp_height:
            return True
        dx = abs(vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy = abs(vp.center_world[1] - self._vp_center[1]) * vp.scale
        return dx > vp.width * 0.5 or dy > vp.height * 0.5

    def _rerender(self, vp, dpr: float) -> None:
        buf_w = vp.width * 2
        buf_h = vp.height * 2
        phys_w = max(1, round(buf_w * dpr))
        phys_h = max(1, round(buf_h * dpr))
        self._pixmap = QPixmap(phys_w, phys_h)
        self._pixmap.setDevicePixelRatio(dpr)
        self._pixmap.fill(Qt.transparent)
        p = QPainter(self._pixmap)
        try:
            buf_vp = self._make_buf_viewport(vp, buf_w, buf_h)
            self._layer.paint(p, buf_vp)
        finally:
            p.end()
        self._vp_center = vp.center_world
        self._vp_scale = vp.scale
        self._vp_width = vp.width
        self._vp_height = vp.height
        self._dpr = dpr
        self._dirty = False

    def _blit(self, painter: QPainter, vp) -> None:
        if self._pixmap is None:
            return
        dx_px = (vp.center_world[0] - self._vp_center[0]) * vp.scale
        dy_px = (self._vp_center[1] - vp.center_world[1]) * vp.scale

        # Source coordinates in logical space
        src_x = vp.width / 2 + dx_px
        src_y = vp.height / 2 + dy_px

        # Convert logical source coordinates to physical pixels
        src_x_phys = round(src_x * self._dpr)
        src_y_phys = round(src_y * self._dpr)
        src_w_phys = round(vp.width * self._dpr)
        src_h_phys = round(vp.height * self._dpr)

        painter.drawPixmap(0, 0, self._pixmap, src_x_phys, src_y_phys, src_w_phys, src_h_phys)

    def _make_buf_viewport(self, vp, buf_w: int, buf_h: int):
        """Construct the 2x-size buffer viewport for ``vp``; subclass hook."""
        raise NotImplementedError
