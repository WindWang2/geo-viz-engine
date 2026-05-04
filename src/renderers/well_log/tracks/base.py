from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from src.data.models import IntervalItem
from src.renderers.well_log.config import TrackConfig


class TrackWidget(QWidget):
    depth_range_changed = Signal(float, float)

    def __init__(self, config: TrackConfig, header_height: int = 40, parent=None):
        super().__init__(parent)
        self._config = config
        self._header_height = header_height
        self._header_widget: QLabel | None = None
        self._content_widget: QWidget | None = None
        self.setMinimumWidth(config.width)
        self._build_layout()

    def _build_layout(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header_widget = QLabel(self._header_text())
        self._header_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._header_widget.setFixedHeight(self._header_height)
        self._header_widget.setStyleSheet(
            "background: #edf2f7; color: #2d3748; "
            "font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(self._header_widget)

        self._content_widget = self._create_content()
        layout.addWidget(self._content_widget, 1)  # stretch=1: expand to fill track height

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

    @property
    def header_widget(self) -> QLabel:
        return self._header_widget

    @property
    def content_widget(self) -> QWidget:
        return self._content_widget

    def preferred_width(self) -> int:
        return self._config.width

    def set_pixel_density(self, px_per_m: float):
        pass

    def sync_depth(self, top_m: float, bottom_m: float):
        pass

    def export_vector(self, painter, width: int, height: int):
        """Render track content as vector graphics for export."""
        # Default: grab as pixmap
        pix = self._content_widget.grab()
        painter.drawPixmap(0, 0, pix.scaled(
            width, height,
            Qt.AspectRatioMode.IgnoreAspectRatio,
        ))


class DepthMappedContent(QWidget):
    """Base for content widgets that paint intervals based on a visible depth range."""

    def __init__(self, intervals: list[IntervalItem],
                 top_depth: float, bottom_depth: float,
                 parent=None):
        super().__init__(parent)
        self._intervals = intervals
        self._visible_top = top_depth
        self._visible_bottom = bottom_depth
        self._px_per_m: float = 0.0

    def set_depth_range(self, top: float, bottom: float):
        self._visible_top = top
        self._visible_bottom = bottom
        self.update()

    def _visible_intervals(self) -> list[IntervalItem]:
        return [
            iv for iv in self._intervals
            if iv.bottom > self._visible_top and iv.top < self._visible_bottom
        ]
