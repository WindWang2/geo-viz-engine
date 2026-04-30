from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from src.data.models import IntervalItem
from src.renderers.well_log.config import IntervalTrackConfig, PatternMapping
from src.renderers.well_log.tracks.base import DepthMappedContent, TrackWidget


def _lookup_color(name: str, mapping: PatternMapping) -> str:
    for key, color in mapping.colors.items():
        if key in name:
            return color
    return "#e5e7eb"


def _lookup_pattern(name: str, mapping: PatternMapping) -> str | None:
    for key, pattern_name in mapping.patterns.items():
        if key in name:
            return pattern_name
    return None


class _IntervalContent(DepthMappedContent):
    def __init__(self, config: IntervalTrackConfig,
                 intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 parent=None):
        super().__init__(intervals, top_depth, bottom_depth, parent)
        self._config = config
        self._pattern_brushes: dict[str, QBrush] = {}
        self._px_per_m: float = 0.0
        self._load_patterns(config.pattern_dir)

    def set_pixel_density(self, px_per_m: float):
        self._px_per_m = px_per_m
        self.update()

    @property
    def _current_top(self) -> float:
        return self._visible_top

    @property
    def _current_bottom(self) -> float:
        return self._visible_bottom

    @_current_top.setter
    def _current_top(self, value: float):
        self._visible_top = value

    @_current_bottom.setter
    def _current_bottom(self, value: float):
        self._visible_bottom = value

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
            brush = QBrush()
            brush.setTexture(pm)
            self._pattern_brushes[svg_file.stem] = brush

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        actual_h = self.height()
        span = self._visible_bottom - self._visible_top
        font = QFont("Noto Sans CJK SC", 8)
        font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        painter.setFont(font)

        for iv in self._visible_intervals():
            top_y = (iv.top - self._visible_top) / span * actual_h
            bot_y = (iv.bottom - self._visible_top) / span * actual_h
            h = bot_y - top_y
            rect = QRectF(0, top_y, w, h)

            # Fill
            pattern_key = _lookup_pattern(iv.name, self._config.color_mapping)
            if pattern_key and pattern_key in self._pattern_brushes:
                painter.setBrush(self._pattern_brushes[pattern_key])
            else:
                fill_color = _lookup_color(iv.name, self._config.color_mapping)
                painter.setBrush(QColor(fill_color))

            painter.setPen(QColor("#a0aec0"))
            painter.drawRect(rect)

            # Text
            if h > 10 and iv.name:
                painter.setPen(QColor("#2d3748"))
                if self._config.rotate_text:
                    painter.save()
                    painter.setClipRect(rect)
                    painter.translate(rect.center().x(), rect.center().y())
                    painter.rotate(-90)
                    painter.drawText(
                        QRectF(-h / 2, -6, h, 12),
                        Qt.AlignmentFlag.AlignCenter, iv.name,
                    )
                    painter.restore()
                else:
                    painter.setClipRect(rect)
                    painter.drawText(
                        QRectF(2, top_y + 2, w - 4, h - 4),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        iv.name,
                    )

        painter.end()


class IntervalTrack(TrackWidget):
    def __init__(self, config: IntervalTrackConfig, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._intervals = intervals
        self._visible_top = top_depth
        self._visible_bottom = bottom_depth
        self._px_per_m: float = 0.0
        self._content: _IntervalContent | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._content = _IntervalContent(
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
