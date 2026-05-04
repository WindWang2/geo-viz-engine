from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
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
        self._pattern_pixmaps: dict[str, QPixmap] = {}
        self._load_patterns(config.pattern_dir)

    def set_pixel_density(self, px_per_m: float):
        self._px_per_m = px_per_m
        self.update()

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
            self._pattern_pixmaps[svg_file.stem] = pm

    def _adaptive_font_size(self, interval_height: float) -> int:
        """Calculate font size based on interval height, clamped to [7, 12]."""
        return max(7, min(12, int(interval_height * 0.25)))

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
            h = bot_y - top_y
            rect = QRectF(0, top_y, w, h)

            # Fill
            painter.save()
            pattern_key = _lookup_pattern(iv.name, self._config.color_mapping)
            if pattern_key and pattern_key in self._pattern_pixmaps:
                painter.setClipRect(rect)
                painter.drawTiledPixmap(rect.toRect(), self._pattern_pixmaps[pattern_key])
                painter.setPen(QColor('#a0aec0'))
                painter.drawRect(rect)
            else:
                fill_color = _lookup_color(iv.name, self._config.color_mapping)
                painter.setBrush(QColor(fill_color))
                painter.setPen(QColor('#a0aec0'))
                painter.drawRect(rect)
            painter.restore()

            # Text — skip if font would be too small
            font_size = self._adaptive_font_size(h)
            if h > 10 and iv.name and font_size >= 8:
                font = QFont("Noto Sans CJK SC", font_size)
                font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
                
                from PySide6.QtGui import QFontMetrics
                fm = QFontMetrics(font)
                if w < fm.height():
                    continue

                painter.setFont(font)
                painter.setPen(QColor('#2d3748'))
                if self._config.rotate_text:
                    painter.save()
                    painter.setClipRect(rect)
                    painter.translate(rect.center().x(), rect.center().y())
                    painter.rotate(-90)
                    painter.drawText(
                        QRectF(-h / 2, -12 / 2, h, 12),
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
        self._content: _IntervalContent | None = None
        self._init_top = top_depth
        self._init_bottom = bottom_depth
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._content = _IntervalContent(
            self._config, self._intervals,
            self._init_top, self._init_bottom, self,
        )
        return self._content

    def set_pixel_density(self, px_per_m: float):
        if self._content:
            self._content.set_pixel_density(px_per_m)

    def sync_depth(self, top_m: float, bottom_m: float):
        if self._content:
            self._content.set_depth_range(top_m, bottom_m)

    def set_depth_range(self, top: float, bottom: float):
        self.sync_depth(top, bottom)

    def export_vector(self, painter: QPainter, width: int, height: int):
        """Render intervals as vector graphics for SVG/PDF export."""
        from PySide6.QtCore import QRectF

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        top_depth = self._init_top
        bottom_depth = self._init_bottom
        span = bottom_depth - top_depth
        if span <= 0:
            return

        for iv in self._intervals:
            if iv.bottom < top_depth or iv.top > bottom_depth:
                continue

            top_y = (iv.top - top_depth) / span * height
            bot_y = (iv.bottom - top_depth) / span * height
            rect = QRectF(0, top_y, width, bot_y - top_y)

            # Fill - use solid color for vector export (patterns cause issues in SVG)
            painter.save()
            fill_color = _lookup_color(iv.name, self._config.color_mapping)
            painter.setBrush(QColor(fill_color))
            painter.setPen(QColor('#a0aec0'))
            painter.drawRect(rect)
            painter.restore()

            # Text
            h = rect.height()
            font_size = self._content._adaptive_font_size(h)
            if h > 10 and iv.name and font_size >= 8:
                font = QFont("Noto Sans CJK SC", font_size)
                font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
                
                from PySide6.QtGui import QFontMetrics
                fm = QFontMetrics(font)
                if width < fm.height():
                    continue

                painter.setFont(font)
                painter.setPen(QColor('#2d3748'))
                if self._config.rotate_text:
                    painter.save()
                    painter.setClipRect(rect)
                    painter.translate(rect.center().x(), rect.center().y())
                    painter.rotate(-90)
                    painter.drawText(
                        QRectF(-h / 2, -12 / 2, h, 12),
                        Qt.AlignmentFlag.AlignCenter, iv.name,
                    )
                    painter.restore()
                else:
                    painter.setClipRect(rect)
                    painter.drawText(
                        QRectF(2, top_y + 2, width - 4, h - 4),
                        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        iv.name,
                    )
