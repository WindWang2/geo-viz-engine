"""EditOverlayLayer — vertex handles, edge highlights, and shared-vertex indicators."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QBrush

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.topology import TopologyModel
from geoviz_paleo_map.viewport import PaleoMapViewport


class EditOverlayLayer(PaleoLayer):
    """Renders vertex handles and edge highlights for the selected polygon."""

    HANDLE_RADIUS = 4.0        # px (screen space)
    HANDLE_HOVER_RADIUS = 5.0
    EDGE_HIGHLIGHT_DIST = 8.0  # px threshold for edge hover

    def __init__(self) -> None:
        self._model: TopologyModel | None = None
        self._selected_id: str | None = None
        self._hovered_vertex_id: int | None = None
        self._hovered_edge: tuple[int, int] | None = None
        self._mouse_screen: QPointF | None = None

    def set_model(self, model: TopologyModel | None) -> None:
        self._model = model

    def set_selected(self, feature_id: str | None) -> None:
        self._selected_id = feature_id

    def set_mouse_position(self, screen_pt: QPointF | None) -> None:
        self._mouse_screen = screen_pt

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if self._model is None or self._selected_id is None:
            return

        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        s = viewport.scale
        cx, cy = viewport.center_world
        ox = viewport.width / 2
        oy = viewport.height / 2

        # Update hover state
        self._update_hover(viewport)

        # Draw edge highlight
        if self._hovered_edge is not None:
            self._draw_edge_highlight(painter, viewport, s, cx, cy, ox, oy)

        # Draw vertex handles
        for ring in ref.rings:
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v is None:
                    continue
                sx = (v.x - cx) * s + ox
                sy = (cy - v.y) * s + oy
                is_hovered = vid == self._hovered_vertex_id
                is_shared = self._is_vertex_shared(vid)
                self._draw_handle(painter, sx, sy, is_hovered, is_shared)

        painter.restore()

    def _draw_handle(self, painter: QPainter, sx: float, sy: float,
                     is_hovered: bool, is_shared: bool) -> None:
        radius = self.HANDLE_HOVER_RADIUS if is_hovered else self.HANDLE_RADIUS

        if is_hovered:
            painter.setPen(QPen(QColor("#1a56db"), 2.0))
            painter.setBrush(QBrush(QColor("#3182ce")))
        else:
            painter.setPen(QPen(QColor("#2d3748"), 1.5))
            painter.setBrush(QBrush(QColor("#ffffff")))

        painter.drawEllipse(QPointF(sx, sy), radius, radius)

        # Shared indicator: outer ring
        if is_shared and not is_hovered:
            painter.setPen(QPen(QColor("#e53e3e"), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(sx, sy), radius + 2, radius + 2)

    def _draw_edge_highlight(self, painter: QPainter, viewport: PaleoMapViewport,
                             s: float, cx: float, cy: float, ox: float, oy: float) -> None:
        if self._hovered_edge is None or self._model is None:
            return
        v1 = self._model.get_vertex(self._hovered_edge[0])
        v2 = self._model.get_vertex(self._hovered_edge[1])
        if v1 is None or v2 is None:
            return

        sx1 = (v1.x - cx) * s + ox
        sy1 = (cy - v1.y) * s + oy
        sx2 = (v2.x - cx) * s + ox
        sy2 = (cy - v2.y) * s + oy

        pen = QPen(QColor("#3182ce"), 2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawLine(QPointF(sx1, sy1), QPointF(sx2, sy2))

    def _update_hover(self, viewport: PaleoMapViewport) -> None:
        self._hovered_vertex_id = None
        self._hovered_edge = None

        if self._model is None or self._selected_id is None or self._mouse_screen is None:
            return

        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return

        mx = self._mouse_screen.x()
        my = self._mouse_screen.y()

        # Check vertex handles first (priority over edges)
        for ring in ref.rings:
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v is None:
                    continue
                sx, sy = viewport.world_to_screen(v.x, v.y)
                dist = ((sx - mx) ** 2 + (sy - my) ** 2) ** 0.5
                if dist < self.HANDLE_HOVER_RADIUS + 4:
                    self._hovered_vertex_id = vid
                    return

        # Check edges
        best_dist = self.EDGE_HIGHLIGHT_DIST
        for ring in ref.rings:
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                v1 = self._model.get_vertex(ids[i])
                v2 = self._model.get_vertex(ids[i + 1])
                if v1 is None or v2 is None:
                    continue
                dist = self._point_to_segment_dist(
                    mx, my,
                    *viewport.world_to_screen(v1.x, v1.y),
                    *viewport.world_to_screen(v2.x, v2.y),
                )
                if dist < best_dist:
                    best_dist = dist
                    self._hovered_edge = (ids[i], ids[i + 1])

    def _is_vertex_shared(self, vid: int) -> bool:
        if self._model is None:
            return False
        # O(1) reverse-index lookup: shared = referenced by more than one feature
        return len(self._model._vertex_to_features.get(vid, ())) > 1

    def hit_test_vertex(self, screen_pt: QPointF,
                        viewport: PaleoMapViewport) -> int | None:
        """Return the vertex ID under the cursor, or None."""
        if self._model is None or self._selected_id is None:
            return None
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        mx, my = screen_pt.x(), screen_pt.y()
        for ring in ref.rings:
            for vid in ring.vertex_ids:
                v = self._model.get_vertex(vid)
                if v is None:
                    continue
                sx, sy = viewport.world_to_screen(v.x, v.y)
                dist = ((sx - mx) ** 2 + (sy - my) ** 2) ** 0.5
                if dist < self.HANDLE_HOVER_RADIUS + 4:
                    return vid
        return None

    def hit_test_edge(self, screen_pt: QPointF,
                      viewport: PaleoMapViewport) -> tuple[int, int] | None:
        """Return the edge (v1_id, v2_id) nearest to cursor, or None."""
        if self._model is None or self._selected_id is None:
            return None
        ref = self._model.get_feature(self._selected_id)
        if ref is None:
            return None
        mx, my = screen_pt.x(), screen_pt.y()
        best_dist = self.EDGE_HIGHLIGHT_DIST
        best_edge = None
        for ring in ref.rings:
            ids = ring.vertex_ids
            for i in range(len(ids) - 1):
                v1 = self._model.get_vertex(ids[i])
                v2 = self._model.get_vertex(ids[i + 1])
                if v1 is None or v2 is None:
                    continue
                dist = self._point_to_segment_dist(
                    mx, my,
                    *viewport.world_to_screen(v1.x, v1.y),
                    *viewport.world_to_screen(v2.x, v2.y),
                )
                if dist < best_dist:
                    best_dist = dist
                    best_edge = (ids[i], ids[i + 1])
        return best_edge

    @staticmethod
    def _point_to_segment_dist(px: float, py: float,
                               x1: float, y1: float,
                               x2: float, y2: float) -> float:
        dx = x2 - x1
        dy = y2 - y1
        len_sq = dx * dx + dy * dy
        if len_sq < 1e-12:
            return ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / len_sq))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5
