from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal, QObject, QEvent, QSize
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QMouseEvent, QPixmap, QCursor
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QApplication, QToolTip, QWidget

from .track_base import BaseTrack, ECHARTS_HEADER_BG, ECHARTS_BORDER, ECHARTS_TEXT, ECHARTS_GROUP_HEADER_HEIGHT
from .coordinator import LayoutCoordinator
from .overlay import CrosshairOverlay

# Track resize handle constants
_RESIZE_HANDLE_WIDTH = 6  # px, clickable zone
_TRACK_MIN_WIDTH = 40
_TRACK_MAX_WIDTH = 300


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


class WellLogCanvas(QWidget):
    """Main canvas widget for well log visualization.

    Manages track layout, depth range, and provides unified paint_all()
    for both display and vector export.
    """

    depth_range_changed = Signal(float, float)
    cursor_moved = Signal(float)
    mouse_moved = Signal(float)  # y position in canvas coordinates, -1 = left

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAutoFillBackground(True)
        self.setMouseTracking(True)
        self._coordinator = LayoutCoordinator()
        self._track_filter = _TrackMouseFilter(self)
        from .overlay import CrosshairOverlay
        self._crosshair: CrosshairOverlay | None = CrosshairOverlay(self)
        self._depth_span: float = 100.0
        self._static_cache: QPixmap | None = None
        self._cache_dirty: bool = True
        self.setMinimumSize(200, 400)
        # Track resize state
        self._resize_left_idx: int = -1  # index of left track being resized
        self._resize_right_idx: int = -1  # index of right track being resized
        self._resize_anchor_x: float = 0.0  # mouse x at drag start
        self._resize_left_orig_w: int = 0
        self._resize_right_orig_w: int = 0
        self._is_resizing: bool = False
        # Mouse drag panning state
        self._is_panning: bool = False
        self._pan_start_y: float = 0.0
        self._pan_start_top: float = 0.0
        self._pan_start_bottom: float = 100.0

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
        self.setMinimumWidth(natural_width)
        scale = max(1.0, w / natural_width) if natural_width > 0 else 1.0

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
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.drawPixmap(0, 0, self._static_cache)
        if self._crosshair and self._crosshair.visible and self.tracks:
            self._crosshair.paint_overlay(painter, QRectF(self.rect()))
        painter.end()

    def leaveEvent(self, event):
        if self._crosshair:
            self._crosshair.set_cursor_pos(None, None)
            self.update()
        self.mouse_moved.emit(-1.0)
        if not self._is_resizing:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().leaveEvent(event)

    # --- Track resize handle logic ---

    def _handle_x_positions(self) -> list[tuple[float, int, int]]:
        """Return list of (x_center, left_track_idx, right_track_idx) for resize handles."""
        visible = [(i, t) for i, t in enumerate(self.tracks) if getattr(t, '_visible', True)]
        if len(visible) < 2:
            return []
        w = self.width()
        natural_width = self.total_width
        scale = w / natural_width if natural_width > 0 else 1.0
        handles = []
        x = 0.0
        for idx in range(len(visible) - 1):
            _, track = visible[idx]
            sw = track.width * scale
            x += sw
            handles.append((x, visible[idx][0], visible[idx + 1][0]))
        return handles

    def _hit_handle(self, mouse_x: float) -> tuple[int, int] | None:
        """Return (left_idx, right_idx) if mouse_x is near a resize handle, else None."""
        half = _RESIZE_HANDLE_WIDTH / 2
        for hx, li, ri in self._handle_x_positions():
            if abs(mouse_x - hx) <= half:
                return (li, ri)
        return None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            hit = self._hit_handle(event.position().x())
            if hit is not None and event.button() == Qt.MouseButton.LeftButton:
                li, ri = hit
                self._resize_left_idx = li
                self._resize_right_idx = ri
                self._resize_anchor_x = event.position().x()
                self._resize_left_orig_w = self.tracks[li].width
                self._resize_right_orig_w = self.tracks[ri].width
                self._is_resizing = True
                event.accept()
                return
            elif self.tracks:
                self._is_panning = True
                self._pan_start_y = event.position().y()
                self._pan_start_top = self.tracks[0].depth_top
                self._pan_start_bottom = self.tracks[0].depth_bottom
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._is_panning and self.tracks:
            header_h = max((t.header_height for t in self.tracks), default=56)
            content_h = max(1.0, self.height() - header_h)
            depth_span = self._pan_start_bottom - self._pan_start_top
            dy = event.position().y() - self._pan_start_y
            delta_depth = -(dy / content_h) * depth_span
            new_top = self._pan_start_top + delta_depth
            new_bottom = self._pan_start_bottom + delta_depth
            self.set_depth_range(new_top, new_bottom)
            event.accept()
            return

        if self._is_resizing:
            dx = event.position().x() - self._resize_anchor_x
            li, ri = self._resize_left_idx, self._resize_right_idx
            new_left = max(_TRACK_MIN_WIDTH, min(_TRACK_MAX_WIDTH, self._resize_left_orig_w + int(dx)))
            new_right = max(_TRACK_MIN_WIDTH, min(_TRACK_MAX_WIDTH, self._resize_right_orig_w - int(dx)))
            if self.tracks[li].width != new_left or self.tracks[ri].width != new_right:
                self.tracks[li].set_width(new_left)
                self.tracks[ri].set_width(new_right)
                self._cache_dirty = True
                self.setMinimumWidth(self.total_width)
                self.update()
            event.accept()
            return

        # Update cursor for resize handles
        hit = self._hit_handle(event.position().x())
        if hit is not None:
            self.setCursor(Qt.CursorShape.SplitHCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

        # Hide crosshair when cursor is in the track header area
        header_h = max((t.header_height for t in self.tracks), default=56)
        pos = event.position()
        if pos.y() < header_h:
            self.mouse_moved.emit(-1.0)
            if self._crosshair:
                self._crosshair.set_cursor_pos(None, None)
        else:
            self.mouse_moved.emit(float(pos.y()))
            if self._crosshair:
                self._crosshair.set_cursor_pos(float(pos.x()), float(pos.y()))

        self.update()
        self._update_hover_tooltip(event.position())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        if self._is_resizing and event.button() == Qt.MouseButton.LeftButton:
            self._is_resizing = False
            self._resize_left_idx = -1
            self._resize_right_idx = -1
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        if not self.tracks:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        factor = 0.88 if delta > 0 else 1.14
        top = self.tracks[0].depth_top
        bottom = self.tracks[0].depth_bottom
        depth_span = bottom - top

        pos_y = event.position().y()
        header_h = max((t.header_height for t in self.tracks), default=56)
        content_h = max(1.0, self.height() - header_h)
        rel_y = max(0.0, min(content_h, pos_y - header_h))
        pivot_depth = top + (rel_y / content_h) * depth_span

        new_span = max(1.0, depth_span * factor)
        ratio = (pivot_depth - top) / max(1e-6, depth_span)

        new_top = pivot_depth - ratio * new_span
        new_bottom = new_top + new_span

        self.set_depth_range(new_top, new_bottom)
        event.accept()

    def _interpolate_curve_val(self, curve, depth: float) -> float | None:
        if not getattr(curve, "depth", None) or not getattr(curve, "values", None):
            return None
        depths = curve.depth
        vals = curve.values
        if len(depths) != len(vals) or len(depths) == 0:
            return None
        if depth < depths[0] or depth > depths[-1]:
            return None
        import bisect
        idx = bisect.bisect_left(depths, depth)
        if idx == 0:
            return vals[0]
        if idx >= len(depths):
            return vals[-1]
        d0, d1 = depths[idx - 1], depths[idx]
        v0, v1 = vals[idx - 1], vals[idx]
        if abs(d1 - d0) < 1e-6:
            return v0
        t = (depth - d0) / (d1 - d0)
        return v0 + t * (v1 - v0)

    def _update_hover_tooltip(self, pos):
        if not self.tracks or pos.y() < 56:
            QToolTip.hideText()
            return

        visible = [(i, t) for i, t in enumerate(self.tracks) if getattr(t, "_visible", True)]
        if not visible:
            QToolTip.hideText()
            return

        w = self.width()
        natural_width = self.total_width
        scale = max(1.0, w / natural_width) if natural_width > 0 else 1.0

        x = pos.x()
        cur_x = 0.0
        target_track = None
        for _, track in visible:
            sw = track.width * scale
            if cur_x <= x < cur_x + sw:
                target_track = track
                break
            cur_x += sw

        if target_track is None:
            QToolTip.hideText()
            return

        top = target_track.depth_top
        bottom = target_track.depth_bottom
        h = self.height()
        header_h = max((t.header_height for t in self.tracks), default=56)
        content_h = max(1.0, h - header_h)
        rel_y = max(0.0, min(content_h, pos.y() - header_h))
        depth = top + (rel_y / content_h) * (bottom - top)

        label = getattr(target_track, "label", "井道")
        lines = [f"📍 深度: {depth:.2f} m  [{label}]"]

        if hasattr(target_track, "curves"):
            for curve in target_track.curves:
                val = self._interpolate_curve_val(curve, depth)
                if val is not None:
                    unit_str = f" {curve.unit}" if getattr(curve, "unit", "") else ""
                    lines.append(f"  • {curve.name}: {val:.2f}{unit_str}")
        elif hasattr(target_track, "intervals") and target_track.intervals:
            for item in target_track.intervals:
                if item.top <= depth <= item.bottom:
                    lines.append(f"  • {item.name} ({item.top:.1f}m - {item.bottom:.1f}m)")
        elif hasattr(target_track, "core_photos") and target_track.core_photos:
            for photo in target_track.core_photos:
                if photo.depth_top <= depth <= photo.depth_bottom:
                    lines.append(f"  • 描述: 📷 {photo.title} ({photo.depth_top:.1f}m - {photo.depth_bottom:.1f}m)")
                    lines.append("    (双击弹出查看详情)")

        QToolTip.showText(self.mapToGlobal(pos.toPoint()), "\n".join(lines), self)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            visible = [(i, t) for i, t in enumerate(self.tracks) if getattr(t, "_visible", True)]
            w = self.width()
            natural_width = self.total_width
            scale = max(1.0, w / natural_width) if natural_width > 0 else 1.0
            x = pos.x()
            cur_x = 0.0
            for _, track in visible:
                sw = track.width * scale
                if cur_x <= x < cur_x + sw:
                    if hasattr(track, "core_photos") and track.core_photos:
                        top = track.depth_top
                        bottom = track.depth_bottom
                        h = self.height()
                        header_h = max((t.header_height for t in self.tracks), default=56)
                        content_h = max(1.0, h - header_h)
                        rel_y = max(0.0, min(content_h, pos.y() - header_h))
                        depth = top + (rel_y / content_h) * (bottom - top)
                        for photo in track.core_photos:
                            if photo.depth_top <= depth <= photo.depth_bottom:
                                try:
                                    import os
                                    from geoviz_well_log.image_preview_dialog import ImagePreviewDialog
                                    pix = photo.pixmap
                                    if pix is None and photo.image_path and os.path.exists(photo.image_path):
                                        pix = QPixmap(photo.image_path)
                                    if pix is not None and not pix.isNull():
                                        dlg = ImagePreviewDialog(pix, photo.title, self)
                                        dlg.exec()
                                except Exception:
                                    pass
                    break
                cur_x += sw
        super().mouseDoubleClickEvent(event)
