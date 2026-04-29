import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.data.models import CurveData
from src.renderers.well_log.config import CurveTrackConfig
from src.renderers.well_log.tracks.base import TrackWidget


class CurveTrack(TrackWidget):
    def __init__(self, config: CurveTrackConfig, curves: list[CurveData],
                 header_height: int = 40, parent=None):
        self._curves = curves
        self._plot_widget: pg.PlotWidget | None = None
        self._view_box: pg.ViewBox | None = None
        super().__init__(config, header_height, parent)

    def _create_content(self) -> QWidget:
        self._plot_widget = pg.PlotWidget()
        pi = self._plot_widget.plotItem
        self._view_box = pi.vb

        pi.hideAxis("left")
        pi.hideAxis("bottom")
        pi.showGrid(x=True, y=True, alpha=0.15)
        pi.invertY(True)

        for curve in self._curves:
            self._add_curve(curve)

        if self._curves:
            c0 = self._curves[0]
            axis = pg.AxisItem(orientation="left")
            axis.setLabel(c0.name, units=c0.unit)
            pi.setAxisItems({"left": axis})

        return self._plot_widget

    def _add_curve(self, curve: CurveData):
        pen = pg.mkPen(curve.color, width=1.5)
        if curve.line_style == "dashed":
            pen.setStyle(Qt.PenStyle.DashLine)
        elif curve.line_style == "dotted":
            pen.setStyle(Qt.PenStyle.DotLine)

        self._plot_widget.plotItem.plot(
            curve.values, curve.depth, pen=pen, name=curve.name,
        )
        lo, hi = curve.display_range
        self._plot_widget.plotItem.setXRange(lo, hi, padding=0)

    @property
    def view_box(self) -> pg.ViewBox:
        return self._view_box

    def set_depth_range(self, top: float, bottom: float):
        if self._view_box:
            self._view_box.setYRange(top, bottom, padding=0)
