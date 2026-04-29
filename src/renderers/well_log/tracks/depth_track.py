import pyqtgraph as pg
from PySide6.QtWidgets import QWidget

from src.renderers.well_log.config import TrackConfig
from src.renderers.well_log.tracks.base import TrackWidget


class DepthTrack(TrackWidget):
    def __init__(self, config: TrackConfig, top_depth: float, bottom_depth: float,
                 header_height: int = 40, parent=None):
        self._top_depth = top_depth
        self._bottom_depth = bottom_depth
        self._plot_widget: pg.PlotWidget | None = None
        self._view_box: pg.ViewBox | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._plot_widget = pg.PlotWidget()
        pi = self._plot_widget.plotItem
        self._view_box = pi.vb

        pi.invertY(True)
        pi.setYRange(self._top_depth, self._bottom_depth)
        pi.setXRange(0, 1)
        pi.hideAxis("bottom")
        pi.showGrid(y=True, alpha=0.3)
        pi.setLabel("left", "Depth", units="m")
        return self._plot_widget

    @property
    def view_box(self) -> pg.ViewBox:
        return self._view_box

    def set_depth_range(self, top: float, bottom: float):
        if self._view_box:
            self._view_box.setYRange(top, bottom, padding=0)
