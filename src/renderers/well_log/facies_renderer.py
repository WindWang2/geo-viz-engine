from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QVBoxLayout,
    QWidget,
)

PATTERNS_DIR = Path(__file__).parent.parent.parent / "patterns"

FACIES_COLORS = {
    "tidal_flat": "#93c5fd",
    "shelf": "#86efac",
    "sand_flat": "#fde047",
    "mud_flat": "#9ca3af",
    "mixed": "#ca8a04",
    "clastic_shelf": "#eab308",
    "dolomitic_flat": "#93c5fd",
    "muddy_shelf": "#a5b4fc",
    "sandy_shelf": "#fef08a",
    "sand_mud_shelf": "#fef08a",
}


class FaciesRenderer(QWidget):
    def __init__(self, intervals: list, width: int = 80, height: int = 600):
        super().__init__()
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        self._build(intervals, width, height)

    def _build(self, intervals: list, width: int, height: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("沉积相")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(40)
        header.setStyleSheet("background: #2d3748; color: #e2e8f0; font-size: 10px; font-weight: bold;")
        layout.addWidget(header)

        scene = QGraphicsScene()
        total_depth = max(iv.bottom for iv in intervals) if intervals else 100
        scale = (height - 40) / total_depth

        for iv in intervals:
            top_y = 40 + iv.top * scale
            rect_h = (iv.bottom - iv.top) * scale
            color = FACIES_COLORS.get(iv.facies, "#e5e7eb")
            rect = QGraphicsRectItem(0, top_y, width, rect_h)
            rect.setBrush(QBrush(QColor(color)))
            rect.setPen(QColor("#4a5568"))
            scene.addItem(rect)

            svg_path = PATTERNS_DIR / f"{iv.facies}.svg"
            if svg_path.exists():
                svg_item = QGraphicsSvgItem(str(svg_path))
                svg_item.setPos(0, top_y)
                svg_renderer = QSvgRenderer(str(svg_path))
                default_size = svg_renderer.defaultSize()
                if default_size.width() > 0 and default_size.height() > 0:
                    svg_item.setScale(min(width / default_size.width(), rect_h / default_size.height()))
                scene.addItem(svg_item)

        view = QGraphicsView(scene)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(view)
