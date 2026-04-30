from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from src.data.models import IntervalItem
from src.renderers.well_log.config import TextTrackConfig
from src.renderers.well_log.tracks.base import DepthMappedContent, TrackWidget


class _TextContent(DepthMappedContent):
    def __init__(self, config: TextTrackConfig,
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
        font = QFont("Noto Sans CJK SC", 8)
        font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        painter.setFont(font)

        span = self._visible_bottom - self._visible_top
        if span <= 0:
            painter.end()
            return

        for iv in self._visible_intervals():
            top_y = (iv.top - self._visible_top) / span * actual_h
            bot_y = (iv.bottom - self._visible_top) / span * actual_h
            h = bot_y - top_y
            rect = QRectF(0, top_y, w, h)

            # Subtle border
            painter.setPen(QColor("#a0aec030"))
            painter.setBrush(QColor("transparent"))
            painter.drawRect(rect)

            # Word-wrapped text
            if iv.name and h > 8:
                painter.setPen(QColor("#2d3748"))
                painter.setClipRect(rect)
                painter.drawText(
                    QRectF(5, top_y + 2, w - 10, h - 4),
                    Qt.TextFlag.TextWordWrap,
                    iv.name,
                )

        painter.end()


class TextTrack(TrackWidget):
    def __init__(self, config: TextTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._intervals = intervals
        self._visible_top = top_depth
        self._visible_bottom = bottom_depth
        self._content: _TextContent | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._content = _TextContent(
            self._config, self._intervals,
            self._visible_top, self._visible_bottom, self,
        )
        return self._content

    def sync_depth(self, top_m: float, bottom_m: float):
        self._visible_top = top_m
        self._visible_bottom = bottom_m
        if self._content:
            self._content.set_depth_range(top_m, bottom_m)

    def preferred_width(self) -> int:
        return self._config.width

    def set_pixel_density(self, px_per_m: float):
        if self._content:
            self._content.set_pixel_density(px_per_m)

    def set_depth_range(self, top: float, bottom: float):
        self.sync_depth(top, bottom)