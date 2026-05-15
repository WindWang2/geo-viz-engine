"""Variable-density heatmap profile renderer."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap, QFont, QPen, QColor
from PySide6.QtWidgets import QWidget

from .colormap import ColormapManager

# Axis margin constants (pixels)
_MARGIN_LEFT = 55
_MARGIN_BOTTOM = 28
_MARGIN_TOP = 5
_MARGIN_RIGHT = 5


class ProfileVD(QWidget):
    """Variable-density heatmap profile renderer with coordinate axes.

    Renders 2-D seismic data (n_samples x n_traces) as a QImage using
    a colour look-up table managed by :class:`ColormapManager`.
    """

    # Signal emitted when user draws a polyline on this profile
    polyline_changed = Signal(list)  # list of (row_frac, col_frac) tuples

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QPixmap | None = None
        self._data: np.ndarray | None = None
        self._normalized: np.ndarray | None = None
        self._has_data = False
        self._colormap_name = "seismic"
        self._slice_info = None

        # Polyline drawing state
        self._drawing_enabled = False
        self._polyline_points: list[tuple[float, float]] = []  # (col_frac, row_frac)
        self._drawing_active = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def has_data(self) -> bool:
        """Return ``True`` after :meth:`render` has been called."""
        return self._has_data

    def current_colormap(self) -> str:
        """Return the name of the currently active colormap."""
        return self._colormap_name

    def set_colormap(self, name: str) -> None:
        """Switch the colormap and re-render if data is present."""
        if name == self._colormap_name and self._has_data:
            return
        self._colormap_name = name
        if self._has_data and self._normalized is not None:
            self._build_image_from_normalized()

    def slice_info(self):
        """Return the :class:`SliceInfo` passed to the last render, or ``None``."""
        return self._slice_info

    def enable_polyline_drawing(self, enabled: bool = True):
        """Enable/disable polyline drawing on this profile."""
        self._drawing_enabled = enabled
        if not enabled:
            self._polyline_points.clear()
            self._drawing_active = False
            self.update()

    def clear_polyline(self):
        """Remove any drawn polyline."""
        self._polyline_points.clear()
        self._drawing_active = False
        self.update()

    def render(
        self,
        data: np.ndarray,
        colormap: str | None = None,
        slice_info=None,
    ) -> None:
        """Convert *data* to an RGBA image and schedule a repaint.

        Parameters
        ----------
        data:
            2-D ``float32`` array of shape ``(n_samples, n_traces)``.
        colormap:
            Name of a colormap registered in :class:`ColormapManager`.
            When ``None`` the current colormap is used.
        slice_info:
            Optional :class:`SliceInfo` metadata stored for later queries.
        """
        self._data = data.astype(np.float32, copy=False)
        if colormap is not None:
            self._colormap_name = colormap
        self._slice_info = slice_info
        self._has_data = True
        # Cache normalized data for fast colormap switches
        dmin, dmax = np.nanmin(self._data), np.nanmax(self._data)
        if dmax == dmin:
            self._normalized = np.zeros_like(self._data, dtype=np.float32)
        else:
            self._normalized = (self._data - dmin) / (dmax - dmin)
        self._build_image_from_normalized()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_image_from_normalized(self) -> None:
        """Map cached normalized data through the colour LUT into a QPixmap."""
        lut = ColormapManager.get_colormap(self._colormap_name)
        indices = (self._normalized * (len(lut) - 1)).astype(np.int32)
        indices = np.clip(indices, 0, len(lut) - 1)
        rgba = lut[indices]

        n_samples, n_traces, _ = rgba.shape
        img = QImage(
            rgba.tobytes(),
            n_traces,
            n_samples,
            n_traces * 4,
            QImage.Format.Format_RGBA8888,
        )
        self._image = QPixmap.fromImage(img.copy())
        self.update()

    # Keep old method name as alias for backward compat
    _build_image = _build_image_from_normalized

    def _image_rect(self):
        """Return the QRectF where the seismic image is drawn (inside axis margins)."""
        r = self.rect()
        return r.adjusted(_MARGIN_LEFT, _MARGIN_TOP, -_MARGIN_RIGHT, -_MARGIN_BOTTOM)

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._image is None:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        img_rect = self._image_rect()

        # 1. Draw the heatmap image inside the axis area
        painter.drawPixmap(img_rect, self._image)

        # 2. Draw coordinate axes
        self._draw_axes(painter, img_rect)

        # 3. Draw polyline overlay if any
        if self._polyline_points:
            self._draw_polyline(painter, img_rect)

        painter.end()

    def _draw_axes(self, painter: QPainter, img_rect):
        """Draw tick marks and labels around the image rectangle."""
        info = self._slice_info
        tick_font = QFont("Sans", 8)
        label_font = QFont("Sans", 9)
        label_font.setBold(True)
        tick_pen = QPen(QColor(80, 80, 80))
        tick_pen.setWidthF(1.0)

        n_ticks = 5
        tick_len = 4

        # --- Bottom axis (horizontal) ---
        painter.setPen(tick_pen)
        painter.setFont(tick_font)
        for i in range(n_ticks + 1):
            frac = i / n_ticks
            x = img_rect.left() + frac * img_rect.width()
            y_top = img_rect.bottom()
            # Tick line
            painter.drawLine(int(x), int(y_top), int(x), int(y_top + tick_len))
            # Tick label
            if info and info.axis_h_values:
                idx = int(frac * (len(info.axis_h_values) - 1))
                idx = min(idx, len(info.axis_h_values) - 1)
                val = info.axis_h_values[idx]
                text = f"{val:.0f}" if abs(val) > 1 else f"{val:.2f}"
            else:
                text = f"{frac:.1f}"
            painter.drawText(int(x - 18), int(y_top + tick_len + 12), text)

        # Bottom axis label
        if info and info.axis_h_label:
            painter.setFont(label_font)
            painter.drawText(
                int(img_rect.center().x() - 30),
                int(img_rect.bottom() + 24),
                info.axis_h_label,
            )

        # --- Left axis (vertical) ---
        painter.setFont(tick_font)
        for i in range(n_ticks + 1):
            frac = i / n_ticks
            y = img_rect.top() + frac * img_rect.height()
            x_left = img_rect.left()
            painter.drawLine(int(x_left - tick_len), int(y), int(x_left), int(y))
            if info and info.axis_v_values:
                idx = int(frac * (len(info.axis_v_values) - 1))
                idx = min(idx, len(info.axis_v_values) - 1)
                val = info.axis_v_values[idx]
                text = f"{val:.0f}" if abs(val) > 1 else f"{val:.2f}"
            else:
                text = f"{frac:.1f}"
            painter.drawText(int(x_left - 48), int(y + 4), text)

        # Left axis label (rotated)
        if info and info.axis_v_label:
            painter.setFont(label_font)
            painter.save()
            painter.translate(12, int(img_rect.center().y() + 30))
            painter.rotate(-90)
            painter.drawText(0, 0, info.axis_v_label)
            painter.restore()

        # Draw border around image area
        border_pen = QPen(QColor(180, 180, 180))
        border_pen.setWidthF(0.5)
        painter.setPen(border_pen)
        painter.drawRect(img_rect)

    def _draw_polyline(self, painter: QPainter, img_rect):
        """Draw the user's polyline path overlaid on the image."""
        if len(self._polyline_points) < 1:
            return

        pen = QPen(QColor(255, 0, 200), 2.5)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)

        pts_px = []
        for col_frac, row_frac in self._polyline_points:
            px = img_rect.left() + col_frac * img_rect.width()
            py = img_rect.top() + row_frac * img_rect.height()
            pts_px.append((int(px), int(py)))

        # Draw lines
        for i in range(len(pts_px) - 1):
            painter.drawLine(pts_px[i][0], pts_px[i][1], pts_px[i + 1][0], pts_px[i + 1][1])

        # Draw nodes
        node_pen = QPen(QColor(255, 255, 0), 1)
        painter.setPen(node_pen)
        painter.setBrush(QColor(255, 0, 200))
        for px, py in pts_px:
            painter.drawEllipse(px - 4, py - 4, 8, 8)

    # ------------------------------------------------------------------
    # Mouse interaction for polyline drawing
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if not self._drawing_enabled or not self._has_data:
            super().mousePressEvent(event)
            return

        img_rect = self._image_rect()

        if event.button() == Qt.MouseButton.RightButton:
            # Right click = finish drawing
            if len(self._polyline_points) >= 2:
                self._drawing_active = False
                self.polyline_changed.emit(list(self._polyline_points))
            return

        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position()
            # Convert pixel to fractional position within image rect
            col_frac = (pos.x() - img_rect.left()) / max(img_rect.width(), 1)
            row_frac = (pos.y() - img_rect.top()) / max(img_rect.height(), 1)

            # Clamp to [0, 1]
            col_frac = max(0.0, min(1.0, col_frac))
            row_frac = max(0.0, min(1.0, row_frac))

            if not self._drawing_active:
                self._polyline_points.clear()
                self._drawing_active = True

            self._polyline_points.append((col_frac, row_frac))
            self.update()

