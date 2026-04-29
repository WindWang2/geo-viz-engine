from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QWidget,
)

from src.data.models import IntervalItem
from src.renderers.well_log.config import TextTrackConfig
from src.renderers.well_log.tracks.base import TrackWidget


class TextTrack(TrackWidget):
    def __init__(self, config: TextTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._intervals = intervals
        self._top_depth = top_depth
        self._bottom_depth = bottom_depth
        self._view: QGraphicsView | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        scene = QGraphicsScene()
        width = self._config.width

        for iv in self._intervals:
            top_y = iv.top - self._top_depth
            height = iv.bottom - iv.top

            rect_item = QGraphicsRectItem(QRectF(0, top_y, width, height))
            rect_item.setPen(QColor("#4a556830"))
            rect_item.setBrush(QColor("transparent"))
            scene.addItem(rect_item)

            if iv.name and height > 8:
                text = QGraphicsTextItem(iv.name)
                text.setPos(5, top_y + 2)
                text.setTextWidth(width - 10)
                scene.addItem(text)

        total_depth = self._bottom_depth - self._top_depth
        self._view = QGraphicsView(scene)
        self._view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._view.setSceneRect(0, 0, width, total_depth)
        return self._view

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
