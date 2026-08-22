"""2D ActiveTimeSlice map: amplitude + pierce points + well-order polyline."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from .color_scales import colorize_amplitude
from .models import VerticalDomain
from .scene import WellSeismicScene

_EMPTY = "Time 平面：加载地震体后，将在此显示当前 Time 切片、井点和井名。\n点击井点连线；右侧显示井间剖面。"


class TimeSliceMap2D(QWidget):
    """Plan-view ActiveTimeSlice. Click a well point to append it to the fence."""

    well_clicked = Signal(str)  # JointWellId

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene: WellSeismicScene | None = None
        self._amp: np.ndarray | None = None
        self._image: QImage | None = None
        self._pierces: list = []
        self._hits: list[tuple[float, float, str]] = []
        self._path_ids: list = []
        self._caption = ""
        self.setMinimumHeight(160)
        self.setMinimumWidth(180)
        self.setStyleSheet("background: #0f172a;")

    def set_scene(self, scene: WellSeismicScene | None) -> None:
        self._scene = scene
        self.refresh()

    def refresh(self) -> None:
        self._hits = []
        self._amp = None
        self._image = None
        self._pierces = []
        self._path_ids = []
        self._caption = ""
        scene = self._scene
        if scene is None:
            self.update()
            return
        if scene.vertical_domain is not VerticalDomain.TIME:
            self._caption = "Time 平面仅在 Time 域可用"
            self.update()
            return
        render = scene.orthogonal_slice_render_state()
        if render is None:
            self._caption = _EMPTY
            self.update()
            return
        _il, _xl, _times, active, _opacity = render
        try:
            amp = np.asarray(scene.slice_time(int(active)), dtype=np.float32)
        except Exception:
            self._caption = _EMPTY
            self.update()
            return
        if amp.ndim != 2 or amp.size == 0:
            self._caption = _EMPTY
            self.update()
            return
        rgba = np.ascontiguousarray(
            colorize_amplitude(
                amp, color_scale=scene.display_settings.seismic_color_scale
            )
        )
        h, w = int(rgba.shape[0]), int(rgba.shape[1])
        self._image = QImage(
            rgba.data, w, h, 4 * w, QImage.Format.Format_RGBA8888
        ).copy()
        self._amp = amp
        time_ms = scene.orthogonal_slice_state.active_time_ms
        self._caption = (
            f"Time 平面  {time_ms:.0f} ms" if time_ms is not None else "Time 平面"
        )
        self._pierces = list(scene.pierce_points_on_active_time())
        self._path_ids = list(scene.fence_well_ids)
        self._recompute_hits()
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._recompute_hits()
        self.update()

    def _plot_rect(self) -> QRect:
        return self.rect().adjusted(8, 22, -8, -8)

    def _recompute_hits(self) -> None:
        self._hits = []
        scene = self._scene
        amp = self._amp
        if scene is None or amp is None:
            return
        registration = scene.registration
        if registration is None:
            return
        rect = self._plot_rect()
        if rect.width() < 8 or rect.height() < 8:
            return
        ni, nx = int(amp.shape[0]), int(amp.shape[1])
        for pierce in self._pierces:
            vi, vx = registration.xy_to_volume_idx(pierce.x, pierce.y)
            px = rect.left() + (float(vx) + 0.5) / max(nx, 1) * (rect.width() - 1)
            py = rect.top() + (float(vi) + 0.5) / max(ni, 1) * (rect.height() - 1)
            self._hits.append((px, py, str(pierce.well_id)))

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(15, 23, 42))
        painter.setPen(QColor(226, 232, 240))
        painter.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        title = self._caption or "Time 平面"
        painter.drawText(8, 16, title)
        rect = self._plot_rect()
        if self._image is None:
            painter.setPen(QColor(148, 163, 184))
            painter.setFont(QFont("Sans Serif", 10))
            painter.drawText(
                rect,
                int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                _EMPTY,
            )
            painter.end()
            return
        scaled = QPixmap.fromImage(self._image).scaled(
            rect.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(rect.topLeft(), scaled)
        path_ids = set(self._path_ids)
        by_id: dict[object, tuple[float, float]] = {}
        for pierce, (px, py, _wid) in zip(self._pierces, self._hits):
            by_id[pierce.well_id] = (px, py)
            painter.setPen(QPen(QColor(15, 23, 42), 3))
            painter.setBrush(QColor(250, 204, 21))
            painter.drawEllipse(int(px) - 5, int(py) - 5, 10, 10)
            painter.setPen(QPen(QColor(250, 204, 21), 1))
            painter.drawEllipse(int(px) - 5, int(py) - 5, 10, 10)
            painter.setFont(QFont("Sans Serif", 9, QFont.Weight.Bold))
            painter.setPen(QColor(15, 23, 42))
            painter.drawText(int(px) + 8, int(py) + 1, pierce.display_name)
            painter.setPen(QColor(254, 240, 138))
            painter.drawText(int(px) + 7, int(py), pierce.display_name)
        pts = [by_id[wid] for wid in self._path_ids if wid in by_id]
        if len(pts) >= 2:
            painter.setPen(QPen(QColor(34, 211, 238), 2))
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                painter.drawLine(int(x0), int(y0), int(x1), int(y1))
        painter.end()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or not self._hits:
            return
        pos = event.position() if hasattr(event, "position") else event.pos()
        x, y = float(pos.x()), float(pos.y())
        best = None
        for px, py, well_id in self._hits:
            dist = (px - x) ** 2 + (py - y) ** 2
            if dist <= 18.0 ** 2 and (best is None or dist < best[0]):
                best = (dist, well_id)
        if best is not None:
            self.well_clicked.emit(best[1])
