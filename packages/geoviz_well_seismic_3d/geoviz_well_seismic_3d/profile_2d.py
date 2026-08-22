"""2D profile strip for active fence VD + wells + tops + probe (#60/#62/#64)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, QRectF, Signal, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from .color_scales import (
    GR_COLOR_SCALES,
    MISSING_GR_RGBA,
    SEISMIC_COLOR_SCALES,
    colorize_amplitude,
    colorize_gr,
)
from .models import VerticalDomain
from .scene import WellSeismicScene

_EMPTY_FENCE_HINT = (
    "无活动剖面。在左侧 Time 平面点井连线，或用顶栏井对 +「井间剖面」。"
)
_LEGEND_W = 108
_TITLE_H = 22
_MARGIN = 8


class FenceProfile2D(QWidget):
    """Variable-density strip; click sets probe (s, z). Fills the widget."""

    probe_changed = Signal(float, float)  # s_m, z

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene: WellSeismicScene | None = None
        self._extract_domain: VerticalDomain | None = None
        self._ext = None
        self._hits = []
        self._image: QImage | None = None
        self._pix: QPixmap | None = None
        self._plot_width = 1
        self._legend_titles = ("地震振幅", "GR (API)")
        self._smax = 1.0
        self._z0 = 0.0
        self._z1 = 1.0
        self._hint = _EMPTY_FENCE_HINT
        self.setMinimumHeight(140)
        self.setMinimumWidth(180)
        self.setStyleSheet("background: #0f172a;")

    @property
    def rendered_image(self) -> QImage:
        """Latest complete profile image, including both color legends."""
        if self.width() < 32 or self.height() < 32:
            self.resize(max(self.width(), 800), max(self.height(), 280))
        image = QImage(self.size(), QImage.Format.Format_ARGB32)
        image.fill(QColor(15, 23, 42))
        painter = QPainter(image)
        self._paint(painter, self.rect())
        painter.end()
        return image

    @property
    def plot_width(self) -> int:
        """Width of the seismic plot excluding the legend rail."""
        return max(1, self._plot_rect().width())

    @property
    def legend_titles(self) -> tuple[str, str]:
        return self._legend_titles

    def set_extract_domain(self, domain: VerticalDomain | None) -> None:
        self._extract_domain = domain
        self.refresh()

    def set_scene(self, scene: WellSeismicScene | None) -> None:
        self._scene = scene
        self.refresh()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self.update()

    def refresh(self) -> None:
        self._ext = None
        self._hits = []
        self._image = None
        self._pix = None
        scene = self._scene
        if scene is None:
            self._hint = "无场景"
            self.update()
            return
        if self._extract_domain is not None:
            ext = scene.extract_active_fence(domain=self._extract_domain)
        else:
            ext = scene.extract_active_fence()
        if ext is None:
            self._hint = _EMPTY_FENCE_HINT
            self.update()
            return
        self._ext = ext
        self._smax = float(ext.arc_length_m[-1]) or 1.0
        self._z0 = float(ext.sample_axis[0])
        self._z1 = float(ext.sample_axis[-1])
        rgba = colorize_amplitude(
            np.asarray(ext.amplitude, dtype=np.float32).T,
            color_scale=scene.display_settings.seismic_color_scale,
        )
        h, w = int(rgba.shape[0]), int(rgba.shape[1])
        self._image = QImage(
            np.ascontiguousarray(rgba).data, w, h, 4 * w, QImage.Format.Format_RGBA8888
        ).copy()
        domain = self._extract_domain or scene.vertical_domain
        self._hits = scene.assemble_active_profile_wells(domain=domain)
        self._hint = ""
        self.update()

    def _plot_rect(self) -> QRect:
        return self.rect().adjusted(_MARGIN, _TITLE_H, -(_LEGEND_W + 4), -_MARGIN)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint(painter, self.rect())
        painter.end()

    def _paint(self, painter: QPainter, bounds: QRect) -> None:
        painter.fillRect(bounds, QColor(15, 23, 42))
        painter.setPen(QColor(226, 232, 240))
        painter.setFont(QFont("Sans Serif", 10, QFont.Weight.DemiBold))
        painter.drawText(bounds.adjusted(_MARGIN, 4, 0, 0), "井间剖面")
        plot = QRect(
            bounds.left() + _MARGIN,
            bounds.top() + _TITLE_H,
            max(1, bounds.width() - _MARGIN - _LEGEND_W - 4),
            max(1, bounds.height() - _TITLE_H - _MARGIN),
        )
        self._plot_width = plot.width()
        if self._image is None or self._ext is None:
            painter.setPen(QColor(148, 163, 184))
            painter.setFont(QFont("Sans Serif", 10))
            painter.drawText(
                plot,
                int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                self._hint or _EMPTY_FENCE_HINT,
            )
            return
        scaled = QPixmap.fromImage(self._image).scaled(
            plot.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(plot.topLeft(), scaled)
        self._pix = scaled
        scene = self._scene
        settings = scene.display_settings if scene is not None else None
        w, h = plot.width(), plot.height()
        gr_range = scene.gr_value_range() if scene is not None else None
        for hit in self._hits:
            x = plot.left() + int(hit.s_m / self._smax * (w - 1))
            width = settings.well_width_px if settings is not None else 5
            painter.setPen(QPen(QColor(15, 23, 42), width + 2))
            painter.drawLine(x, plot.top(), x, plot.bottom())
            has_gr = (
                gr_range is not None
                and hit.curve_z is not None
                and hit.curve_values is not None
                and len(hit.curve_z) >= 2
                and np.any(np.isfinite(hit.curve_values))
            )
            if has_gr:
                curve_z = np.asarray(hit.curve_z, dtype=np.float64)
                curve_values = np.asarray(hit.curve_values, dtype=np.float64)
                count = min(len(curve_z), len(curve_values))
                for index in range(count - 1):
                    v0, v1 = curve_values[index : index + 2]
                    if np.isfinite(v0) and np.isfinite(v1):
                        rgba = self.gr_colors(
                            np.array([(v0 + v1) * 0.5]),
                            value_range=gr_range,
                            color_scale=settings.gr_color_scale,
                        )[0]
                    else:
                        rgba = np.asarray(MISSING_GR_RGBA, dtype=np.uint8)
                    painter.setPen(
                        QPen(QColor(*[int(value) for value in rgba]), width)
                    )
                    painter.drawLine(
                        x,
                        plot.top() + self._z_to_y(float(curve_z[index]), h),
                        x,
                        plot.top() + self._z_to_y(float(curve_z[index + 1]), h),
                    )
            else:
                painter.setPen(QPen(QColor(*MISSING_GR_RGBA), width))
                painter.drawLine(x, plot.top(), x, plot.bottom())
            painter.setFont(QFont("Sans Serif", 9, QFont.Weight.Bold))
            painter.setPen(QColor(15, 23, 42))
            painter.drawText(x + 3, plot.top() + 13, hit.display_name)
            painter.setPen(QColor(254, 240, 138))
            painter.drawText(x + 2, plot.top() + 12, hit.display_name)
            if not has_gr:
                painter.setPen(QColor(148, 163, 184))
                painter.drawText(x + 2, plot.top() + 24, "无 GR")
            painter.setPen(QPen(QColor(255, 200, 80), 1))
            for tname, tz in hit.tops:
                y = plot.top() + self._z_to_y(tz, h)
                painter.drawLine(x - 4, y, x + 4, y)
                painter.drawText(x + 6, y, tname)
        amp = np.asarray(self._ext.amplitude, dtype=np.float32)
        self._draw_color_legends(
            painter,
            x0=plot.right() + 8,
            top=plot.top(),
            height=plot.height(),
            seismic_scale=settings.seismic_color_scale if settings else "blue-white-red",
            gr_scale=settings.gr_color_scale if settings else "viridis",
            amplitude_range=(
                -float(np.nanpercentile(np.abs(amp), 98.0)),
                float(np.nanpercentile(np.abs(amp), 98.0)),
            ),
            gr_range=gr_range,
        )
        if scene is not None and scene.probe is not None:
            p = scene.probe
            px = plot.left() + int(p.s_m / self._smax * (w - 1))
            py = plot.top() + self._z_to_y(p.z, h)
            painter.setPen(QPen(QColor(255, 80, 60), 2))
            painter.setBrush(QColor(255, 80, 60, 80))
            painter.drawEllipse(px - 5, py - 5, 10, 10)

    def _draw_color_legends(
        self,
        painter: QPainter,
        *,
        x0: int,
        top: int,
        height: int,
        seismic_scale: str,
        gr_scale: str,
        amplitude_range: tuple[float, float],
        gr_range: tuple[float, float] | None,
    ) -> None:
        painter.setPen(QColor(226, 232, 240))
        painter.setFont(QFont("Sans Serif", 8))
        bar_top = top + 18
        bar_bottom = max(bar_top + 20, top + height - 12)
        for offset, title, stops, values in (
            (
                0,
                self._legend_titles[0],
                SEISMIC_COLOR_SCALES.get(
                    seismic_scale,
                    SEISMIC_COLOR_SCALES["blue-white-red"],
                ),
                amplitude_range,
            ),
            (
                52,
                self._legend_titles[1],
                GR_COLOR_SCALES.get(gr_scale, GR_COLOR_SCALES["viridis"]),
                gr_range,
            ),
        ):
            left = x0 + offset
            painter.setPen(QColor(226, 232, 240))
            painter.drawText(left - 2, top + 12, title)
            gradient = QLinearGradient(
                float(left), float(bar_bottom), float(left), float(bar_top)
            )
            for index, color in enumerate(stops):
                gradient.setColorAt(
                    index / max(len(stops) - 1, 1),
                    QColor(*color),
                )
            painter.fillRect(
                QRectF(left, bar_top, 12, bar_bottom - bar_top),
                QBrush(gradient),
            )
            painter.setPen(QPen(QColor(148, 163, 184), 1))
            painter.drawRect(QRectF(left, bar_top, 12, bar_bottom - bar_top))
            painter.setPen(QColor(226, 232, 240))
            if values is None:
                painter.drawText(left + 15, bar_top + 10, "无数据")
            else:
                painter.drawText(left + 15, bar_top + 8, f"{values[1]:.3g}")
                painter.drawText(left + 15, bar_bottom, f"{values[0]:.3g}")

    def _z_to_y(self, z: float, h: int) -> int:
        if abs(self._z1 - self._z0) < 1e-12:
            return 0
        t = (z - self._z0) / (self._z1 - self._z0)
        return int(max(0, min(h - 1, t * (h - 1))))

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._on_click(event)

    def _on_click(self, event) -> None:
        if self._ext is None or self._image is None:
            return
        pos = event.position() if hasattr(event, "position") else event.pos()
        x, y = float(pos.x()), float(pos.y())
        plot = self._plot_rect()
        if not plot.contains(int(x), int(y)):
            return
        w, h = max(plot.width(), 1), max(plot.height(), 1)
        s = (x - plot.left()) / max(w - 1, 1) * self._smax
        z = self._z0 + ((y - plot.top()) / max(h - 1, 1)) * (self._z1 - self._z0)
        self.probe_changed.emit(float(s), float(z))
        self.refresh()

    @staticmethod
    def amplitude_image(
        amp: np.ndarray,
        *,
        color_scale: str = "blue-white-red",
    ) -> QImage:
        """Render a zero-centred seismic amplitude image."""
        a = np.asarray(amp, dtype=np.float32).T
        rgba = colorize_amplitude(a, color_scale=color_scale)
        h, w = a.shape
        sy = max(1, 280 // max(h, 1))
        sx = max(1, 640 // max(w, 1))
        rgba = np.repeat(np.repeat(rgba, sy, axis=0), sx, axis=1)
        h2, w2 = rgba.shape[:2]
        img = QImage(rgba.data, w2, h2, 4 * w2, QImage.Format.Format_RGBA8888)
        return img.copy()

    @staticmethod
    def gr_colors(
        values: np.ndarray,
        *,
        value_range: tuple[float, float],
        color_scale: str = "viridis",
    ) -> np.ndarray:
        """Return RGBA colors for GR samples and neutral gray for missing data."""
        return colorize_gr(
            values,
            value_range=value_range,
            color_scale=color_scale,
        )
