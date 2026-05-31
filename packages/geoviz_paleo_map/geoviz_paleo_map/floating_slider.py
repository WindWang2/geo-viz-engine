"""FloatingScaleSlider — premium glassmorphic map scale slider overlay."""
from __future__ import annotations

import math
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget

# 96 DPI: 1 pixel = 0.02646 cm
_CM_PER_PX = 0.02646

# Canvas zoom limits (must match ZoomPanHandler)
_ZOOM_MIN = 0.1
_ZOOM_MAX = 10.0


class FloatingScaleSlider(QWidget):
    """Floating scale bar slider showing 1:XXX ratio (log2 scale) overlaying the canvas.

    Left = zoomed in (small denominator), right = zoomed out (large denominator).
    Dragging changes the canvas zoom level.
    """
    zoom_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(54)
        self.setFixedWidth(320)
        self._zoom = 2.0
        self._canvas_w = 800
        self._kpd = 111.32
        self._scale_min = 1.0   # zoomed-in end (small denom)
        self._scale_max = 1.0   # zoomed-out end (large denom)
        self._log2_smin = 0.0
        self._log2_smax = 0.0
        self._scale_ticks: list[tuple[float, str]] = []
        self._threshold_zooms: list[float] = []

        # Interactive button rects
        self._btn_minus_rect = QRectF(10, 16, 22, 22)
        self._btn_plus_rect = QRectF(320 - 10 - 22, 16, 22, 22)

    def set_params(self, canvas_w: int, kpd: float,
                   threshold_zooms: list[float]) -> None:
        self._canvas_w = max(1, canvas_w)
        self._kpd = kpd
        self._threshold_zooms = list(threshold_zooms)
        # Compute scale range from actual zoom limits
        self._scale_min = self._zoom_to_scale_den(_ZOOM_MAX)  # most zoomed in
        self._scale_max = self._zoom_to_scale_den(_ZOOM_MIN)  # most zoomed out
        self._log2_smin = math.log2(self._scale_min)
        self._log2_smax = math.log2(self._scale_max)
        self._scale_ticks = self._make_ticks()
        self.update()

    def _make_ticks(self) -> list[tuple[float, str]]:
        """Generate nice 1:XXX tick marks within the slider's scale range with spacing guard."""
        raw = [5_000, 10_000, 25_000, 50_000, 100_000,
               250_000, 500_000, 1_000_000, 2_000_000,
               5_000_000, 10_000_000, 25_000_000, 50_000_000,
               100_000_000, 200_000_000]
        ticks = []
        last_x = -999.0
        for d in raw:
            if self._scale_min * 0.8 <= d <= self._scale_max * 1.2:
                frac = self._den_to_frac(d)
                tx = self._frac_to_x(frac)
                # Ensure ticks are spaced by at least 45 pixels to prevent text overlap
                if tx - last_x >= 45.0:
                    if d >= 100_000_000:
                        lbl = f"1:{d // 100_000_000}亿"
                    elif d >= 100_000:
                        lbl = f"1:{d // 10_000}万"
                    elif d >= 1_000:
                        lbl = f"1:{d // 1_000}千"
                    else:
                        lbl = f"1:{d}"
                    ticks.append((float(d), lbl))
                    last_x = tx
        return ticks

    def set_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self.update()

    # --- math: zoom ↔ scale denominator ↔ slider position ---

    def _zoom_to_scale_den(self, zoom: float) -> float:
        """Scale denominator at given zoom. Smaller = more zoomed in."""
        km_per_deg = self._kpd
        km_per_px = km_per_deg / (2 ** (zoom - 1))
        return (km_per_px * 1e5) / _CM_PER_PX

    def _scale_den_to_zoom(self, den: float) -> float:
        km_per_px = (den * _CM_PER_PX) / 1e5
        km_per_deg = self._kpd
        return math.log2(km_per_deg / km_per_px) + 1.0

    def _den_to_frac(self, den: float) -> float:
        """0.0 = left (small den = zoomed in), 1.0 = right (large den = zoomed out)."""
        log2_d = math.log2(max(self._scale_min, min(self._scale_max, den)))
        if self._log2_smax <= self._log2_smin:
            return 0.5
        return (log2_d - self._log2_smin) / (self._log2_smax - self._log2_smin)

    def _frac_to_den(self, frac: float) -> float:
        log2_d = self._log2_smin + frac * (self._log2_smax - self._log2_smin)
        return 2 ** log2_d

    def _zoom_to_frac(self, zoom: float) -> float:
        return self._den_to_frac(self._zoom_to_scale_den(zoom))

    def _frac_to_zoom(self, frac: float) -> float:
        return self._scale_den_to_zoom(self._frac_to_den(frac))

    def _track_rect(self):
        # Left padding takes button space: 10 + 22 + 10 = 42
        # Right padding takes button space: 10 + 22 + 10 = 42
        x0 = 42.0
        x1 = 320.0 - 42.0
        return x0, x1

    def _frac_to_x(self, frac: float) -> float:
        x0, x1 = self._track_rect()
        return x0 + frac * (x1 - x0)

    def _x_to_frac(self, x: float) -> float:
        x0, x1 = self._track_rect()
        if x1 <= x0:
            return 0.5
        return max(0.0, min(1.0, (x - x0) / (x1 - x0)))

    # --- mouse ---

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            if self._btn_minus_rect.contains(pos):
                self._zoom_by(-0.5)
            elif self._btn_plus_rect.contains(pos):
                self._zoom_by(0.5)
            else:
                self._drag(pos.x())

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._drag(event.position().x())

    def _zoom_by(self, delta: float) -> None:
        new_zoom = max(_ZOOM_MIN, min(_ZOOM_MAX, self._zoom + delta))
        if new_zoom != self._zoom:
            self._zoom = new_zoom
            self.update()
            self.zoom_changed.emit(new_zoom)

    def _drag(self, x: float) -> None:
        frac = self._x_to_frac(x)
        zoom = self._frac_to_zoom(frac)
        self._zoom = zoom
        self.update()
        self.zoom_changed.emit(zoom)

    # --- painting ---

    @staticmethod
    def _fmt_scale(den: float) -> str:
        if den >= 100_000_000:
            return f"1:{den / 100_000_000:.1f}亿"
        if den >= 100_000:
            return f"1:{den / 10_000:.0f}万"
        if den >= 1_000:
            return f"1:{den / 1_000:.0f}千"
        return f"1:{den:.0f}"

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 1. Glassmorphic Background Card
        p.setPen(QPen(QColor("#e2e8f0"), 1.0))
        p.setBrush(QBrush(QColor(255, 255, 255, 230)))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 8, 8)

        # 2. Interactive Buttons +/-
        btn_pen = QPen(QColor("#64748b"), 1.5)
        p.setPen(btn_pen)
        p.setBrush(QBrush(QColor("#f1f5f9")))
        p.drawRoundedRect(self._btn_minus_rect, 4, 4)
        p.drawRoundedRect(self._btn_plus_rect, 4, 4)

        # Draw minus '-'
        p.drawLine(15, 27, 27, 27)

        # Draw plus '+'
        p.drawLine(self.width() - 27, 27, self.width() - 15, 27)
        p.drawLine(self.width() - 21, 21, self.width() - 21, 33)

        x0, x1 = self._track_rect()
        w = x1 - x0
        mid_y = 27.0
        bar_h = 6.0
        bar_top = mid_y - bar_h / 2

        # 3. Slider Track Background
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#e2e8f0"))
        p.drawRoundedRect(int(x0), int(bar_top), int(w), int(bar_h), 3, 3)

        # 4. Zone fills: 相 (blue) | 亚相 (green) | 微相 (yellow)
        zone_colors = [QColor("#bfdbfe"), QColor("#bbf7d0"), QColor("#fde68a")]
        thr_x = [self._frac_to_x(self._zoom_to_frac(z))
                 for z in self._threshold_zooms]
        prev = x0
        for i, tx in enumerate(thr_x):
            p.setBrush(zone_colors[i])
            p.drawRoundedRect(int(prev), int(bar_top),
                              max(1, int(tx - prev)), int(bar_h), 3, 3)
            prev = tx
        p.setBrush(zone_colors[-1])
        p.drawRoundedRect(int(prev), int(bar_top),
                          max(1, int(x1 - prev)), int(bar_h), 3, 3)

        # 5. Zone Labels centered in colored segments + threshold division lines
        p.setPen(QPen(QColor("#475569"), 1.0))
        font = QFont("Sans Serif", 7)
        p.setFont(font)
        
        # Segment boundaries
        segments = [x0] + thr_x + [x1]
        level_labels = ["相", "亚相", "微相"]
        for i in range(3):
            left = segments[i]
            right = segments[i + 1]
            center_x = (left + right) / 2.0
            label = level_labels[i]
            tw = p.fontMetrics().horizontalAdvance(label)
            # Only draw the zone text if the segment is wide enough to contain it comfortably
            if (right - left) >= (tw + 6):
                p.drawText(QPointF(center_x - tw / 2, bar_top - 3), label)
                
        # Draw threshold division tick marks
        p.setPen(QPen(QColor("#475569"), 1.0))
        for tx in thr_x:
            p.drawLine(int(tx), int(bar_top - 2), int(tx), int(bar_top + bar_h + 2))

        # 6. Tick marks with 1:XXX labels
        p.setPen(QPen(QColor("#94a3b8"), 1))
        tick_font = QFont("Sans Serif", 6)
        p.setFont(tick_font)
        tick_y = bar_top + bar_h + 3
        for den, lbl in self._scale_ticks:
            frac = self._den_to_frac(den)
            tx = self._frac_to_x(frac)
            p.drawLine(int(tx), int(tick_y), int(tx), int(tick_y + 3))
            tw = p.fontMetrics().horizontalAdvance(lbl)
            p.drawText(QPointF(tx - tw / 2, tick_y + 11), lbl)

        # 7. Thumb
        thumb_frac = self._zoom_to_frac(self._zoom)
        thumb_x = self._frac_to_x(thumb_frac)
        p.setPen(QPen(QColor("#2563eb"), 2))
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QPointF(thumb_x, mid_y), 6, 6)

        # 8. Current 1:XXX label at thumb
        current_den = self._zoom_to_scale_den(self._zoom)
        scale_text = self._fmt_scale(current_den)
        p.setPen(QColor("#1e40af"))
        bold = QFont("Sans Serif", 8)
        bold.setBold(True)
        p.setFont(bold)
        tw = p.fontMetrics().horizontalAdvance(scale_text)
        lx = max(x0, min(thumb_x - tw / 2, x1 - tw))
        p.drawText(QPointF(lx, bar_top - 15), scale_text)
