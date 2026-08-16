"""2D profile strip for active fence VD + wells + tops + probe (#60/#62/#64)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Signal, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .color_scales import (
    GR_COLOR_SCALES,
    MISSING_GR_RGBA,
    SEISMIC_COLOR_SCALES,
    colorize_amplitude,
    colorize_gr,
)
from .models import VerticalDomain
from .scene import WellSeismicScene

# Empty-state guidance (#122) — not orthogonal IL/XL/T fallback
_EMPTY_FENCE_HINT = (
    "无活动剖面。在 3D 点选两口井，或用顶栏井对 +「井间剖面」创建 fence。"
)


class FenceProfile2D(QWidget):
    """Variable-density strip; click sets probe (s, z)."""

    probe_changed = Signal(float, float)  # s_m, z

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene: WellSeismicScene | None = None
        # None = follow the scene domain (2D/3D unified); an explicit
        # domain is only for callers that manage their own extraction.
        self._extract_domain: VerticalDomain | None = None
        self._label = QLabel("无活动剖面")
        self._label.setMinimumHeight(140)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("background: #0f172a; color: #94a3b8;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pix: QPixmap | None = None
        self._plot_width = 1
        self._legend_titles = ("地震振幅", "GR (API)")
        self._smax = 1.0
        self._z0 = 0.0
        self._z1 = 1.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)
        self._label.mousePressEvent = self._on_click  # type: ignore[method-assign]

    @property
    def rendered_image(self) -> QImage:
        """Latest complete profile image, including both color legends."""
        if self._pix is None:
            return QImage()
        return self._pix.toImage()

    @property
    def plot_width(self) -> int:
        """Width of the seismic plot excluding the legend rail."""
        return self._plot_width

    @property
    def legend_titles(self) -> tuple[str, str]:
        return self._legend_titles

    def set_extract_domain(self, domain: VerticalDomain | None) -> None:
        """Override sample-axis domain for extracts (None follows scene)."""
        self._extract_domain = domain
        self.refresh()

    def set_scene(self, scene: WellSeismicScene | None) -> None:
        self._scene = scene
        self.refresh()

    def refresh(self) -> None:
        if self._scene is None:
            self._label.setText("无场景")
            self._label.setPixmap(QPixmap())
            return
        if self._extract_domain is not None:
            ext = self._scene.extract_active_fence(domain=self._extract_domain)
        else:
            ext = self._scene.extract_active_fence()
        if ext is None:
            self._label.setText(_EMPTY_FENCE_HINT)
            self._label.setPixmap(QPixmap())
            return
        self._smax = float(ext.arc_length_m[-1]) or 1.0
        self._z0 = float(ext.sample_axis[0])
        self._z1 = float(ext.sample_axis[-1])
        settings = self._scene.display_settings
        img = self.amplitude_image(
            ext.amplitude,
            color_scale=settings.seismic_color_scale,
        )
        base_pix = QPixmap.fromImage(img)
        self._plot_width = base_pix.width()
        pix = QPixmap(base_pix.width() + 116, base_pix.height())
        pix.fill(QColor(15, 23, 42))
        painter = QPainter(pix)
        painter.drawPixmap(0, 0, base_pix)
        w, h = self._plot_width, pix.height()
        profile_domain = self._extract_domain or self._scene.vertical_domain
        hits = self._scene.assemble_active_profile_wells(
            domain=profile_domain
        )
        gr_range = self._scene.gr_value_range()
        for hit in hits:
            x = int(hit.s_m / self._smax * (w - 1))
            width = settings.well_width_px
            painter.setPen(QPen(QColor(15, 23, 42), width + 2))
            painter.drawLine(x, 0, x, h - 1)
            has_gr = (
                gr_range is not None
                and hit.curve_z is not None
                and hit.curve_values is not None
                and len(hit.curve_z) >= 2
                and np.any(np.isfinite(hit.curve_values))
            )
            if has_gr:
                curve_z = np.asarray(hit.curve_z, dtype=np.float64)
                curve_values = np.asarray(
                    hit.curve_values, dtype=np.float64
                )
                count = min(len(curve_z), len(curve_values))
                curve_z, curve_values = (
                    curve_z[:count],
                    curve_values[:count],
                )
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
                        QPen(
                            QColor(*[int(value) for value in rgba]),
                            width,
                        )
                    )
                    painter.drawLine(
                        x,
                        self._z_to_y(float(curve_z[index]), h),
                        x,
                        self._z_to_y(float(curve_z[index + 1]), h),
                    )
            else:
                painter.setPen(
                    QPen(QColor(*MISSING_GR_RGBA), width)
                )
                painter.drawLine(x, 0, x, h - 1)
            painter.setPen(QPen(QColor(226, 232, 240), 1))
            painter.drawText(x + 2, 12, hit.display_name)
            if not has_gr:
                painter.drawText(x + 2, 24, "无 GR")
            # tops
            painter.setPen(QPen(QColor(255, 200, 80), 1))
            for tname, tz in hit.tops:
                y = self._z_to_y(tz, h)
                painter.drawLine(x - 4, y, x + 4, y)
                painter.drawText(x + 6, y, tname)
        self._draw_color_legends(
            painter,
            x0=self._plot_width,
            height=h,
            seismic_scale=settings.seismic_color_scale,
            gr_scale=settings.gr_color_scale,
            amplitude_range=(
                -float(np.nanpercentile(np.abs(ext.amplitude), 98.0)),
                float(np.nanpercentile(np.abs(ext.amplitude), 98.0)),
            ),
            gr_range=gr_range,
        )
        if self._scene.probe is not None:
            p = self._scene.probe
            px = int(p.s_m / self._smax * (w - 1))
            py = self._z_to_y(p.z, h)
            painter.setPen(QPen(QColor(255, 80, 60), 2))
            painter.drawEllipse(px - 4, py - 4, 8, 8)
        painter.end()
        self._pix = pix
        self._label.setPixmap(pix)
        self._label.setText("")

    def _draw_color_legends(
        self,
        painter: QPainter,
        *,
        x0: int,
        height: int,
        seismic_scale: str,
        gr_scale: str,
        amplitude_range: tuple[float, float],
        gr_range: tuple[float, float] | None,
    ) -> None:
        painter.setPen(QColor(226, 232, 240))
        bar_top = 32
        bar_bottom = max(bar_top + 20, height - 28)
        for offset, title, stops, values in (
            (
                10,
                self._legend_titles[0],
                SEISMIC_COLOR_SCALES.get(
                    seismic_scale,
                    SEISMIC_COLOR_SCALES["blue-white-red"],
                ),
                amplitude_range,
            ),
            (
                64,
                self._legend_titles[1],
                GR_COLOR_SCALES.get(
                    gr_scale, GR_COLOR_SCALES["viridis"]
                ),
                gr_range,
            ),
        ):
            left = x0 + offset
            painter.drawText(left - 4, 15, title)
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
            painter.drawRect(
                QRectF(left, bar_top, 12, bar_bottom - bar_top)
            )
            painter.setPen(QColor(226, 232, 240))
            if values is None:
                painter.drawText(left + 15, bar_top + 10, "无数据")
            else:
                painter.drawText(left + 15, bar_top + 8, f"{values[1]:.3g}")
                painter.drawText(
                    left + 15, bar_bottom, f"{values[0]:.3g}"
                )

    def _z_to_y(self, z: float, h: int) -> int:
        if abs(self._z1 - self._z0) < 1e-12:
            return 0
        t = (z - self._z0) / (self._z1 - self._z0)
        return int(max(0, min(h - 1, t * (h - 1))))

    def _on_click(self, event) -> None:
        if self._pix is None or self._pix.isNull():
            return
        pos = event.position() if hasattr(event, "position") else event.pos()
        x, y = float(pos.x()), float(pos.y())
        w, h = self._plot_width, self._pix.height()
        if w <= 1 or h <= 1:
            return
        # map label coords to pixmap
        lw, lh = max(self._label.width(), 1), max(self._label.height(), 1)
        px = x / lw * (self._pix.width() - 1)
        if px >= w:
            return
        py = y / lh * (h - 1)
        s = px / max(w - 1, 1) * self._smax
        z = self._z0 + (py / max(h - 1, 1)) * (self._z1 - self._z0)
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
