from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal, QObject, QEvent, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent, QPixmap
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QWidget

from .track_base import BaseTrack, ECHARTS_HEADER_BG, ECHARTS_BORDER, ECHARTS_TEXT, ECHARTS_GROUP_HEADER_HEIGHT
from .coordinator import LayoutCoordinator
from .overlay import CrosshairOverlay


class _TrackMouseFilter(QObject):
    """Event filter installed on each track widget to capture mouse events."""

    def __init__(self, canvas: "WellLogCanvas"):
        super().__init__(canvas)
        self._canvas = canvas

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if isinstance(event, QMouseEvent):
            if event.type() == QEvent.Type.MouseMove:
                canvas_pos = obj.mapTo(self._canvas, event.position().toPoint())
                self._canvas.mouse_moved.emit(float(canvas_pos.y()))
            elif event.type() == QEvent.Type.Leave:
                self._canvas.mouse_moved.emit(-1.0)
            # Forward mouse press/release/move to canvas for ZoomPanHandler
            if event.type() in (QEvent.Type.MouseButtonPress,
                                QEvent.Type.MouseButtonRelease,
                                QEvent.Type.MouseMove):
                canvas_pos = obj.mapTo(self._canvas, event.position().toPoint())
                new_event = QMouseEvent(
                    event.type(),
                    canvas_pos,
                    event.globalPosition(),
                    event.button(),
                    event.buttons(),
                    event.modifiers(),
                )
                QApplication.sendEvent(self._canvas, new_event)
        return False  # don't consume — let tracks still receive events


class WellLogCanvas(QOpenGLWidget):
    """Main canvas widget for well log visualization.

    Manages track layout, depth range, and provides unified paint_all()
    for both display and vector export.
    """

    depth_range_changed = Signal(float, float)
    interval_clicked = Signal(str, float, float)
    cursor_moved = Signal(float)
    mouse_moved = Signal(float)  # y position in canvas coordinates, -1 = left

    def __init__(self, parent=None):
        super().__init__(parent)
        self._coordinator = LayoutCoordinator()
        self._track_filter = _TrackMouseFilter(self)
        self._crosshair: CrosshairOverlay | None = None
        self._depth_span: float = 100.0
        self._static_cache: QPixmap | None = None
        self._cache_dirty: bool = True
        self.setMinimumSize(200, 400)

    @property
    def crosshair(self) -> CrosshairOverlay | None:
        return self._crosshair

    @crosshair.setter
    def crosshair(self, overlay: CrosshairOverlay):
        self._crosshair = overlay

    @property
    def tracks(self) -> list[BaseTrack]:
        return self._coordinator.tracks

    @property
    def total_width(self) -> int:
        return self._coordinator.total_width

    @property
    def depth_span(self) -> float:
        if not self.tracks:
            return self._depth_span
        return self.tracks[0].depth_span

    def add_track(self, track: BaseTrack):
        self._coordinator.add_track(track)
        track.setParent(self)
        track.setMouseTracking(True)
        track.installEventFilter(self._track_filter)
        self._cache_dirty = True
        self.setMinimumWidth(self.total_width)

    def remove_track(self, track: BaseTrack):
        track.removeEventFilter(self._track_filter)
        self._coordinator.remove_track(track)
        self._cache_dirty = True
        self.setMinimumWidth(self.total_width)

    def set_depth_range(self, top: float, bottom: float):
        self._depth_span = bottom - top
        self._coordinator.set_depth_range(top, bottom)
        self._cache_dirty = True
        self.depth_range_changed.emit(top, bottom)
        self.update()

    def set_tracks(self, tracks: list[BaseTrack]):
        for t in self._coordinator.tracks[:]:
            self.remove_track(t)
        for t in tracks:
            self.add_track(t)
        self._cache_dirty = True
        self.setMinimumWidth(self.total_width)

    def paint_all(self, painter: QPainter):
        """Unified render entry: group headers + individual tracks."""
        if not self.tracks:
            return

        # Filter to visible tracks only
        visible_tracks = [(i, t) for i, t in enumerate(self.tracks)
                          if getattr(t, '_visible', True)]
        if not visible_tracks:
            return

        w = self.width()
        h = self.height()
        natural_width = self.total_width
        scale = w / natural_width if natural_width > 0 else 1.0

        # Compute scaled x offsets and widths for visible tracks
        scaled: list[tuple[float, float]] = []
        x_off = 0.0
        for _, track in visible_tracks:
            sw = track.width * scale
            scaled.append((x_off, sw))
            x_off += sw

        # Collect groups: group_name -> [(x_offset, width), ...]
        groups: dict[str, list[tuple[float, float]]] = {}
        for (_, track), s in zip(visible_tracks, scaled):
            gn = track.group_name
            if gn:
                groups.setdefault(gn, []).append(s)

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
            group_rect = QRectF(x_start, 0, gw, ECHARTS_GROUP_HEADER_HEIGHT)
            painter.fillRect(group_rect, QColor(ECHARTS_HEADER_BG))
            painter.setPen(QPen(QColor(ECHARTS_BORDER), 1))
            painter.drawRect(group_rect)
            painter.setPen(QPen(QColor(ECHARTS_TEXT)))
            painter.setFont(group_font)
            painter.drawText(group_rect, Qt.AlignmentFlag.AlignCenter, group_name)

        # Render individual tracks with uniform header height
        max_header = max((t.header_height for _, t in visible_tracks), default=0)
        for (_, track), (x_off, sw) in zip(visible_tracks, scaled):
            full_rect = QRectF(x_off, 0, sw, h)
            track.export_render(painter, full_rect, canvas_header_height=max_header)

    def resizeEvent(self, event):
        self._cache_dirty = True
        super().resizeEvent(event)

    def paintEvent(self, event):
        dpr = self.devicePixelRatioF()
        w = int(self.width() * dpr)
        h = int(self.height() * dpr)

        if self._cache_dirty or self._static_cache is None or self._static_cache.size() != QSize(w, h):
            self._static_cache = QPixmap(w, h)
            self._static_cache.setDevicePixelRatio(dpr)
            self._static_cache.fill(QColor("#ffffff"))
            cache_painter = QPainter(self._static_cache)
            self.paint_all(cache_painter)
            cache_painter.end()
            self._cache_dirty = False

        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._static_cache)
        if self._crosshair and self._crosshair.visible and self.tracks:
            self._crosshair.paint_overlay(painter, QRectF(self.rect()))
        painter.end()

    def mouseMoveEvent(self, event: QMouseEvent):
        self.mouse_moved.emit(event.position().y())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.mouse_moved.emit(-1.0)
        super().leaveEvent(event)
