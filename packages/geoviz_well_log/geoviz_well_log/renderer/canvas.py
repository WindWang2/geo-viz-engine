from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget

from .track_base import BaseTrack
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
        """Unified render entry: header + content for all tracks."""
        if not self.tracks:
            return

        w = self.width()
        h = self.height()
        x_offset = 0.0

        for track in self.tracks:
            full_rect = QRectF(x_offset, 0, track.width, h)
            track.export_render(painter, full_rect)
            x_offset += track.width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        self.paint_all(painter)
        painter.end()
