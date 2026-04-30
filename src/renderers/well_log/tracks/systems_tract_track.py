from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPolygonF
from PySide6.QtWidgets import QWidget

from src.data.models import IntervalItem
from src.renderers.well_log.config import SystemsTractTrackConfig
from src.renderers.well_log.tracks.base import DepthMappedContent, TrackWidget


class _SystemsTractContent(DepthMappedContent):
    def __init__(self, config: SystemsTractTrackConfig,
                 intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 parent=None):
        super().__init__(intervals, top_depth, bottom_depth, parent)
        self._config = config
        self._px_per_m: float = 0.0

    def set_pixel_density(self, px_per_m: float):
        self._px_per_m = px_per_m
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        actual_h = self.height()
        span = self._visible_bottom - self._visible_top
        if span <= 0:
            painter.end()
            return

        for iv in self._visible_intervals():
            top_y = (iv.top - self._visible_top) / span * actual_h
            bot_y = (iv.bottom - self._visible_top) / span * actual_h
            rect = QRectF(0, top_y, w, bot_y - top_y)

            name_lower = iv.name.lower() if iv.name else ""
            if "tst" in name_lower:
                color = "#93c5fd"
                poly = QPolygonF([
                    rect.bottomLeft(), rect.bottomRight(),
                    QPointF(rect.center().x(), rect.top()),
                ])
            elif "hst" in name_lower:
                color = "#fde047"
                poly = QPolygonF([
                    rect.topLeft(), rect.topRight(),
                    QPointF(rect.center().x(), rect.bottom()),
                ])
            else:
                color = "#e5e7eb"
                painter.setBrush(QColor(color))
                painter.setPen(QColor("#a0aec0"))
                painter.drawRect(rect)
                continue

            painter.setBrush(QColor(color))
            painter.setPen(QColor("#a0aec0"))
            painter.drawPolygon(poly)

        painter.end()


class SystemsTractTrack(TrackWidget):
    def __init__(self, config: SystemsTractTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._intervals = intervals
        self._visible_top = top_depth
        self._visible_bottom = bottom_depth
        self._px_per_m: float = 0.0
        self._content: _SystemsTractContent | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._content = _SystemsTractContent(
            self._config, self._intervals,
            self._visible_top, self._visible_bottom, self,
        )
        return self._content

    def set_pixel_density(self, px_per_m: float):
        self._px_per_m = px_per_m
        if self._content:
            self._content.set_pixel_density(px_per_m)

    def sync_depth(self, top_m: float, bottom_m: float):
        self._visible_top = top_m
        self._visible_bottom = bottom_m
        if self._content:
            self._content.set_depth_range(top_m, bottom_m)

    def preferred_width(self) -> int:
        return self._config.width

    def set_depth_range(self, top: float, bottom: float):
        self.sync_depth(top, bottom)
