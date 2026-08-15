"""RegionLabelsLayer — facies name centered at each polygon's centroid
with contrast-aware text color."""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen

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
    is_locked: bool = False
    feature_id: str = ""
    level: str = ""


def _luminance(c: QColor) -> float:
    r = c.red() / 255.0
    g = c.green() / 255.0
    b = c.blue() / 255.0
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_color(bg: QColor) -> QColor:
    """Return a dark text color on light backgrounds and vice versa."""
    return QColor("#2d3748") if _luminance(bg) > 0.5 else QColor("#f7fafc")


def _ring_centroid(coords: list) -> tuple[float, float] | None:
    """Shoelace-formula centroid of a ring; None for degenerate (zero-area) rings."""
    n = len(coords)
    if n < 3:
        return None
    area2 = 0.0
    sum_x = 0.0
    sum_y = 0.0
    for i in range(n):
        x0, y0 = coords[i][0], coords[i][1]
        x1, y1 = coords[(i + 1) % n][0], coords[(i + 1) % n][1]
        cross = x0 * y1 - x1 * y0
        area2 += cross
        sum_x += (x0 + x1) * cross
        sum_y += (y0 + y1) * cross
    if abs(area2) < 1e-12:
        return None
    return sum_x / (3.0 * area2), sum_y / (3.0 * area2)


def _point_in_ring(px: float, py: float, coords: list) -> bool:
    """Ray-casting point-in-polygon test for a (possibly unclosed) ring."""
    inside = False
    n = len(coords)
    for i in range(n):
        x0, y0 = coords[i][0], coords[i][1]
        x1, y1 = coords[(i + 1) % n][0], coords[(i + 1) % n][1]
        if (y0 > py) != (y1 > py):
            x_at = x0 + (py - y0) * (x1 - x0) / (y1 - y0)
            if px < x_at:
                inside = not inside
    return inside


class RegionLabelsLayer(PaleoLayer):
    def __init__(self, features: list[dict], style_resolver: FaciesStyleResolver,
                 font_size: int = 9, locked_ids: set[str] | None = None):
        self._resolver = style_resolver
        self._font_size = font_size
        self._locked_ids = locked_ids or set()
        self._items: list[_LabelItem] = []
        self.visible_labels: list[str] = []
        # Screen rects occupied by chrome (legend/north arrow/scale bar). The
        # canvas/export populates this before paint so labels steer clear of
        # decorations. Reserved each frame because chrome anchors to viewport size.
        self.chrome_rects: list[QRectF] = []
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
            feature_id = props.get("id", "")
            level = props.get("level", "")
            if not text:
                continue
            is_locked = (feature_id in self._locked_ids)
            # Anchor = outer-ring centroid (shoelace); concave polygons whose
            # centroid falls outside (or in a hole) fall back to bbox center.
            for poly in rings:
                outer = poly[0] if poly else []
                if len(outer) < 3:
                    continue
                xs = [p[0] for p in outer]
                ys = [p[1] for p in outer]
                min_x, max_x = min(xs), max(xs)
                min_y, max_y = min(ys), max(ys)
                centroid = _ring_centroid(outer)
                if centroid is not None and _point_in_ring(centroid[0], centroid[1], outer) \
                        and not any(_point_in_ring(centroid[0], centroid[1], hole)
                                    for hole in poly[1:]):
                    cx, cy = centroid
                else:
                    cx = (min_x + max_x) / 2
                    cy = (min_y + max_y) / 2
                world_pt = lnglat_to_world(cx, cy)
                self._items.append(_LabelItem(text=text,
                                              centroid_world=world_pt,
                                              facies_name=facies,
                                              bbox_world=(min_x, min_y, max_x, max_y),
                                              is_locked=is_locked,
                                              feature_id=feature_id,
                                              level=level))
                break  # one label per feature (use first polygon's centroid)

    def paint(self, painter: QPainter, viewport: PaleoMapViewport) -> None:
        if not self.visible:
            return
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        from geoviz_paleo_map.collision import CollisionDetector
        cd = CollisionDetector(margin=2.0)
        # Pre-register chrome footprints so labels never collide with the
        # legend / north arrow / scale bar (decoration-priority placement).
        for rect in self.chrome_rects:
            cd.try_add(rect)
        visible_labels = []

        default_sizes = {"facies": 11, "sub_facies": 8, "micro_facies": 7}
        # Dynamic zoom scaling: base zoom=4 (scale=8), text grows with sqrt(scale)
        import math
        zoom_factor = max(0.5, min(3.0, math.sqrt(viewport.scale / 8.0)))

        for item in self._items:
            # Resolve font size dynamically based on its hierarchy level, falling back to self._font_size
            lvl_size = default_sizes.get(item.level, self._font_size)
            lvl_size = int(lvl_size * zoom_factor)
            
            font = QFont("Sans Serif", lvl_size)
            font.setBold(True)
            painter.setFont(font)
            metrics = painter.fontMetrics()
            text_h = metrics.height()
            
            # Skip labels whose polygon is too small on screen
            bmin = viewport.world_to_screen(item.bbox_world[0], item.bbox_world[3])
            bmax = viewport.world_to_screen(item.bbox_world[2], item.bbox_world[1])
            sw = abs(bmax.x() - bmin.x())
            sh = abs(bmax.y() - bmin.y())
            
            display_text = f"🔒 {item.text}" if item.is_locked else item.text
            text_w = metrics.horizontalAdvance(display_text)
            
            if sw < text_w * 1.1 or sh < text_h * 1.3:
                continue
            screen = viewport.world_to_screen(*item.centroid_world)
            style = self._resolver.resolve(item.facies_name)
            
            badge_rect = QRectF(
                screen.x() - text_w / 2 - 6,
                screen.y() - text_h / 2 - 2,
                text_w + 12,
                text_h + 4
            )
            if not cd.try_add(badge_rect):
                continue
            visible_labels.append(item.text)
            
            if item.is_locked:
                # Premium rounded rectangle badge container for locked labels
                badge_rect = QRectF(
                    screen.x() - text_w / 2 - 6,
                    screen.y() - text_h / 2 - 2,
                    text_w + 12,
                    text_h + 4
                )
                painter.save()
                
                # Dynamic contrast-aware coloring for background and border
                bg_color = style.base_color
                if _luminance(bg_color) > 0.5:
                    painter.setBrush(QBrush(QColor("#f0f7ff")))
                    painter.setPen(QPen(QColor("#3b82f6"), 1.0))
                    text_color = QColor("#1d4ed8")
                else:
                    painter.setBrush(QBrush(QColor("#1e293b")))
                    painter.setPen(QPen(QColor("#60a5fa"), 1.0))
                    text_color = QColor("#eff6ff")
                
                painter.drawRoundedRect(badge_rect, 4, 4)
                
                # Extra-bold text inside badge
                font_locked = QFont(font)
                font_locked.setWeight(QFont.Weight.ExtraBold)
                painter.setFont(font_locked)
                
                painter.setPen(QPen(text_color, 0))
                painter.drawText(QPointF(screen.x() - text_w / 2,
                                         screen.y() + metrics.ascent() / 2 - 1),
                                 display_text)
                painter.restore()
            else:
                color = contrast_color(style.base_color)
                painter.setPen(QPen(color, 0))
                painter.drawText(QPointF(screen.x() - text_w / 2,
                                         screen.y() + metrics.ascent() / 2),
                                 display_text)
        self.visible_labels = visible_labels


