from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.data.models import IntervalItem
from src.renderers.well_log.config import TrackConfig


class TrackWidget(QWidget):
    depth_range_changed = Signal(float, float)

    def __init__(self, config: TrackConfig, header_height: int = 40, parent=None):
        super().__init__(parent)
        self._config = config
        self._header_height = header_height
        self.setFixedWidth(config.width)
        self._build_layout()

    def _build_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel(self._header_text())
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(self._header_height)
        header.setStyleSheet(
            "background: #edf2f7; color: #2d3748; "
            "font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(header)

        self._content_widget = self._create_content()
        layout.addWidget(self._content_widget)

    def _header_text(self) -> str:
        if self._config.label2:
            return f"{self._config.label}\n{self._config.label2}"
        return self._config.label

    def _create_content(self) -> QWidget:
        raise NotImplementedError

    def set_depth_range(self, top: float, bottom: float):
        raise NotImplementedError

    @property
    def config(self) -> TrackConfig:
        return self._config

    def preferred_width(self) -> int:
        return self._config.width

    def set_pixel_density(self, px_per_m: float):
        pass  # override in subclasses that use _depth_to_y

    def sync_depth(self, top_m: float, bottom_m: float):
        pass  # override in subclasses to update visible range


class DepthMappedContent(QWidget):
    """Base for content widgets that paint intervals based on a visible depth range."""

    def __init__(self, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 parent=None):
        super().__init__(parent)
        self._intervals = intervals
        self._visible_top = top_depth
        self._visible_bottom = bottom_depth

    def set_depth_range(self, top: float, bottom: float):
        self._visible_top = top
        self._visible_bottom = bottom
        self.update()

    def _depth_to_y(self, depth: float) -> float:
        span = self._visible_bottom - self._visible_top
        if span <= 0:
            return 0.0
        return (depth - self._visible_top) / span * self.height()

    def _depth_to_y_absolute(self, depth_m: float, canvas_h: float) -> float:
        span = self._visible_bottom - self._visible_top
        if span <= 0:
            return 0.0
        return (depth_m - self._visible_top) / span * canvas_h

    def _visible_intervals(self) -> list[IntervalItem]:
        return [
            iv for iv in self._intervals
            if iv.bottom > self._visible_top and iv.top < self._visible_bottom
        ]
