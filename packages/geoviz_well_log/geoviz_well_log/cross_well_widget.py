from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
)

from .renderer.canvas import WellLogCanvas
from .renderer.depth_ruler import DepthRuler
from .connection_overlay import ConnectionOverlay
from .painter_sync_manager import QPainterSyncManager


class CrossWellWidget(QWidget):
    """Multi-well cross-section view using QPainter-rendered WellLogCanvas widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvases: list[WellLogCanvas] = []
        self._well_names: list[str] = []
        self._sync_manager = QPainterSyncManager(self)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Scroll area with horizontal layout
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(150)
        self._container_layout.addStretch()
        self._scroll.setWidget(self._container)
        main_layout.addWidget(self._scroll)

        # Connection overlay on container
        self._overlay = ConnectionOverlay(self._container)

        # Depth ruler on right edge of scroll viewport
        self._depth_ruler = DepthRuler(self._scroll.viewport())

    @property
    def canvas_count(self) -> int:
        return len(self._canvases)

    def add_canvas(self, canvas: WellLogCanvas, well_name: str):
        """Add a well canvas to the cross-well view."""
        self._canvases.append(canvas)
        self._well_names.append(well_name)
        # Insert before the stretch
        idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(idx, canvas)
        self._sync_manager.add_canvas(canvas)
        canvas.setMouseTracking(True)
        self._update_overlay_geometry()

    def remove_canvas(self, canvas: WellLogCanvas):
        """Remove a well canvas from the cross-well view."""
        if canvas in self._canvases:
            idx = self._canvases.index(canvas)
            self._sync_manager.remove_canvas(canvas)
            self._container_layout.removeWidget(canvas)
            canvas.setParent(None)
            self._canvases.pop(idx)
            self._well_names.pop(idx)
            self._update_overlay_geometry()

    def clear_all(self):
        """Remove all wells and clear state."""
        for canvas in self._canvases[:]:
            self.remove_canvas(canvas)
        self._overlay.set_links([])

    def _update_overlay_geometry(self):
        """Update overlay geometry to cover the container."""
        if self._overlay:
            self._overlay.setGeometry(self._container.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_geometry()
        # Position depth ruler
        vp = self._scroll.viewport().rect()
        ruler_w = self._depth_ruler.width()
        self._depth_ruler.setGeometry(vp.width() - ruler_w, 0, ruler_w, vp.height())
