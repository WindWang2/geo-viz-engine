from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

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
            "background: #2d3748; color: #e2e8f0; "
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
