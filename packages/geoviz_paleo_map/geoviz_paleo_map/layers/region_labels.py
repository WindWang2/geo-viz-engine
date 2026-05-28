"""RegionLabelsLayer — facies name centered at each polygon's bbox center
with contrast-aware text color."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen

from geoviz_paleo_map.layers.base import PaleoLayer
from geoviz_paleo_map.projection import lnglat_to_world
from geoviz_paleo_map.style import FaciesStyleResolver
from geoviz_paleo_map.viewport import PaleoMapViewport


@dataclass
class _LabelItem:
    text: str
    centroid_world: tuple[float, float]
    facies_name: str
    bbox_world: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y


def _luminance(c: QColor) -> float:
    r = c.red() / 255.0
    g = c.green() / 255.0
    b = c.blue() / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_color(bg: QColor) -> QColor:
    """Return a dark text color on light backgrounds and vice versa."""
    return QColor("#2d3748") if _luminance(bg) > 0.5 else QColor("#f7fafc")


class RegionLabelsLayer(PaleoLayer):
    def __init__(self, features: list[dict], style_resolver: FaciesStyleResolver,
                 font_size: int = 9):
        self._resolver = style_resolver
        self._font_size = font_size
        self._items: list[_LabelItem] = []
        for feat in features:
            geom = feat.get("geometry") or {}
            gtype = geom.get("type")
            if gtype == "Polygon":
                rings = [geom["coordinates"]]
            elif gtype == "MultiPolygon":
                rings = geom["coordinates"]
            else:
                continue
            props = feat.get("properties") or {}
            text = props.get("name") or props.get("facies") or ""
            facies = props.get("facies") or props.get("name") or ""
            if not text:
                continue
            # Centroid = bbox center of outer ring
            for poly in rings:
                outer = poly[0] if poly else []
                if len(outer) < 3:
                    continue
                xs = [p[0] for p in outer]
                ys = [p[1] for p in outer]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                cx = (min_x + max_x) / 2
                cy = (min_y + max_y) / 2
                world_pt = lnglat_to_world(cx, cy)
                self._items.append(_LabelItem(text=text,
                                              centroid_world=world_pt,
                                              facies_name=facies,
                                              bbox_world=(min_x, min_y, max_x, max_y)))
                break  # one label per feature (use first polygon's centroid)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        font = QFont("Sans Serif", self._font_size)
        font.setBold(True)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_h = metrics.height()
        for item in self._items:
            # Skip labels whose polygon is too small on screen
            bmin = viewport.world_to_screen(item.bbox_world[0], item.bbox_world[3])
            bmax = viewport.world_to_screen(item.bbox_world[2], item.bbox_world[1])
            sw = abs(bmax.x() - bmin.x())
            sh = abs(bmax.y() - bmin.y())
            text_w = metrics.horizontalAdvance(item.text)
            if sw < text_w * 1.2 or sh < text_h * 1.5:
                continue
            screen = viewport.world_to_screen(*item.centroid_world)
            style = self._resolver.resolve(item.facies_name)
            color = contrast_color(style.base_color)
            painter.setPen(QPen(color, 0))
            painter.drawText(QPointF(screen.x() - text_w / 2,
                                     screen.y() + metrics.ascent() / 2),
                             item.text)
