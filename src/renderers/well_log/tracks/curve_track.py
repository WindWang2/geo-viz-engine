import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QPolygonF
from PySide6.QtCore import QPointF
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
        self._plot_widget = pg.PlotWidget(background="w")
        pi = self._plot_widget.plotItem
        pi.getAxis("left").setPen(pg.mkPen("#4a5568"))
        pi.getAxis("left").setTextPen(pg.mkPen("#2d3748"))
        self._view_box = pi.vb

        pi.hideAxis("left")
        pi.hideAxis("bottom")
        pi.showGrid(x=True, y=True, alpha=0.3)
        pi.invertY(True)

        for curve in self._curves:
            self._add_curve(curve)

        if self._curves:
            c0 = self._curves[0]
            axis = pg.AxisItem(orientation="left")
            axis.setLabel(c0.name, units=c0.unit)
            # Prevent Qt FreeType crash on font merging for special chars (Ω, μ, etc.)
            if hasattr(axis, 'label') and axis.label is not None:
                safe_font = QFont(axis.label.font())
                safe_font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
                axis.label.setFont(safe_font)
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

    def preferred_width(self) -> int:
        return self._config.width

    def set_pixel_density(self, px_per_m: float):
        pass  # pyqtgraph ViewBox density is managed by linked axes

    def set_depth_range(self, top: float, bottom: float):
        if self._view_box:
            self._view_box.setYRange(top, bottom, padding=0)

    def sync_depth(self, top: float, bottom: float):
        self.set_depth_range(top, bottom)

    def export_vector(self, painter: QPainter, width: int, height: int):
        """Render curves as vector paths for SVG/PDF export."""
        from PySide6.QtCore import QRect
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # White background
        painter.fillRect(0, 0, width, height, QColor("white"))

        # Clip to bounds - curves must not extend outside
        painter.setClipRect(0, 0, width, height)

        # Draw grid
        grid_pen = QPen(QColor("#e5e7eb"), 0.5)
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for i in range(1, 10):
            x = int(width * i / 10)
            painter.drawLine(x, 0, x, height)
        for i in range(1, 10):
            y = int(height * i / 10)
            painter.drawLine(0, y, width, y)

        # Get depth range from viewbox
        y_min, y_max = self._view_box.viewRange()[1]

        for curve in self._curves:
            if not curve.depth or not curve.values:
                continue

            # Map curve data to pixel coordinates, clamped to bounds
            lo, hi = curve.display_range
            points = []
            for d, v in zip(curve.depth, curve.values):
                if d < y_min or d > y_max:
                    continue
                px = (v - lo) / (hi - lo) * width if hi != lo else 0
                py = (d - y_min) / (y_max - y_min) * height
                # Clamp to bounds
                px = max(0, min(width, px))
                py = max(0, min(height, py))
                points.append(QPointF(px, py))

            if len(points) < 2:
                continue

            # Draw curve as vector path
            pen = QPen(QColor(curve.color), 1.5)
            if curve.line_style.value == "dashed":
                pen.setStyle(Qt.PenStyle.DashLine)
            elif curve.line_style.value == "dotted":
                pen.setStyle(Qt.PenStyle.DotLine)
            painter.setPen(pen)
            painter.drawPolyline(QPolygonF(points))

        # Border (drawn after clipping so it's always visible)
        painter.setClipping(False)
        painter.setPen(QPen(QColor("#a0aec0"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, width - 1, height - 1)
