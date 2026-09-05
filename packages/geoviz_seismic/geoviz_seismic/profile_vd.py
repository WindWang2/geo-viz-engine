"""Variable-density heatmap profile renderer."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal, QTimer
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
    polyline_changed = Signal(list)  # list of (col_frac, row_frac) tuples

    # Signal emitted on mouse move: (h_seismic_value, v_seismic_value)
    cursor_moved = Signal(float, float)

    # Signal emitted on mouse move: formatted readout string
    amplitude_readout = Signal(str)

    # Signal emitted when user picks a horizon point: (inline, xline, time_ms)
    horizon_picked = Signal(float, float, float)

    # Signal emitted when user adds an annotation: (h_value, v_value, text)
    annotation_added = Signal(float, float, str)

    # Signal emitted when zoom/pan changes the viewport
    view_changed = Signal()

    # Signal emitted on Shift+wheel: delta (+1 or -1) for slice browsing
    slice_step_requested = Signal(int)

    # Signal for 4-panel cursor linkage: (h_value, v_value, slice_type)
    cursor_moved_3d = Signal(float, float, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QPixmap | None = None
        self._data: np.ndarray | None = None
        # Cached uint8 LUT-index array - the fused normalize+index result.
        # Reused on viewport (zoom/pan) changes; recomputed
        # only on new slice or clip-range change.
        self._indexed: np.ndarray | None = None
        self._rgba_override: np.ndarray | None = None
        # Long-lived contiguous buffer backing the QImage — avoids a fresh
        # allocation on every zoom/pan rebuild. Holds the uint8 index array
        # (Indexed8 path).
        self._rgba_buf: np.ndarray | None = None
        self._has_data = False
        self._colormap_name = "seismic"
        self._slice_info = None

        # Polyline drawing state
        self._drawing_enabled = False
        self._polyline_points: list[tuple[float, float]] = []  # (col_frac, row_frac)
        self._drawing_active = False

        # Cross-hair state (received from other panels)
        self._crosshair_h: float | None = None  # seismic coordinate
        self._crosshair_v: float | None = None

        # Horizon picking state
        self._picking_enabled = False
        self._picked_points: list[tuple[float, float]] = []  # (h_value, v_value) in seismic coords

        # Annotation state
        self._annotation_mode = False
        self._annotations: list = []  # list of SeismicAnnotation
        self._annotation_drag_idx: int | None = None

        # Display gain
        self._clip_pct = 99.0  # percentile clip (P1 to P_clip)
        # Display polarity (SEG normal by default): +1 native sign, -1 flipped.
        self._polarity = 1
        # Cached percentile clip range (lo, hi) — the expensive nanpercentile
        # scan (23ms on a 1.5M-pixel slice) was recomputed on every slice-swap
        # and every clip change, but the clip range is approximately stable
        # across sibling slices of the same volume. Invalidated on clip_pct
        # change and on volume reload. Keyed on (shape, filename, generation)
        # rather than shape alone — two different volumes with the same shape
        # must not share a cached P1/P99 (#119). The key is derived from the
        # current slice's SliceInfo when available; a missing SliceInfo falls
        # back to (shape,) so tests with bare render() calls remain simple.
        self._clip_range_cache: tuple[float, float] | None = None
        self._clip_range_key: tuple | None = None

        # Zoom/pan viewport state
        self._zoom_scale: float = 1.0
        self._view_h: tuple[float, float] = (0.0, 1.0)  # visible horizontal fraction
        self._view_v: tuple[float, float] = (0.0, 1.0)  # visible vertical fraction
        self._panning: bool = False
        self._pan_last: tuple[float, float] | None = None

        # Synthetic overlay state
        self._synthetic_overlay: dict | None = None

        # Cursor signal throttle (~60 fps)
        self._cursor_timer = QTimer(self)
        self._cursor_timer.setInterval(16)
        self._cursor_timer.setSingleShot(True)
        self._cursor_timer.timeout.connect(self._emit_cursor)
        self._pending_cursor: tuple[float, float, int, int] | None = None

        self.setMouseTracking(True)

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
        if self._has_data and self._indexed is not None:
            self._build_image_from_normalized()

    def set_polarity(self, normal: bool = True) -> None:
        """Flip the displayed amplitude sign (SEG normal ↔ reversed).

        Polarity is a DISPLAY convention only: the color mapping negates the
        clip range so positive lobes swap colour, but the stored data, the
        cursor amplitude readout and picked values stay in the survey's raw
        sign convention. Re-rendering reuses the cached percentile range —
        negation swaps (lo, hi); no rescan is needed.
        """
        polarity = 1 if normal else -1
        if polarity == self._polarity and self._has_data:
            return
        self._polarity = polarity
        if self._has_data:
            self._renormalize()

    def polarity_normal(self) -> bool:
        """True when the display uses the survey's native sign convention."""
        return self._polarity > 0

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

    def set_crosshair(self, h_value: float | None, v_value: float | None):
        """Set cross-hair position from another panel's cursor (seismic coords)."""
        self._crosshair_h = h_value
        self._crosshair_v = v_value
        self.update()

    def enable_picking(self, enabled: bool):
        """Enable/disable horizon picking mode."""
        self._picking_enabled = enabled

    def enable_annotation_mode(self, enabled: bool):
        """Toggle annotation placement mode."""
        self._annotation_mode = enabled

    def add_annotation(self, annotation):
        """Add an annotation object to this panel."""
        self._annotations.append(annotation)
        self.update()

    def clear_annotations(self):
        """Remove all annotations."""
        self._annotations.clear()
        self.update()

    def annotations(self) -> list:
        """Return a copy of current annotations."""
        return list(self._annotations)

    def add_picked_point(self, h_value: float, v_value: float):
        """Add an externally-picked point to this panel's display."""
        self._picked_points.append((h_value, v_value))
        self.update()

    def clear_picked_points(self):
        """Remove all picked points."""
        self._picked_points.clear()
        self.update()

    def set_clip_percentile(self, pct: float):
        """Set clip percentile (1-99) and re-normalize."""
        pct = max(1.0, min(99.0, pct))
        if abs(pct - self._clip_pct) < 0.01:
            return
        self._clip_pct = pct
        self._clip_range_cache = None  # invalidate; recompute on next _renormalize
        self._clip_range_key = None
        if self._has_data:
            self._renormalize()

    # ------------------------------------------------------------------
    # Synthetic overlay API
    # ------------------------------------------------------------------

    def set_synthetic_overlay(
        self,
        h_position: float,
        twt: np.ndarray,
        values: np.ndarray,
        label: str = "",
        color: str = "#ff0000",
    ):
        """Set a synthetic trace overlay at the given horizontal position.

        Args:
            h_position: Horizontal seismic coordinate (e.g. crossline number).
            twt: TWT values for each sample in the synthetic trace.
            values: Synthetic trace amplitude values.
            label: Display label for the well.
            color: Trace color (hex string).
        """
        self._synthetic_overlay = {
            "h_position": h_position,
            "twt": np.asarray(twt, dtype=np.float64),
            "values": np.asarray(values, dtype=np.float32),
            "label": label,
            "color": color,
        }
        self.update()

    def clear_synthetic_overlay(self):
        """Remove the synthetic trace overlay."""
        self._synthetic_overlay = None
        self.update()

    def _draw_synthetic_overlay(self, painter: QPainter, img_rect):
        """Draw the synthetic wiggle trace overlay on the seismic section."""
        if self._synthetic_overlay is None or self._slice_info is None:
            return
        ov = self._synthetic_overlay
        h_pos = ov["h_position"]
        twt = ov["twt"]
        values = ov["values"]
        color = QColor(ov["color"])

        # Find pixel x for the well position
        pos = self._seismic_to_pixel(h_pos, twt[0] if len(twt) > 0 else 0)
        if pos is None:
            return
        px_x = pos[0]
        if px_x < img_rect.left() or px_x > img_rect.right():
            return  # well outside viewport

        # Scale factor for wiggle width (pixels per unit amplitude)
        wiggle_width = img_rect.width() * 0.03
        amp_max = max(np.max(np.abs(values)), 1e-6)

        # Build polyline
        points = []
        for i in range(len(twt)):
            pixel = self._seismic_to_pixel(h_pos, twt[i])
            if pixel is None:
                continue
            px_y = pixel[1]
            px_offset = values[i] / amp_max * wiggle_width
            points.append((px_x + px_offset, px_y))

        if len(points) < 2:
            return

        # Draw wiggle
        pen = QPen(color, 1.5)
        pen.setCosmetic(True)
        painter.setPen(pen)
        from PySide6.QtGui import QPolygonF
        from PySide6.QtCore import QPointF
        polygon = QPolygonF([QPointF(x, y) for x, y in points])
        painter.drawPolyline(polygon)

        # Draw label
        if ov["label"]:
            painter.setPen(QPen(color, 1))
            painter.setFont(QFont("Monospace", 8))
            painter.drawText(int(px_x) - 20, img_rect.top() + 12, ov["label"])

    def clip_percentile(self) -> float:
        return self._clip_pct

    def _clip_cache_key(self, slice_info=None) -> tuple:
        """Build a cache key that distinguishes different volumes of the same shape.

        Two consecutive loads of different surveys can have identical shapes but
        wildly different amplitude distributions — reusing the previous P1/P99
        would mis-scale the new volume until the user drags the clip slider.
        When *slice_info* carries identifying axis values we fold those into
        the key; otherwise fall back to the bare shape for unit-test call sites
        that do not provide a SliceInfo (#119)."""
        si = slice_info if slice_info is not None else self._slice_info
        shape = tuple(self._data.shape) if self._data is not None else ()
        if si is None:
            return (shape,)
        # Axis arrays encode the concrete volume (start/step/count) through
        # SeismicVolumeMeta — the first and last tick plus the tick count
        # cheaply distinguish two volumes of the same shape without storing
        # the full array.
        try:
            h_vals = getattr(si, "axis_h_values", None)
            v_vals = getattr(si, "axis_v_values", None)
            h_key = (len(h_vals), h_vals[0] if h_vals else None, h_vals[-1] if h_vals else None) if h_vals is not None else ()
            v_key = (len(v_vals), v_vals[0] if v_vals else None, v_vals[-1] if v_vals else None) if v_vals is not None else ()
            return (shape, getattr(si, "slice_type", None), h_key, v_key)
        except Exception:
            return (shape,)

    def render(
        self,
        data: np.ndarray,
        colormap: str | None = None,
        slice_info=None,
    ) -> None:
        """Convert *data* to an RGBA image and schedule a repaint."""
        self._data = data.astype(np.float32, copy=False)
        self._slice_info = slice_info
        # Reuse clip range cache across sibling slices of the same volume;
        # invalidate when the volume identity changes (#119).
        key = self._clip_cache_key(slice_info)
        if self._clip_range_key != key:
            self._clip_range_cache = None
            self._clip_range_key = key
        self._rgba_override = None
        if colormap is not None:
            self._colormap_name = colormap
        self._has_data = True
        # Reset viewport on new data
        self._zoom_scale = 1.0
        self._view_h = (0.0, 1.0)
        self._view_v = (0.0, 1.0)
        self._renormalize()

    def render_rgba(
        self,
        rgba: np.ndarray,
        slice_info=None,
    ) -> None:
        """Render a pre-composed RGBA image directly (e.g. RGB attribute fusion).

        Args:
            rgba: (H, W, 4) uint8 RGBA array.
            slice_info: Optional slice metadata for axes.
        """
        assert rgba.ndim == 3 and rgba.shape[2] == 4, f"Expected (H,W,4), got {rgba.shape}"
        self._rgba_override = rgba.astype(np.uint8, copy=True)
        # Store synthetic float data for amplitude readout (not meaningful for RGB)
        self._data = np.zeros(rgba.shape[:2], dtype=np.float32)
        self._slice_info = slice_info
        self._has_data = True
        self._colormap_name = "__rgb__"
        self._zoom_scale = 1.0
        self._view_h = (0.0, 1.0)
        self._view_v = (0.0, 1.0)
        self._build_image_from_rgba()

    def indexed_snapshot(self) -> tuple[np.ndarray, tuple[float, float]] | None:
        """Return ``(indexed, clip_range)`` for the L2 texture cache, or ``None``.

        The uint8 LUT-index array is the display-ready slice texture content
        (1 byte/pixel, exactly what a GL_R8 upload or the Indexed8 QImage
        consume).  Together with the clip range it fully reproduces a later
        :meth:`render_indexed` hit; a following clip-percentile change
        invalidates via the normal ``_clip_range_cache`` key logic.
        """
        if not self._has_data or self._indexed is None or self._clip_range_cache is None:
            return None
        if self._rgba_override is not None:
            # RGB-fusion display: ``_indexed`` is stale from an earlier
            # amplitude render and must not be published as texture content.
            return None
        return self._indexed, self._clip_range_cache

    def render_indexed(
        self,
        data: np.ndarray,
        indexed: np.ndarray,
        clip_range: tuple[float, float],
        slice_info=None,
    ) -> None:
        """L2-hit fast path: render from a cached LUT-index texture.

        Equivalent to :meth:`render` minus the normalize pass — the
        percentile scan + index computation is the expensive part of a
        re-visit (tens of ms on million-sample slices); with the cached
        ``indexed`` array only the viewport sub-slice + colour-table QImage
        build runs (single-digit ms).
        """
        self._data = data.astype(np.float32, copy=False)
        self._indexed = np.asarray(indexed, dtype=np.uint8)
        self._rgba_override = None
        self._slice_info = slice_info
        self._has_data = True
        self._zoom_scale = 1.0
        self._view_h = (0.0, 1.0)
        self._view_v = (0.0, 1.0)
        # Adopt the cached clip range so a later percentile change recomputes
        # from raw data instead of inheriting a stale range.
        key = self._clip_cache_key(slice_info)
        self._clip_range_cache = (float(clip_range[0]), float(clip_range[1]))
        self._clip_range_key = key
        self._build_image_from_normalized()

    def _renormalize(self):
        """Compute the uint8 LUT-index array from the current slice.

        Delegates to ``ColormapManager.normalize_to_index`` with the cached
        percentile clip range. The clip range (lo, hi) is cached across
        sibling slices of the same volume (same shape + axis identity).

        On viewport (zoom/pan) changes, ``_build_image_from_normalized``
        re-slices the cached ``_indexed`` array without re-entering here.
        """
        if self._data is None:
            return
        dmin, dmax = np.nanmin(self._data), np.nanmax(self._data)
        if dmax == dmin:
            self._indexed = np.zeros(self._data.shape, dtype=np.uint8)
            self._build_image_from_normalized()
            return
        # Compute or reuse the cached clip range. The key includes axis
        # identity so consecutive loads of two different surveys with the same
        # shape do not inherit each other's P1/P99 (#119).
        key = self._clip_cache_key()
        if self._clip_range_cache is None or self._clip_range_key != key:
            pct = self._clip_pct
            lo = np.nanpercentile(self._data, 100.0 - pct)
            hi = np.nanpercentile(self._data, pct)
            if hi <= lo:
                hi = dmax
                lo = dmin
            self._clip_range_cache = (float(lo), float(hi))
            self._clip_range_key = key
        lo, hi = self._clip_range_cache
        # Display polarity: normalize the NEGATED slice through the same
        # cached range — unambiguous sign flip without touching the cached
        # range or the stored data (raw readouts keep the survey sign).
        data = self._data if self._polarity > 0 else -self._data
        self._indexed = ColormapManager.normalize_to_index(
            data, lut_size=256, value_range=(lo, hi)
        )
        self._build_image_from_normalized()

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _pixel_to_seismic(self, pos) -> tuple[float, float, int, int] | None:
        """Convert pixel position to (h_value, v_value, col_idx, row_idx) or None."""
        if not self._has_data or self._slice_info is None:
            return None
        img_rect = self._image_rect()
        vp_frac_x = (pos.x() - img_rect.left()) / max(img_rect.width(), 1)
        vp_frac_y = (pos.y() - img_rect.top()) / max(img_rect.height(), 1)
        vp_frac_x = max(0.0, min(1.0, vp_frac_x))
        vp_frac_y = max(0.0, min(1.0, vp_frac_y))

        info = self._slice_info
        n_cols = len(info.axis_h_values) if info.axis_h_values else 1
        n_rows = len(info.axis_v_values) if info.axis_v_values else 1

        # Convert viewport fraction to global fraction
        h_start, h_end = self._view_h
        v_start, v_end = self._view_v
        global_frac_x = h_start + vp_frac_x * (h_end - h_start)
        global_frac_y = v_start + vp_frac_y * (v_end - v_start)

        col_idx = max(0, min(int(global_frac_x * (n_cols - 1)), n_cols - 1))
        row_idx = max(0, min(int(global_frac_y * (n_rows - 1)), n_rows - 1))

        h_val = info.axis_h_values[col_idx] if info.axis_h_values else global_frac_x
        v_val = info.axis_v_values[row_idx] if info.axis_v_values else global_frac_y

        return h_val, v_val, col_idx, row_idx

    def _seismic_to_pixel(self, h_value: float, v_value: float) -> tuple[float, float] | None:
        """Convert seismic coordinates to pixel position within image rect."""
        info = self._slice_info
        if info is None or not self._has_data:
            return None
        img_rect = self._image_rect()

        h_vals = info.axis_h_values
        v_vals = info.axis_v_values
        if not h_vals or not v_vals:
            return None

        h_idx = _find_nearest_index(h_vals, h_value)
        v_idx = _find_nearest_index(v_vals, v_value)

        # Convert to global fraction, then to viewport fraction
        global_frac_x = h_idx / max(len(h_vals) - 1, 1)
        global_frac_y = v_idx / max(len(v_vals) - 1, 1)

        h_start, h_end = self._view_h
        v_start, v_end = self._view_v
        h_span = h_end - h_start
        v_span = v_end - v_start

        if h_span <= 0 or v_span <= 0:
            return None

        vp_frac_x = (global_frac_x - h_start) / h_span
        vp_frac_y = (global_frac_y - v_start) / v_span

        px = img_rect.left() + vp_frac_x * img_rect.width()
        py = img_rect.top() + vp_frac_y * img_rect.height()
        return px, py

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_image_from_normalized(self) -> None:
        """Map the visible portion of the indexed data through the colour LUT.

        Uses ``QImage.Format_Indexed8`` + a 256-entry colour table (cached by
        colormap name in ``ColormapManager.get_color_table``). The ``_indexed``
        array (uint8) is already the LUT index, so this is just a viewport
        sub-slice + contiguous copy - no arithmetic, no RGBA gather.
        Reused on zoom/pan without re-entering ``_renormalize``.
        """
        if self._rgba_override is not None:
            self._build_image_from_rgba()
            return
        if self._indexed is None:
            return

        cmap_name = self._colormap_name
        try:
            ColormapManager.get_colormap(cmap_name)
        except (ValueError, KeyError):
            cmap_name = "seismic"

        n_rows, n_cols = self._indexed.shape

        # Determine visible data range from viewport
        h_start, h_end = self._view_h
        v_start, v_end = self._view_v

        col_start = max(0, int(h_start * (n_cols - 1)))
        col_end = min(n_cols, int(h_end * (n_cols - 1)) + 1)
        row_start = max(0, int(v_start * (n_rows - 1)))
        row_end = min(n_rows, int(v_end * (n_rows - 1)) + 1)

        # Ensure at least 1 pixel
        col_end = max(col_start + 1, col_end)
        row_end = max(row_start + 1, row_end)

        sub = self._indexed[row_start:row_end, col_start:col_end]
        sub_samples, sub_traces = sub.shape

        # Hold the contiguous buffer alive for the QImage's lifetime.
        self._rgba_buf = np.ascontiguousarray(sub)
        img = QImage(
            self._rgba_buf.data,
            sub_traces,
            sub_samples,
            sub_traces,  # 1 byte per pixel (Indexed8)
            QImage.Format.Format_Indexed8,
        )
        img.setColorTable(ColormapManager.get_color_table(cmap_name))
        self._image = QPixmap.fromImage(img)
        self.update()

    def _build_image_from_rgba(self) -> None:
        """Render pre-composed RGBA data, respecting the current viewport."""
        if self._rgba_override is None:
            return
        n_rows, n_cols, _ = self._rgba_override.shape

        h_start, h_end = self._view_h
        v_start, v_end = self._view_v
        col_start = max(0, int(h_start * (n_cols - 1)))
        col_end = min(n_cols, int(h_end * (n_cols - 1)) + 1)
        row_start = max(0, int(v_start * (n_rows - 1)))
        row_end = min(n_rows, int(v_end * (n_rows - 1)) + 1)
        col_end = max(col_start + 1, col_end)
        row_end = max(row_start + 1, row_end)

        sub = self._rgba_override[row_start:row_end, col_start:col_end]
        sub_rows, sub_cols = sub.shape[0], sub.shape[1]
        # Same zero-copy pattern as _build_image_from_normalized: hold the
        # contiguous buffer alive for the QImage (avoids .tobytes() + .copy()).
        self._rgba_buf = np.ascontiguousarray(sub)
        img = QImage(
            self._rgba_buf.data,
            sub_cols,
            sub_rows,
            sub_cols * 4,
            QImage.Format.Format_RGBA8888,
        )
        self._image = QPixmap.fromImage(img)
        self.update()

    def _reset_zoom(self) -> None:
        """Reset viewport to show the full data extent."""
        self._zoom_scale = 1.0
        self._view_h = (0.0, 1.0)
        self._view_v = (0.0, 1.0)
        self._build_image_from_normalized()
        self.view_changed.emit()

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

        # 2.5 Draw synthetic overlay (between axes and crosshair)
        self._draw_synthetic_overlay(painter, img_rect)

        # 3. Draw cross-hair from linked panels
        self._draw_crosshair(painter, img_rect)

        # 4. Draw picked horizon points
        if self._picked_points:
            self._draw_picked_points(painter, img_rect)

        # 5. Draw polyline overlay if any
        if self._polyline_points:
            self._draw_polyline(painter, img_rect)

        # 6. Draw annotations
        if self._annotations:
            self._draw_annotations(painter, img_rect)

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
            painter.drawLine(int(x), int(y_top), int(x), int(y_top + tick_len))
            if info and info.axis_h_values:
                h_s, h_e = self._view_h
                idx = int((h_s + frac * (h_e - h_s)) * (len(info.axis_h_values) - 1))
                idx = max(0, min(idx, len(info.axis_h_values) - 1))
                val = info.axis_h_values[idx]
                text = f"{val:.0f}" if abs(val) > 1 else f"{val:.2f}"
            else:
                text = f"{frac:.1f}"
            painter.drawText(int(x - 18), int(y_top + tick_len + 12), text)

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
                v_s, v_e = self._view_v
                idx = int((v_s + frac * (v_e - v_s)) * (len(info.axis_v_values) - 1))
                idx = max(0, min(idx, len(info.axis_v_values) - 1))
                val = info.axis_v_values[idx]
                text = f"{val:.0f}" if abs(val) > 1 else f"{val:.2f}"
            else:
                text = f"{frac:.1f}"
            painter.drawText(int(x_left - 48), int(y + 4), text)

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

    def _draw_crosshair(self, painter: QPainter, img_rect):
        """Draw cross-hair lines from linked panels."""
        if self._crosshair_h is None and self._crosshair_v is None:
            return
        pen = QPen(QColor(255, 255, 0, 180), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)

        if self._crosshair_h is not None:
            pt = self._seismic_to_pixel(self._crosshair_h, 0)
            if pt:
                x = pt[0]
                if img_rect.left() <= x <= img_rect.right():
                    painter.drawLine(int(x), int(img_rect.top()), int(x), int(img_rect.bottom()))

        if self._crosshair_v is not None:
            pt = self._seismic_to_pixel(0, self._crosshair_v)
            if pt:
                y = pt[1]
                if img_rect.top() <= y <= img_rect.bottom():
                    painter.drawLine(int(img_rect.left()), int(y), int(img_rect.right()), int(y))

    def _draw_picked_points(self, painter: QPainter, img_rect):
        """Draw horizon pick points as orange circles."""
        painter.setPen(QPen(QColor(200, 100, 0), 1))
        painter.setBrush(QColor(255, 165, 0))
        for h_val, v_val in self._picked_points:
            pt = self._seismic_to_pixel(h_val, v_val)
            if pt:
                painter.drawEllipse(int(pt[0]) - 4, int(pt[1]) - 4, 8, 8)

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

        for i in range(len(pts_px) - 1):
            painter.drawLine(pts_px[i][0], pts_px[i][1], pts_px[i + 1][0], pts_px[i + 1][1])

        node_pen = QPen(QColor(255, 255, 0), 1)
        painter.setPen(node_pen)
        painter.setBrush(QColor(255, 0, 200))
        for px, py in pts_px:
            painter.drawEllipse(px - 4, py - 4, 8, 8)

    def _draw_annotations(self, painter: QPainter, img_rect):
        """Draw text annotations with background labels."""
        from PySide6.QtGui import QFontMetrics

        font = QFont("Sans", 10)
        painter.setFont(font)
        fm = QFontMetrics(font)

        for ann in self._annotations:
            pt = self._seismic_to_pixel(ann.h_value, ann.v_value)
            if pt is None:
                continue
            px, py = int(pt[0]), int(pt[1])

            color = QColor(ann.color)
            text_w = fm.horizontalAdvance(ann.text) + 8
            text_h = fm.height() + 4

            # Small marker dot at annotation point
            painter.setPen(QPen(color, 1))
            painter.setBrush(color)
            painter.drawEllipse(px - 3, py - 3, 6, 6)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Text positioned above-right of the point
            tx = px + 6
            ty = py - 8

            # Background rectangle
            bg_color = QColor(255, 255, 255, 210)
            painter.fillRect(tx - 2, ty - text_h + 3, text_w, text_h, bg_color)
            painter.setPen(QPen(color, 1))
            painter.drawRect(tx - 2, ty - text_h + 3, text_w, text_h)

            # Text
            painter.setPen(color)
            painter.drawText(tx + 2, ty, ann.text)

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def wheelEvent(self, event):
        if not self._has_data:
            super().wheelEvent(event)
            return

        # Shift+wheel: emit slice step for browsing
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = event.angleDelta().y()
            self.slice_step_requested.emit(1 if delta > 0 else -1)
            return

        img_rect = self._image_rect()
        mx = event.position().x()
        my = event.position().y()

        if not (img_rect.left() <= mx <= img_rect.right() and
                img_rect.top() <= my <= img_rect.bottom()):
            super().wheelEvent(event)
            return

        # Cursor position as viewport fraction
        vp_x = (mx - img_rect.left()) / max(img_rect.width(), 1)
        vp_y = (my - img_rect.top()) / max(img_rect.height(), 1)

        # Zoom factor: scroll up = zoom in, scroll down = zoom out
        delta = event.angleDelta().y()
        factor = 1.2 if delta > 0 else 1.0 / 1.2

        # Current viewport spans
        h_start, h_end = self._view_h
        v_start, v_end = self._view_v
        h_span = h_end - h_start
        v_span = v_end - v_start

        # Cursor global fraction (position in data space under the cursor)
        cursor_gx = h_start + vp_x * h_span
        cursor_gy = v_start + vp_y * v_span

        # New spans after zoom
        new_h_span = h_span / factor
        new_v_span = v_span / factor

        # Clamp zoom: data span from 1/32 (32x zoom) to 4x (0.25x zoom)
        min_span = 1.0 / 32.0
        max_span = 4.0
        new_h_span = max(min_span, min(max_span, new_h_span))
        new_v_span = max(min_span, min(max_span, new_v_span))

        # Recalculate viewport so cursor stays at the same data position
        new_h_start = cursor_gx - vp_x * new_h_span
        new_h_end = new_h_start + new_h_span
        new_v_start = cursor_gy - vp_y * new_v_span
        new_v_end = new_v_start + new_v_span

        # Clamp with 10% overscroll margin
        margin = 0.1
        if new_h_start < -margin:
            new_h_start = -margin
            new_h_end = new_h_start + new_h_span
        if new_h_end > 1.0 + margin:
            new_h_end = 1.0 + margin
            new_h_start = new_h_end - new_h_span
        if new_v_start < -margin:
            new_v_start = -margin
            new_v_end = new_v_start + new_v_span
        if new_v_end > 1.0 + margin:
            new_v_end = 1.0 + margin
            new_v_start = new_v_end - new_v_span

        self._view_h = (new_h_start, new_h_end)
        self._view_v = (new_v_start, new_v_end)
        avg_span = (new_h_span + new_v_span) / 2.0
        self._zoom_scale = 1.0 / avg_span if avg_span > 0 else 1.0

        self._build_image_from_normalized()
        self.view_changed.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._has_data:
            self._reset_zoom()
            return
        super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        if not self._has_data:
            super().mouseMoveEvent(event)
            return

        # Drag an existing annotation (annotation mode, left button held):
        # update its seismic coordinates to the cursor position.
        if self._annotation_drag_idx is not None:
            result = self._pixel_to_seismic(event.position())
            if result is not None:
                h_val, v_val, _, _ = result
                ann = self._annotations[self._annotation_drag_idx]
                ann.h_value = h_val
                ann.v_value = v_val
                self.update()
            return

        # Middle-button pan
        if self._panning and self._pan_last is not None:
            img_rect = self._image_rect()
            dx = event.position().x() - self._pan_last[0]
            dy = event.position().y() - self._pan_last[1]
            self._pan_last = (event.position().x(), event.position().y())

            h_start, h_end = self._view_h
            v_start, v_end = self._view_v
            h_span = h_end - h_start
            v_span = v_end - v_start

            frac_dx = -dx / max(img_rect.width(), 1) * h_span
            frac_dy = -dy / max(img_rect.height(), 1) * v_span

            new_h_start = h_start + frac_dx
            new_h_end = h_end + frac_dx
            new_v_start = v_start + frac_dy
            new_v_end = v_end + frac_dy

            margin = 0.1
            if new_h_start < -margin:
                shift = -margin - new_h_start
                new_h_start += shift
                new_h_end += shift
            if new_h_end > 1.0 + margin:
                shift = (1.0 + margin) - new_h_end
                new_h_start += shift
                new_h_end += shift
            if new_v_start < -margin:
                shift = -margin - new_v_start
                new_v_start += shift
                new_v_end += shift
            if new_v_end > 1.0 + margin:
                shift = (1.0 + margin) - new_v_end
                new_v_start += shift
                new_v_end += shift

            self._view_h = (new_h_start, new_h_end)
            self._view_v = (new_v_start, new_v_end)
            self._build_image_from_normalized()
            self.view_changed.emit()
            return

        result = self._pixel_to_seismic(event.position())
        if result is None:
            super().mouseMoveEvent(event)
            return

        h_val, v_val, col_idx, row_idx = result

        # Throttle cursor signals to ~60 fps
        self._pending_cursor = (h_val, v_val, col_idx, row_idx)
        if not self._cursor_timer.isActive():
            self._cursor_timer.start()

    def _emit_cursor(self):
        """Emit throttled cursor and readout signals."""
        if self._pending_cursor is None:
            return
        h_val, v_val, col_idx, row_idx = self._pending_cursor
        self._pending_cursor = None

        self.cursor_moved.emit(h_val, v_val)

        # Emit 3D-aware cursor signal for panel linkage
        info = self._slice_info
        if info and info.slice_type:
            self.cursor_moved_3d.emit(h_val, v_val, info.slice_type)

        if info and self._data is not None:
            n_samples, n_traces = self._data.shape
            if 0 <= row_idx < n_samples and 0 <= col_idx < n_traces:
                amp = float(self._data[row_idx, col_idx])
                h_label = info.axis_h_label or "H"
                v_label = info.axis_v_label or "V"
                self.amplitude_readout.emit(
                    f"{h_label}={h_val:.0f}  {v_label}={v_val:.1f}  Amp={amp:.4f}"
                )

    def mousePressEvent(self, event):
        if not self._has_data:
            super().mousePressEvent(event)
            return

        # Middle-button pan
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_last = (event.position().x(), event.position().y())
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        img_rect = self._image_rect()

        # Horizon picking mode (left click, no drawing active)
        if self._picking_enabled and event.button() == Qt.MouseButton.LeftButton:
            result = self._pixel_to_seismic(event.position())
            if result:
                h_val, v_val, _, _ = result
                info = self._slice_info
                if info:
                    self._picked_points.append((h_val, v_val))
                    self.horizon_picked.emit(h_val, v_val, 0)
                    self.update()
            return

        # Annotation mode
        if self._annotation_mode:
            result = self._pixel_to_seismic(event.position())
            if result is None:
                super().mousePressEvent(event)
                return
            h_val, v_val, _, _ = result

            if event.button() == Qt.MouseButton.LeftButton:
                # Check if clicking near existing annotation (for drag)
                near_idx = self._find_annotation_at(h_val, v_val)
                if near_idx is not None:
                    self._annotation_drag_idx = near_idx
                else:
                    from PySide6.QtWidgets import QInputDialog
                    from .models import SeismicAnnotation
                    text, ok = QInputDialog.getText(self, "标注", "输入标注文字:")
                    if ok and text.strip():
                        info = self._slice_info
                        ann = SeismicAnnotation(
                            text=text.strip(),
                            h_value=h_val,
                            v_value=v_val,
                            slice_type=info.slice_type if info else "inline",
                            slice_position=info.position if info else 0,
                        )
                        self._annotations.append(ann)
                        self.annotation_added.emit(h_val, v_val, text.strip())
                        self.update()
                return

            if event.button() == Qt.MouseButton.RightButton:
                near_idx = self._find_annotation_at(h_val, v_val)
                if near_idx is not None:
                    self._annotations.pop(near_idx)
                    self.update()
                return

        # Polyline drawing mode
        if not self._drawing_enabled:
            super().mousePressEvent(event)
            return

        if event.button() == Qt.MouseButton.RightButton:
            if len(self._polyline_points) >= 2:
                self._drawing_active = False
                self.polyline_changed.emit(list(self._polyline_points))
            return

        if event.button() == Qt.MouseButton.LeftButton:
            result = self._pixel_to_seismic(event.position())
            if result is not None:
                _, _, col_idx, row_idx = result
                n_cols = self._data.shape[1] if self._data is not None else 1
                n_rows = self._data.shape[0] if self._data is not None else 1
                col_frac = col_idx / max(n_cols - 1, 1)
                row_frac = row_idx / max(n_rows - 1, 1)
            else:
                pos = event.position()
                col_frac = (pos.x() - img_rect.left()) / max(img_rect.width(), 1)
                row_frac = (pos.y() - img_rect.top()) / max(img_rect.height(), 1)

            col_frac = max(0.0, min(1.0, col_frac))
            row_frac = max(0.0, min(1.0, row_frac))

            if not self._drawing_active:
                self._polyline_points.clear()
                self._drawing_active = True

            self._polyline_points.append((col_frac, row_frac))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self._pan_last = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if self._annotation_drag_idx is not None:
            self._annotation_drag_idx = None
            return
        super().mouseReleaseEvent(event)

    def _find_annotation_at(self, h_val: float, v_val: float) -> int | None:
        """Find index of annotation near given seismic coordinates, or None."""
        info = self._slice_info
        if info is None or not info.axis_h_values or not info.axis_v_values:
            return None
        h_range = max(info.axis_h_values) - min(info.axis_h_values)
        v_range = max(info.axis_v_values) - min(info.axis_v_values)
        threshold = 0.03
        for i, ann in enumerate(self._annotations):
            dh = abs(ann.h_value - h_val) / max(h_range, 1e-6)
            dv = abs(ann.v_value - v_val) / max(v_range, 1e-6)
            if dh < threshold and dv < threshold:
                return i
        return None


def _find_nearest_index(sorted_values: list, target: float) -> int:
    """Binary search for nearest index in an ascending or descending sorted list."""
    n = len(sorted_values)
    if n <= 1:
        return 0
    descending = sorted_values[0] > sorted_values[-1]
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if descending:
            if sorted_values[mid] > target:
                lo = mid + 1
            else:
                hi = mid
        else:
            if sorted_values[mid] < target:
                lo = mid + 1
            else:
                hi = mid
    # Check if neighbor is closer
    candidates = [lo]
    if lo > 0:
        candidates.append(lo - 1)
    if lo < n - 1:
        candidates.append(lo + 1)
    best_idx = lo
    best_diff = abs(sorted_values[lo] - target)
    for idx in candidates:
        diff = abs(sorted_values[idx] - target)
        if diff < best_diff:
            best_diff = diff
            best_idx = idx
    return best_idx
