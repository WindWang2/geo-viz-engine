from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QWidget

from .track_base import BaseTrack, ECHARTS_HEADER_BG, ECHARTS_BORDER, ECHARTS_TEXT, ECHARTS_GROUP_HEADER_HEIGHT
from .coordinator import LayoutCoordinator


class WellLogCanvas(QWidget):
    """Main canvas widget for well log visualization.

    Manages track layout, depth range, and provides unified paint_all()
    for both display and vector export.
    """

    depth_range_changed = Signal(float, float)
    interval_clicked = Signal(str, float, float)
    cursor_moved = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._coordinator = LayoutCoordinator()
        self.setMinimumSize(200, 400)

    @property
    def tracks(self) -> list[BaseTrack]:
        return self._coordinator.tracks

    @property
    def total_width(self) -> int:
        return self._coordinator.total_width

    def add_track(self, track: BaseTrack):
        self._coordinator.add_track(track)
        track.setParent(self)
        self.setMinimumWidth(self.total_width)

    def remove_track(self, track: BaseTrack):
        self._coordinator.remove_track(track)
        self.setMinimumWidth(self.total_width)

    def set_depth_range(self, top: float, bottom: float):
        self._coordinator.set_depth_range(top, bottom)
        self.depth_range_changed.emit(top, bottom)
        self.update()

    def set_tracks(self, tracks: list[BaseTrack]):
        for t in self._coordinator.tracks[:]:
            self._coordinator.remove_track(t)
        for t in tracks:
            self._coordinator.add_track(t)
        self.setMinimumWidth(self.total_width)

    def paint_all(self, painter: QPainter):
        """Unified render entry: group headers + individual tracks."""
        if not self.tracks:
            return

        w = self.width()
        h = self.height()

        # Collect groups: group_name -> [(x_offset, width), ...]
        groups: dict[str, list[tuple[float, float]]] = {}
        x_off = 0.0
        for track in self.tracks:
            gn = track.group_name
            if gn:
                groups.setdefault(gn, []).append((x_off, track.width))
            x_off += track.width

        # Draw group headers
        group_font = QFont()
        group_font.setPixelSize(15)
        group_font.setBold(True)
        painter.setFont(group_font)
        painter.setPen(QPen(QColor(ECHARTS_TEXT)))

        for group_name, spans in groups.items():
            if not spans:
                continue
            x_start = spans[0][0]
            x_end = spans[-1][0] + spans[-1][1]
            gw = x_end - x_start
            # Group header rect at the very top
            group_rect = QRectF(x_start, 0, gw, ECHARTS_GROUP_HEADER_HEIGHT)
            painter.fillRect(group_rect, QColor(ECHARTS_HEADER_BG))
            old_pen = painter.pen()
            painter.setPen(QPen(QColor(ECHARTS_BORDER), 1))
            painter.drawRect(group_rect)
            painter.setPen(QPen(QColor(ECHARTS_TEXT)))
            painter.setFont(group_font)
            painter.drawText(group_rect, Qt.AlignmentFlag.AlignCenter, group_name)

        # Render individual tracks with uniform header height
        max_header = max((t.header_height for t in self.tracks), default=0)
        x_offset = 0.0
        for track in self.tracks:
            full_rect = QRectF(x_offset, 0, track.width, h)
            track.export_render(painter, full_rect, canvas_header_height=max_header)
            x_offset += track.width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        self.paint_all(painter)
        painter.end()
