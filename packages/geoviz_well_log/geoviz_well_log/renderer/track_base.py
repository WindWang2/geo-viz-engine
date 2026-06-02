from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QSizeF, Signal, QPointF
from PySide6.QtGui import QPainter, QFont, QColor, QPen
from PySide6.QtWidgets import QWidget

# Azurite Design System constants
ECHARTS_BORDER = "#94a3b8"
ECHARTS_GRID = "#cbd5e1"
ECHARTS_HEADER_BG = "#e2e8f0"
ECHARTS_SUB_HEADER_BG = "#f8fafc"
ECHARTS_TEXT = "#0f172a"
ECHARTS_HEADER_TOP = 10
ECHARTS_GROUP_HEADER_HEIGHT = 32
ECHARTS_TRACK_HEADER_HEIGHT = 56
ECHARTS_BODY_TOP_GAP = 8
ECHARTS_FONT_FAMILY = "'Microsoft YaHei', 'Segoe UI', sans-serif"


class BaseTrack(QWidget):
    """Abstract base for all well log tracks.

    Every track implements paint_content(painter, rect) which is called
    with the same QPainter for both display and vector export.

    Subclasses **must** override ``paint_content``; instantiating
    ``BaseTrack`` directly raises ``TypeError``.
    """

    depth_range_changed = Signal(float, float)

    def __init__(self, label: str = "", width: int = 100, header_height: int = 56,
                 group_name: str = "", parent=None):
        if type(self) is BaseTrack:
            raise TypeError("BaseTrack is abstract and cannot be instantiated directly")
        super().__init__(parent)
        self._label = label
        self._width = width
        self._header_height = header_height
        self._group_name = group_name
        self._depth_top = 0.0
        self._depth_bottom = 100.0
        self._visible = True
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)

    @property
    def label(self) -> str:
        return self._label

    @property
    def width(self) -> int:
        return self._width

    def set_width(self, w: int):
        """Update track width (clamped to min/max)."""
        w = max(40, min(300, w))
        self._width = w
        self.setMinimumWidth(w)
        self.setMaximumWidth(w)

    @property
    def header_height(self) -> int:
        return self._header_height

    @property
    def group_name(self) -> str:
        return self._group_name

    @property
    def depth_top(self) -> float:
        return self._depth_top

    @property
    def depth_bottom(self) -> float:
        return self._depth_bottom

    @property
    def depth_span(self) -> float:
        return self._depth_bottom - self._depth_top

    @property
    def visible(self) -> bool:
        return self._visible

    @visible.setter
    def visible(self, value: bool):
        self._visible = value

    def set_depth_range(self, top: float, bottom: float):
        self._depth_top = top
        self._depth_bottom = bottom
        self.update()

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def paint_grid(self, painter: QPainter, rect: QRectF):
        """Draw horizontal grid lines matching ECharts yAxis splitLine."""
        pen = QPen(QColor(ECHARTS_GRID), 1, Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        span = self.depth_span
        if span <= 0:
            return
        interval = self._compute_grid_interval(rect.height(), span)
        start = (self.depth_top // interval) * interval
        if start < self.depth_top:
            start += interval
        depth = start
        while depth <= self.depth_bottom:
            y = self._depth_to_y(depth, rect)
            if rect.top() <= y <= rect.bottom():
                painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            depth += interval

    def _compute_grid_interval(self, rect_height: float, span: float) -> float:
        """Pick interval so that grid lines are >=20px apart."""
        candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
        for c in candidates:
            px_per_tick = rect_height / (span / c)
            if px_per_tick >= 20:
                return c
        return candidates[-1]

    def paint_content(self, painter: QPainter, rect: QRectF):
        """Render track content. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement paint_content")

    def paint_header(self, painter: QPainter, rect: QRectF):
        """Render track header (label)."""
        painter.save()
        painter.setPen(QColor(ECHARTS_TEXT))
        font = QFont()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._label)
        painter.restore()

    def export_render(self, painter: QPainter, full_rect: QRectF,
                      canvas_header_height: int | None = None):
        """Export: header + content together.

        canvas_header_height overrides per-track header height so all tracks
        share the same header band height on the canvas.
        """
        hh = canvas_header_height if canvas_header_height is not None else self._header_height
        header_rect = QRectF(full_rect.topLeft(), QSizeF(full_rect.width(), hh))
        content_rect = QRectF(
            full_rect.left(), full_rect.top() + hh,
            full_rect.width(), full_rect.height() - hh,
        )
        painter.save()
        # Header background
        painter.fillRect(header_rect, QColor(ECHARTS_HEADER_BG))
        painter.setPen(QColor(ECHARTS_BORDER))
        painter.drawRect(header_rect)
        self.paint_header(painter, header_rect)
        # Content
        self.paint_content(painter, content_rect)
        painter.setPen(QColor(ECHARTS_BORDER))
        painter.drawRect(content_rect)
        painter.restore()
