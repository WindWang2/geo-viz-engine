"""Variable-density heatmap profile renderer."""

from __future__ import annotations

import numpy as np
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from .colormap import ColormapManager


class ProfileVD(QWidget):
    """Variable-density heatmap profile renderer.

    Renders 2-D seismic data (n_samples x n_traces) as a QImage using
    a colour look-up table managed by :class:`ColormapManager`.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._image: QPixmap | None = None
        self._data: np.ndarray | None = None
        self._normalized: np.ndarray | None = None
        self._has_data = False
        self._colormap_name = "seismic"
        self._slice_info = None

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
        self.setMinimumSize(n_traces, n_samples)
        self.update()

    # Keep old method name as alias for backward compat
    _build_image = _build_image_from_normalized

    def paintEvent(self, event) -> None:  # noqa: N802
        if self._image is None:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self._image)
        painter.end()
