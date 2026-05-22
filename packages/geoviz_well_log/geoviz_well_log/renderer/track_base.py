from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QSizeF, Signal
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtWidgets import QWidget


class BaseTrack(QWidget):
    """Abstract base for all well log tracks.

    Every track implements paint_content(painter, rect) which is called
    with the same QPainter for both display and vector export.

    Subclasses **must** override ``paint_content``; instantiating
    ``BaseTrack`` directly raises ``TypeError``.
    """

    depth_range_changed = Signal(float, float)

    def __init__(self, label: str = "", width: int = 100, header_height: int = 32, parent=None):
        if type(self) is BaseTrack:
            raise TypeError("BaseTrack is abstract and cannot be instantiated directly")
        super().__init__(parent)
        self._label = label
        self._width = width
        self._header_height = header_height
        self._depth_top = 0.0
        self._depth_bottom = 100.0
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)

    @property
    def label(self) -> str:
        return self._label

    @property
    def width(self) -> int:
        return self._width

    @property
    def header_height(self) -> int:
        return self._header_height

    @property
    def depth_top(self) -> float:
        return self._depth_top

    @property
    def depth_bottom(self) -> float:
        return self._depth_bottom

    @property
    def depth_span(self) -> float:
        return self._depth_bottom - self._depth_top

    def set_depth_range(self, top: float, bottom: float):
        self._depth_top = top
        self._depth_bottom = bottom
        self.update()

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def paint_content(self, painter: QPainter, rect: QRectF):
        """Render track content. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement paint_content")

    def paint_header(self, painter: QPainter, rect: QRectF):
        """Render track header (label)."""
        painter.save()
        painter.setPen(Qt.GlobalColor.black)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._label)
        painter.restore()

    def export_render(self, painter: QPainter, full_rect: QRectF):
        """Export: header + content together."""
        header_rect = QRectF(full_rect.topLeft(), QSizeF(full_rect.width(), self._header_height))
        content_rect = QRectF(
            full_rect.left(), full_rect.top() + self._header_height,
            full_rect.width(), full_rect.height() - self._header_height,
        )
        painter.save()
        # Header background
        painter.fillRect(header_rect, QColor("#f0f0f0"))
        painter.drawRect(header_rect)
        self.paint_header(painter, header_rect)
        # Content
        self.paint_content(painter, content_rect)
        painter.drawRect(content_rect)
        painter.restore()
