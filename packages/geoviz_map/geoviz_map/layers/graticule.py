"""GraticuleLayer — lng/lat dashed grid."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen

from geoviz_map.layers.base import MapLayer
from geoviz_map.viewport import MapViewport


class GraticuleLayer(MapLayer):
    def __init__(self,
                 lng_min: float = 104, lng_max: float = 126, lng_step: float = 2,
                 lat_min: float = 14, lat_max: float = 42, lat_step: float = 2,
                 color: str = "#0284c7", opacity: float = 0.12,
                 width: float = 0.8):
        self.lng_min = lng_min
        self.lng_max = lng_max
        self.lng_step = lng_step
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.lat_step = lat_step
        self.color = QColor(color)
        self.color.setAlphaF(opacity)
        self.width = width

    def lng_lines(self) -> list[float]:
        out: list[float] = []
        v = self.lng_min
        while v <= self.lng_max + 1e-9:
            out.append(round(v, 6))
            v += self.lng_step
        return out

    def lat_lines(self) -> list[float]:
        out: list[float] = []
        v = self.lat_min
        while v <= self.lat_max + 1e-9:
            out.append(round(v, 6))
            v += self.lat_step
        return out

    def paint(self, painter: QPainter, viewport: MapViewport) -> None:
        pen = QPen(self.color, self.width)
        pen.setStyle(Qt.PenStyle.CustomDashLine)
        pen.setDashPattern([4.0, 4.0])
        painter.setPen(pen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Vertical (lng) lines span lat_min..lat_max
        for lng in self.lng_lines():
            p1 = viewport.lnglat_to_screen(lng, self.lat_min)
            p2 = viewport.lnglat_to_screen(lng, self.lat_max)
            painter.drawLine(p1, p2)

        # Horizontal (lat) lines span lng_min..lng_max
        for lat in self.lat_lines():
            p1 = viewport.lnglat_to_screen(self.lng_min, lat)
            p2 = viewport.lnglat_to_screen(self.lng_max, lat)
            painter.drawLine(p1, p2)
