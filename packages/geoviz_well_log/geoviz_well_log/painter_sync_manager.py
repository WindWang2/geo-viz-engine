from __future__ import annotations

from PySide6.QtCore import QObject

from .renderer.canvas import WellLogCanvas


class QPainterSyncManager(QObject):
    """Synchronizes depth range across multiple WellLogCanvas widgets via Qt signals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvases: list[WellLogCanvas] = []
        self._is_syncing = False

    def add_canvas(self, canvas: WellLogCanvas):
        if canvas not in self._canvases:
            self._canvases.append(canvas)
            canvas.depth_range_changed.connect(self._on_range_changed)

    def remove_canvas(self, canvas: WellLogCanvas):
        if canvas in self._canvases:
            canvas.depth_range_changed.disconnect(self._on_range_changed)
            self._canvases.remove(canvas)

    def _on_range_changed(self, top: float, bottom: float):
        if self._is_syncing:
            return
        self._is_syncing = True
        try:
            for canvas in self._canvases:
                canvas.blockSignals(True)
                canvas.set_depth_range(top, bottom)
                canvas.blockSignals(False)
        finally:
            self._is_syncing = False
