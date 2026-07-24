"""Minimal 2D profile strip widget for active fence VD (#60 / #62)."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage, QPainter, QColor, QPen
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .scene import WellSeismicScene


class FenceProfile2D(QWidget):
    """Variable-density strip + well markers for active fence extraction."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._scene: WellSeismicScene | None = None
        self._label = QLabel("无活动剖面")
        self._label.setMinimumHeight(120)
        self._label.setStyleSheet("background: #0f172a; color: #94a3b8;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._label)

    def set_scene(self, scene: WellSeismicScene | None) -> None:
        self._scene = scene
        self.refresh()

    def refresh(self) -> None:
        if self._scene is None:
            self._label.setText("无场景")
            self._label.setPixmap(None)  # type: ignore[arg-type]
            return
        ext = self._scene.extract_active_fence()
        if ext is None:
            self._label.setText("无活动剖面提取（需体积 + 剖面线）")
            return
        img = self._amplitude_to_image(ext.amplitude)
        hits = self._scene.assemble_active_profile_wells()
        # Paint markers
        from PySide6.QtGui import QPixmap

        pix = QPixmap.fromImage(img)
        painter = QPainter(pix)
        painter.setPen(QPen(QColor(80, 255, 120), 2))
        w, h = pix.width(), pix.height()
        smax = float(ext.arc_length_m[-1]) or 1.0
        for hit in hits:
            x = int(hit.s_m / smax * (w - 1))
            painter.drawLine(x, 0, x, h - 1)
            painter.drawText(x + 2, 12, hit.name)
        painter.end()
        self._label.setPixmap(pix)
        self._label.setText("")

    @staticmethod
    def _amplitude_to_image(amp: np.ndarray) -> QImage:
        a = np.asarray(amp, dtype=np.float32)
        # amp is (n_along, n_sample) — display with sample vertical
        a = a.T  # (sample, along)
        lo, hi = np.nanpercentile(a, 2), np.nanpercentile(a, 98)
        if not np.isfinite(lo) or not np.isfinite(hi) or hi <= lo:
            lo, hi = float(np.nanmin(a)), float(np.nanmax(a) + 1e-6)
        norm = np.clip((a - lo) / (hi - lo + 1e-12), 0, 1)
        gray = (norm * 255).astype(np.uint8)
        # Simple blue-white-red-ish via grayscale for MVP
        h, w = gray.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[..., 0] = gray
        rgba[..., 1] = gray
        rgba[..., 2] = 255 - gray // 2
        rgba[..., 3] = 255
        # Scale up for visibility
        scale = max(1, 400 // max(w, 1))
        rgba = np.repeat(np.repeat(rgba, scale, axis=0), max(1, 600 // max(h, 1)), axis=1)
        h2, w2 = rgba.shape[:2]
        img = QImage(rgba.data, w2, h2, 4 * w2, QImage.Format.Format_RGBA8888)
        return img.copy()
