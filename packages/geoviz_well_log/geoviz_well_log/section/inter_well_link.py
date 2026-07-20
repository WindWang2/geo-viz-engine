"""Inter-well horizon polylines and facies quad polygon rendering."""
from __future__ import annotations

from dataclasses import dataclass, field
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen


@dataclass
class HorizonLink:
    """Stratigraphic horizon top boundary link across adjacent wells."""

    name: str
    x_left: float
    y_left: float
    x_right: float
    y_right: float
    color: QColor = field(default_factory=lambda: QColor(31, 111, 224))


@dataclass
class FaciesQuad:
    """Facies polygon fill across adjacent wells."""

    facies_name: str
    x_left: float
    y1_left: float  # Top left Y
    y2_left: float  # Bottom left Y
    x_right: float
    y1_right: float  # Top right Y
    y2_right: float  # Bottom right Y
    color: QColor = field(default_factory=lambda: QColor(240, 180, 100, 130))


def paint_horizon_link(painter: QPainter, link: HorizonLink) -> None:
    """Draw smooth control polyline for horizon link with label."""
    painter.save()
    pen = QPen(link.color, 2, Qt.DashLine)
    painter.setPen(pen)

    # Bezier curve across inter-well spacing
    dx = (link.x_right - link.x_left) / 3.0
    c1 = QPointF(link.x_left + dx, link.y_left)
    c2 = QPointF(link.x_right - dx, link.y_right)

    path = QPainterPath()
    path.moveTo(link.x_left, link.y_left)
    path.cubicTo(c1, c2, QPointF(link.x_right, link.y_right))
    painter.drawPath(path)

    # Label text in middle
    mid_x = (link.x_left + link.x_right) / 2.0
    mid_y = (link.y_left + link.y_right) / 2.0 - 4.0
    painter.setPen(QPen(QColor(40, 50, 65)))
    painter.setFont(QFont("SansSerif", 8, QFont.Weight.Bold))
    painter.drawText(
        QRectF(mid_x - 60, mid_y - 12, 120, 20),
        Qt.AlignmentFlag.AlignCenter,
        link.name,
    )
    painter.restore()


def paint_facies_quad(painter: QPainter, quad: FaciesQuad) -> None:
    """Draw semi-transparent quad polygon fill for facies continuity."""
    painter.save()
    path = QPainterPath()
    path.moveTo(quad.x_left, quad.y1_left)

    # Smooth top edge
    dx = (quad.x_right - quad.x_left) / 3.0
    c1_top = QPointF(quad.x_left + dx, quad.y1_left)
    c2_top = QPointF(quad.x_right - dx, quad.y1_right)
    path.cubicTo(c1_top, c2_top, QPointF(quad.x_right, quad.y1_right))

    # Right edge
    path.lineTo(quad.x_right, quad.y2_right)

    # Smooth bottom edge back
    c1_bot = QPointF(quad.x_right - dx, quad.y2_right)
    c2_bot = QPointF(quad.x_left + dx, quad.y2_left)
    path.cubicTo(c1_bot, c2_bot, QPointF(quad.x_left, quad.y2_left))
    path.closeSubpath()

    painter.setPen(QPen(quad.color.lighter(120), 1, Qt.PenStyle.SolidLine))
    painter.setBrush(QBrush(quad.color))
    painter.drawPath(path)
    painter.restore()
