from pathlib import Path

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
    QWidget,
)

from src.data.models import IntervalItem
from src.renderers.well_log.config import IntervalTrackConfig, PatternMapping
from src.renderers.well_log.tracks.base import TrackWidget


class IntervalTrack(TrackWidget):
    def __init__(self, config: IntervalTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._intervals = intervals
        self._top_depth = top_depth
        self._bottom_depth = bottom_depth
        self._scene: QGraphicsScene | None = None
        self._view: QGraphicsView | None = None
        self._pattern_cache: dict[str, QPixmap] = {}
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        cfg: IntervalTrackConfig = self._config
        self._scene = QGraphicsScene()
        width = cfg.width

        self._load_patterns(cfg.pattern_dir)

        for iv in self._intervals:
            top_y = iv.top - self._top_depth
            height = iv.bottom - iv.top
            rect = QRectF(0, top_y, width, height)

            fill_color = self._lookup_color(iv.name, cfg.color_mapping)
            pattern_key = self._lookup_pattern(iv.name, cfg.color_mapping)

            if pattern_key and pattern_key in self._pattern_cache:
                brush = QBrush()
                brush.setTexture(self._pattern_cache[pattern_key])
            else:
                brush = QBrush(QColor(fill_color))

            item = QGraphicsRectItem(rect)
            item.setBrush(brush)
            item.setPen(QColor("#4a5568"))
            self._scene.addItem(item)

            if height > 10 and iv.name:
                text = QGraphicsSimpleTextItem(iv.name)
                text.setPos(2, top_y + 2)
                if cfg.rotate_text:
                    text.setRotation(-90)
                    text.setPos(width / 2, top_y + height / 2)
                self._scene.addItem(text)

        total_depth = self._bottom_depth - self._top_depth
        self._view = QGraphicsView(self._scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setSceneRect(0, 0, width, total_depth)
        return self._view

    def _load_patterns(self, pattern_dir: str | None):
        if not pattern_dir:
            return
        pdir = Path(pattern_dir)
        if not pdir.exists():
            return
        for svg_file in pdir.glob("*.svg"):
            renderer = QSvgRenderer(str(svg_file))
            if not renderer.isValid():
                continue
            size = renderer.defaultSize()
            pm = QPixmap(size)
            pm.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pm)
            renderer.render(painter)
            painter.end()
            self._pattern_cache[svg_file.stem] = pm

    @staticmethod
    def _lookup_color(name: str, mapping: PatternMapping) -> str:
        for key, color in mapping.colors.items():
            if key in name:
                return color
        return "#e5e7eb"

    @staticmethod
    def _lookup_pattern(name: str, mapping: PatternMapping) -> str | None:
        for key, pattern_name in mapping.patterns.items():
            if key in name:
                return pattern_name
        return None

    def set_depth_range(self, top: float, bottom: float):
        if not self._view:
            return
        height = bottom - top
        view_height = self._view.viewport().height()
        if height > 0 and view_height > 0:
            self._view.resetTransform()
            self._view.scale(1, view_height / height)
            self._view.centerOn(
                self._config.width / 2,
                (top + bottom) / 2 - self._top_depth,
            )
