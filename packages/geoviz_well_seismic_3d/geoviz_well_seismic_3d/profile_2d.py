"""2D profile strip for active fence VD + wells + tops + probe (#60/#62/#64)."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

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
        # None = follow scene domain; Time = force Time extract (workbench #122)
        self._extract_domain: VerticalDomain | None = None
        self._label = QLabel("无活动剖面")
        self._label.setMinimumHeight(140)
        self._label.setWordWrap(True)
        self._label.setStyleSheet("background: #0f172a; color: #94a3b8;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pix: QPixmap | None = None
        self._smax = 1.0
        self._z0 = 0.0
        self._z1 = 1.0
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)
        self._label.mousePressEvent = self._on_click  # type: ignore[method-assign]

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
        img = self._amplitude_to_image(ext.amplitude)
        pix = QPixmap.fromImage(img)
        painter = QPainter(pix)
        w, h = pix.width(), pix.height()
        hits = self._scene.assemble_active_profile_wells()
        for hit in hits:
            x = int(hit.s_m / self._smax * (w - 1))
            painter.setPen(QPen(QColor(80, 255, 120), 2))
            painter.drawLine(x, 0, x, h - 1)
            painter.drawText(x + 2, 12, hit.display_name)
            # tops
            painter.setPen(QPen(QColor(255, 200, 80), 1))
            for tname, tz in hit.tops:
                y = self._z_to_y(tz, h)
                painter.drawLine(x - 4, y, x + 4, y)
                painter.drawText(x + 6, y, tname)
            # simple curve scale tick
            if hit.curve_name and hit.curve_values is not None:
                painter.setPen(QPen(QColor(180, 180, 255), 1))
                painter.drawText(x + 2, h - 4, hit.curve_name)
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
        w, h = self._pix.width(), self._pix.height()
        if w <= 1 or h <= 1:
            return
        # map label coords to pixmap
        lw, lh = max(self._label.width(), 1), max(self._label.height(), 1)
        px = x / lw * (w - 1)
        py = y / lh * (h - 1)
        s = px / max(w - 1, 1) * self._smax
        z = self._z0 + (py / max(h - 1, 1)) * (self._z1 - self._z0)
        self.probe_changed.emit(float(s), float(z))
        self.refresh()

    @staticmethod
    def _amplitude_to_image(amp: np.ndarray) -> QImage:
        a = np.asarray(amp, dtype=np.float32).T
        lo, hi = np.nanpercentile(a, 2), np.nanpercentile(a, 98)
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo, hi = float(np.nanmin(a)), float(np.nanmax(a) + 1e-6)
        norm = np.clip((a - lo) / (hi - lo + 1e-12), 0, 1)
        gray = (norm * 255).astype(np.uint8)
        h, w = gray.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = gray
        rgba[..., 1] = gray
        rgba[..., 2] = 255 - gray // 2
        rgba[..., 3] = 255
        sy = max(1, 280 // max(h, 1))
        sx = max(1, 640 // max(w, 1))
        rgba = np.repeat(np.repeat(rgba, sy, axis=0), sx, axis=1)
        h2, w2 = rgba.shape[:2]
        img = QImage(rgba.data, w2, h2, 4 * w2, QImage.Format.Format_RGBA8888)
        return img.copy()
