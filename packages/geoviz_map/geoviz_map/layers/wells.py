"""WellsLayer — well markers (dot + halo'd label) with hover + click hit-test."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.models import WellMarker
from geoviz_map.viewport import MapViewport


DOT_BORDER = QColor("#ffffff")
LABEL_HALO = QColor("#ffffff")
LABEL_WITH_DATA = QColor("#0f172a")
LABEL_NO_DATA = QColor("#64748b")
DOT_RADIUS = 7.0  # half of 14px
HOVER_SCALE = 1.2
HIT_RADIUS = 10.0  # generous click target


class WellsLayer(MapLayer):
    def __init__(self, wells: list[WellMarker]):
        self.wells = wells
        self.hovered_name: str | None = None
        # Updated each paint(): list of (name, screen_pt)
        self._screen_positions: list[tuple[str, QPointF]] = []
        self.visible_labels: list[str] = []
        
        # Build spatial index for hit-testing (Phase 2 Audit Task 2)
        self._kdtree = None
        self._tree_names = []
        self._build_index()

    def _build_index(self):
        import numpy as np
        from geoviz_map.projection import lnglat_to_world
        try:
            from scipy.spatial import KDTree
        except ImportError:
            return
            
        pts = []
        for w in self.wells:
            x, y = lnglat_to_world(w.lng, w.lat)
            pts.append([x, y])
            self._tree_names.append(w.name)
            
        if pts:
            self._kdtree = KDTree(np.array(pts))

    def set_hovered(self, name: str | None) -> None:
        self.hovered_name = name

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        if not self.visible:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        positions: list[tuple[str, QPointF]] = []
        visible_labels: list[str] = []
        
        from geoviz_map.collision import CollisionDetector
        from PySide6.QtCore import QRectF
        
        cd = CollisionDetector(margin=2.0)
        
        # Setup font once
        font = QFont("Sans Serif", 9)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()

        for w in self.wells:
            pt = viewport.lnglat_to_screen(w.lng, w.lat)
            positions.append((w.name, pt))

            r = DOT_RADIUS * (HOVER_SCALE if w.name == self.hovered_name else 1.0)
            painter.setPen(QPen(DOT_BORDER, 2.0))
            painter.setBrush(QColor(w.color))
            painter.drawEllipse(pt, r, r)

            # Label collision check
            color = LABEL_WITH_DATA if w.has_data else LABEL_NO_DATA
            text_width = metrics.horizontalAdvance(w.name)
            text_height = metrics.height()
            
            label_pt = QPointF(pt.x() - text_width / 2, pt.y() + r + 14.0)
            rect = QRectF(label_pt.x(), label_pt.y() - metrics.ascent(), text_width, text_height)
            
            if cd.try_add(rect):
                visible_labels.append(w.name)
                self._draw_text_with_halo(painter, label_pt, w.name, color)

        self._screen_positions = positions
        self.visible_labels = visible_labels

    def hit_test(self, screen_pt: QPointF,
                 viewport: MapViewport) -> str | None:
        if self._kdtree is not None:
            # 1. Convert screen target to world space
            wx, wy = viewport.screen_to_world(screen_pt)
            
            # 2. Query nearest point in world space
            # HIT_RADIUS is in pixels. Map to world distance.
            world_radius = HIT_RADIUS / max(1e-6, viewport.scale)
            
            dist, idx = self._kdtree.query([wx, wy], k=1, distance_upper_bound=world_radius)
            
            import numpy as np
            if idx < len(self._tree_names) and dist != np.inf:
                return self._tree_names[idx]
            return None
        else:
            # Fallback to O(N) loop
            positions = [(w.name, viewport.lnglat_to_screen(w.lng, w.lat))
                         for w in self.wells]
            r2 = HIT_RADIUS * HIT_RADIUS
            for name, pt in positions:
                dx = pt.x() - screen_pt.x()
                dy = pt.y() - screen_pt.y()
                if dx * dx + dy * dy <= r2:
                    return name
            return None

    @staticmethod
    def _draw_text_with_halo(painter: QPainter, pt: QPointF, text: str,
                             color: QColor) -> None:
        painter.setPen(QPen(LABEL_HALO, 0))
        for dx, dy in ((-1.5, -1.5), (1.5, -1.5), (-1.5, 1.5), (1.5, 1.5)):
            painter.drawText(QPointF(pt.x() + dx, pt.y() + dy), text)
        painter.setPen(QPen(color, 0))
        painter.drawText(pt, text)
