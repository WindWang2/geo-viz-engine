"""PlacementController — tool-mode state machine for free-graphics placement.

Mode groups (spec §3.3):

* **click-drag box** — rect, ellipse, north_arrow, scale_bar:
  press → drag (live preview) → release creates the item.
* **single-click** — text, image: one click drops a default-size item
  (image placement opens the host's file picker first).
* **freehand** — press → move (accumulate points) → release finalises.
* **polygon** — click to add vertices, double-click / Enter to close.
* **select** — default; the bare QGraphicsView selection/move/resize path.

The controller owns no UI; the window wires tool-bar buttons to
:meth:`set_mode` and routes view mouse / key events to the controller's
``begin_click`` / ``add_point`` / ``end_click`` / ``finish_polygon`` /
``cancel`` methods. All coordinates are scene (paper-absolute mm) units.

Deviation from the plan: ``cancel`` also returns the window to ``select``
mode (the plan's Esc test requires it), and ``set_mode`` resets its own
state instead of calling ``cancel`` so the two never recurse.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF

from geoviz_paleo_map.cartography.items.free import ITEM_CLASSES
from geoviz_paleo_map.cartography.items.free.image_item import FreeImageItem
from geoviz_paleo_map.cartography.items.free.text_item import FreeTextItem

CLICK_BOX_KINDS = ("rect", "ellipse", "north_arrow", "scale_bar")
DEFAULT_BOX_W = 40.0
DEFAULT_BOX_H = 20.0
MIN_BOX_MM = 2.0


class PlacementController:
    """Mode-driven placement state machine (no Qt widget of its own)."""

    def __init__(self, scene, parent_window=None) -> None:
        self._scene = scene
        self._win = parent_window
        self._mode = "select"
        self._active = False
        self._points: list[QPointF] = []

    # -- mode -----------------------------------------------------------

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode == self._mode:
            return
        self._active = False
        self._points = []
        self._mode = mode

    # -- click protocol (called by the window's eventFilter) -----------

    def begin_click(self, scene_pos: QPointF) -> None:
        if self._mode == "select":
            return
        if self._mode == "polygon" and self._active:
            # Click-to-add-vertices interaction: each press appends; only the
            # first press initializes the list. The unconditional reset below
            # used to wipe the accumulated vertices on every click, so a
            # click-placed polygon could never reach three points (#547).
            # Skip a press at (nearly) the same position as the last vertex —
            # the press that precedes a closing double-click lands there.
            p = self._clamp(scene_pos)
            if not self._points or (p - self._points[-1]).manhattanLength() > 1e-6:
                self._points.append(p)
            return
        self._active = True
        self._points = [self._clamp(scene_pos)]
        if self._mode in CLICK_BOX_KINDS:
            # box: wait for drag end; nothing added yet
            return
        if self._mode == "text":
            self._place_text(self._clamp(scene_pos))
            self._finish_active()
            return
        if self._mode == "image":
            self._place_image(self._clamp(scene_pos))
            self._finish_active()
            return
        if self._mode in ("freehand", "polygon"):
            return  # accumulate on add_point

    def add_point(self, scene_pos: QPointF) -> None:
        if not self._active:
            return
        if self._mode == "freehand":
            # Freehand accumulates the drag path. Polygon vertices come from
            # begin_click presses only: moves between clicks are not even
            # delivered without mouse tracking, and a press-drag would
            # otherwise spray duplicate vertices along the path.
            self._points.append(self._clamp(scene_pos))

    def end_click(self, scene_pos: QPointF) -> None:
        if not self._active:
            return
        if self._mode in CLICK_BOX_KINDS:
            start = self._points[0]
            end = self._clamp(scene_pos)
            rect = QRectF(start, end).normalized()
            if rect.width() < MIN_BOX_MM or rect.height() < MIN_BOX_MM:
                # treated as a click: default-size box at the click point
                rect = QRectF(start.x(), start.y(), DEFAULT_BOX_W, DEFAULT_BOX_H)
            self._place_box(rect)
            self._finish_active()
        elif self._mode == "freehand":
            if len(self._points) >= 2:
                self._place_points("freehand")
            self._finish_active()
        elif self._mode == "polygon":
            pass  # polygon waits for finish_polygon() on double-click / Enter

    def finish_polygon(self) -> None:
        if not self._active or self._mode != "polygon":
            return
        if len(self._points) >= 3:
            self._place_points("polygon")
        self._finish_active()

    def cancel(self) -> None:
        """Abort the current placement and return the window to select mode."""
        self._active = False
        self._points = []
        if self._win is not None:
            self._win.set_tool_mode("select")

    # -- helpers --------------------------------------------------------

    def _finish_active(self) -> None:
        self._active = False
        self._points = []
        # Auto-return to select after each placement.
        if self._win is not None:
            self._win.set_tool_mode("select")

    def _clamp(self, pos: QPointF) -> QPointF:
        paper = self._scene.paper_rect()
        x = max(paper.left(), min(pos.x(), paper.right()))
        y = max(paper.top(), min(pos.y(), paper.bottom()))
        return QPointF(x, y)

    def _clamp_rect(self, rect: QRectF) -> QRectF:
        paper = self._scene.paper_rect()
        x = max(paper.left(), rect.x())
        y = max(paper.top(), rect.y())
        w = min(rect.width(), paper.right() - x)
        h = min(rect.height(), paper.bottom() - y)
        return QRectF(x, y, max(MIN_BOX_MM, w), max(MIN_BOX_MM, h))

    def _place_box(self, rect: QRectF) -> None:
        rect = self._clamp_rect(rect)
        cls = ITEM_CLASSES[self._mode]
        item = cls(rect)
        self._scene.addItem(item)
        self._scene.clearSelection()
        item.setSelected(True)

    def _place_text(self, pos: QPointF) -> None:
        item = FreeTextItem(pos, text="文本")
        self._scene.addItem(item)
        self._scene.clearSelection()
        item.setSelected(True)

    def _place_image(self, pos: QPointF) -> None:
        # Window handles the QFileDialog; if it returns "" (cancelled or
        # local test), we create a placeholder at the click point.
        path = ""
        if self._win is not None:
            path = self._win._pick_image_path()
        rect = QRectF(pos.x(), pos.y(), DEFAULT_BOX_W, DEFAULT_BOX_H)
        item = FreeImageItem(rect, path=path)
        self._scene.addItem(item)
        self._scene.clearSelection()
        item.setSelected(True)

    def _place_points(self, kind: str) -> None:
        cls = ITEM_CLASSES[kind]
        pts = [(p.x(), p.y()) for p in self._points]
        item = cls(pts)
        self._scene.addItem(item)
        self._scene.clearSelection()
        item.setSelected(True)
