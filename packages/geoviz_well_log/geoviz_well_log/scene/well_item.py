from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QCursor
from PySide6.QtWidgets import QGraphicsObject, QStyleOptionGraphicsItem, QWidget

from ..renderer.track_base import (
    BaseTrack, ECHARTS_HEADER_BG, ECHARTS_BORDER, ECHARTS_TEXT,
    ECHARTS_GROUP_HEADER_HEIGHT,
)
from ..models import IntervalItem


class WellItem(QGraphicsObject):
    """A single well column rendered as a QGraphicsObject.

    Renders BaseTrack objects via QPainter in paint(), reusing
    the export_render() pipeline from WellLogCanvas.
    Horizontally draggable, with depth-to-Y coordinate mapping.

    Column height is derived from: (depth_bottom - depth_top) * depth_scale.
    """

    well_moved = Signal()
    interval_clicked = Signal(str, float, float)  # well_name, top, bottom

    def __init__(self, well_name: str, tracks: list[BaseTrack],
                 column_width: int = 300,
                 depth_scale: float = 0.8,
                 parent=None):
        super().__init__(parent)
        self._well_name = well_name
        self._tracks = list(tracks)
        self._column_width = column_width
        self._depth_top = 0.0
        self._depth_bottom = 100.0
        self._depth_scale = depth_scale  # pixels per depth unit

        # Natural (unscaled) width = sum of track widths
        self._natural_width = sum(t.width for t in self._tracks) if self._tracks else column_width

        # Drag state
        self._dragging = False
        self._drag_start_x = 0.0

        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.setFlag(QGraphicsObject.GraphicsItemFlag.ItemIsSelectable, True)
        self.setAcceptHoverEvents(True)

    # --- Geometry ---

    def boundingRect(self) -> QRectF:
        label_h = 28
        h = self.column_height
        return QRectF(-2, -label_h - 2, self._column_width + 4, h + label_h + 4)

    @property
    def well_name(self) -> str:
        return self._well_name

    @property
    def tracks(self) -> list[BaseTrack]:
        return list(self._tracks)

    @property
    def column_width(self) -> float:
        return self._column_width

    @property
    def column_height(self) -> float:
        """Content height derived from depth span * scale, plus header."""
        span = self._depth_bottom - self._depth_top
        return self.header_height + span * self._depth_scale

    @property
    def header_height(self) -> float:
        if not self._tracks:
            return 56
        return max(t.header_height for t in self._tracks)

    @property
    def content_top(self) -> float:
        return self.header_height

    @property
    def content_height(self) -> float:
        span = self._depth_bottom - self._depth_top
        return span * self._depth_scale

    @property
    def depth_top(self) -> float:
        return self._depth_top

    @property
    def depth_bottom(self) -> float:
        return self._depth_bottom

    @property
    def depth_scale(self) -> float:
        return self._depth_scale

    # --- Setters ---

    def set_depth_range(self, top: float, bottom: float):
        self.prepareGeometryChange()
        self._depth_top = top
        self._depth_bottom = bottom
        for track in self._tracks:
            track.set_depth_range(top, bottom)
        self.update()

    def set_depth_scale(self, scale: float):
        self.prepareGeometryChange()
        self._depth_scale = scale
        self.update()

    def set_column_width(self, width: float):
        self._column_width = width
        self.update()

    def set_tracks(self, tracks: list[BaseTrack]):
        self._tracks = list(tracks)
        self._natural_width = sum(t.width for t in self._tracks) if self._tracks else self._column_width
        for track in self._tracks:
            track.set_depth_range(self._depth_top, self._depth_bottom)
        self.update()

    # --- Depth <-> Y mapping ---

    def depth_to_y(self, depth: float) -> float:
        """Convert depth to local Y coordinate (within content area)."""
        span = self._depth_bottom - self._depth_top
        if span <= 0:
            return self.content_top
        ratio = (depth - self._depth_top) / span
        return self.content_top + ratio * self.content_height

    def y_to_depth(self, y: float) -> float | None:
        """Convert local Y coordinate to depth."""
        content_h = self.content_height
        if content_h <= 0:
            return None
        ratio = (y - self.content_top) / content_h
        span = self._depth_bottom - self._depth_top
        return self._depth_top + ratio * span

    # --- Hit testing ---

    def interval_at(self, local_pos: QPointF) -> IntervalItem | None:
        """Find the narrowest interval containing the depth at local_pos."""
        from ..renderer.interval_track import IntervalTrack
        from ..renderer.lithology_track import LithologyTrack

        depth = self.y_to_depth(local_pos.y())
        if depth is None:
            return None

        best = None
        for track in self._tracks:
            if not getattr(track, '_visible', True):
                continue
            if isinstance(track, IntervalTrack):
                for iv in track._intervals:
                    if iv.top <= depth <= iv.bottom:
                        if best is None or (iv.bottom - iv.top) < (best.bottom - best.top):
                            best = iv
            elif isinstance(track, LithologyTrack):
                for iv in track._intervals:
                    item = IntervalItem(top=iv.top, bottom=iv.bottom, name=iv.lithology)
                    if item.top <= depth <= item.bottom:
                        if best is None or (item.bottom - item.top) < (best.bottom - best.top):
                            best = item
        return best

    # --- Rendering ---

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        h = self.column_height

        # Draw well name label above the column
        label_h = 28
        label_rect = QRectF(0, -label_h, self._column_width, label_h)
        painter.fillRect(label_rect, QColor("#f7fafc"))
        painter.setPen(QPen(QColor("#e2e8f0"), 1))
        painter.drawLine(QPointF(0, 0), QPointF(self._column_width, 0))
        font = QFont()
        font.setPixelSize(14)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor("#1a202c"))
        painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, self._well_name)

        # White background
        bg_rect = QRectF(0, 0, self._column_width, h)
        painter.fillRect(bg_rect, QColor("#ffffff"))

        if not self._tracks:
            painter.restore()
            return

        # Filter to visible tracks
        visible_tracks = [t for t in self._tracks if getattr(t, '_visible', True)]
        if not visible_tracks:
            painter.restore()
            return

        # Compute scale to fit tracks into column width
        natural_w = sum(t.width for t in visible_tracks)
        scale = self._column_width / natural_w if natural_w > 0 else 1.0

        # Compute scaled x offsets
        scaled: list[tuple[float, float]] = []
        x_off = 0.0
        for track in visible_tracks:
            sw = track.width * scale
            scaled.append((x_off, sw))
            x_off += sw

        # Draw group headers
        groups: dict[str, list[tuple[float, float]]] = {}
        for track, s in zip(visible_tracks, scaled):
            gn = track.group_name
            if gn:
                groups.setdefault(gn, []).append(s)

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
        max_header = max((t.header_height for t in visible_tracks), default=56)
        for track, (x_off, sw) in zip(visible_tracks, scaled):
            full_rect = QRectF(x_off, 0, sw, h)
            track.export_render(painter, full_rect, canvas_header_height=max_header)

        # Selection highlight
        if self.isSelected():
            painter.setPen(QPen(QColor("#3b82f6"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(bg_rect.adjusted(-1, -1, 1, 1))

        painter.restore()

    # --- Drag (horizontal only) ---

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start_x = event.pos().x()
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            new_x = self.pos().x() + event.pos().x() - self._drag_start_x
            self.setPos(new_x, self.pos().y())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self.well_moved.emit()
        super().mouseReleaseEvent(event)

    def hoverEnterEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        super().hoverLeaveEvent(event)
