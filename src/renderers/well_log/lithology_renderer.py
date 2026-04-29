from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import QGraphicsScene, QGraphicsView, QGraphicsRectItem, QLabel, QWidget, QVBoxLayout


LITHOLOGY_COLORS = {
    "sandstone": "#fef9c3",
    "siltstone": "#e5e7eb",
    "mudstone": "#9ca3af",
    "shale": "#6b7280",
    "limestone": "#bfdbfe",
    "dolomite": "#bfdbfe",
}

PATTERNS_DIR = Path(__file__).parent.parent.parent / "patterns"


class LithologyRenderer(QWidget):
    def __init__(self, intervals: list, width: int = 80, height: int = 600):
        super().__init__()
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        self._build(intervals, width, height)

    def _build(self, intervals: list, width: int, height: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("岩性")
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
            color = LITHOLOGY_COLORS.get(iv.lithology, "#e5e7eb")
            rect = QGraphicsRectItem(0, top_y, width, rect_h)
            rect.setBrush(QBrush(QColor(color)))
            rect.setPen(QColor("#4a5568"))
            scene.addItem(rect)

            svg_path = PATTERNS_DIR / f"{iv.lithology}.svg"
            if svg_path.exists():
                svg_item = scene.addSvg(str(svg_path))
                if svg_item:
                    svg_item.setPos(0, top_y)
                    svg_renderer = QSvgRenderer(str(svg_path))
                    svg_item.setScale(min(width / svg_renderer.defaultSize().width(), rect_h / svg_renderer.defaultSize().height()))

        view = QGraphicsView(scene)
        view.setRenderHint(QPainter.RenderHint.Antialiasing)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(view)
