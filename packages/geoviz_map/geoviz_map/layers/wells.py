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

    def set_hovered(self, name: str | None) -> None:
        self.hovered_name = name

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        positions: list[tuple[str, QPointF]] = []
        for w in self.wells:
            pt = viewport.lnglat_to_screen(w.lng, w.lat)
            positions.append((w.name, pt))

            r = DOT_RADIUS * (HOVER_SCALE if w.name == self.hovered_name else 1.0)
            painter.setPen(QPen(DOT_BORDER, 2.0))
            painter.setBrush(QColor(w.color))
            painter.drawEllipse(pt, r, r)

            # Label below dot
            font = QFont("Sans Serif", 9)
            font.setBold(True)
            painter.setFont(font)
            color = LABEL_WITH_DATA if w.has_data else LABEL_NO_DATA
            label_pt = QPointF(pt.x(), pt.y() + r + 14.0)
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(w.name)
            label_pt = QPointF(label_pt.x() - text_width / 2, label_pt.y())
            self._draw_text_with_halo(painter, label_pt, w.name, color)

        self._screen_positions = positions

    def hit_test(self, screen_pt: QPointF,
                 viewport: MapViewport) -> str | None:
        # Always re-project from the live viewport. The cached
        # `_screen_positions` was computed inside the oversized buffer used by
        # LayerPixmapCache, so its pixel coordinates do not match the
        # user-visible viewport.
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
