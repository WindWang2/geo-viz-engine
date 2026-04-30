from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPolygonF
from PySide6.QtWidgets import QWidget

from src.data.models import IntervalItem
from src.renderers.well_log.config import SystemsTractTrackConfig
from src.renderers.well_log.tracks.base import DepthMappedContent, TrackWidget


class _SystemsTractContent(DepthMappedContent):
    def __init__(self, config: SystemsTractTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float, parent=None):
        super().__init__(intervals, top_depth, bottom_depth, parent)
        self._config = config

    def set_pixel_density(self, px_per_m: float):
        self._px_per_m = px_per_m
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w = self.width()

        span = self._visible_bottom - self._visible_top
        if span <= 0:
            painter.end()
            return

        for iv in self._visible_intervals():
            top_y = (iv.top - self._visible_top) / span * self.height()
            bot_y = (iv.bottom - self._visible_top) / span * self.height()
            h = bot_y - top_y

            name_lower = iv.name.lower() if iv.name else ""

            if "tst" in name_lower:
                color = "#93c5fd"
                poly = QPolygonF([
                    QPointF(0, bot_y),
                    QPointF(w, bot_y),
                    QPointF(w / 2, top_y),
                ])
            elif "hst" in name_lower:
                color = "#fde047"
                poly = QPolygonF([
                    QPointF(0, top_y),
                    QPointF(w, top_y),
                    QPointF(w / 2, bot_y),
                ])
            else:
                painter.setPen(QColor("#4a5568"))
                painter.setBrush(QBrush(QColor("#e5e7eb")))
                painter.drawRect(0, top_y, w, h)
                continue

            pp = QPainterPath()
            pp.addPolygon(poly)
            pp.closeSubpath()
            painter.setPen(QColor("#4a5568"))
            painter.setBrush(QBrush(QColor(color)))
            painter.drawPath(pp)
        painter.end()


class SystemsTractTrack(TrackWidget):
    def __init__(self, config: SystemsTractTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._intervals = intervals
        self._content: _SystemsTractContent | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._content = _SystemsTractContent(
            self._config, self._intervals,
            self._config.header_height, 0, self,
        )
        return self._content

    def set_pixel_density(self, px_per_m: float):
        if self._content:
            self._content.set_pixel_density(px_per_m)

    def sync_depth(self, top_m: float, bottom_m: float):
        if self._content:
            self._content.set_depth_range(top_m, bottom_m)

    def preferred_width(self) -> int:
        return self._config.width

    def set_depth_range(self, top: float, bottom: float):
        self.sync_depth(top, bottom)