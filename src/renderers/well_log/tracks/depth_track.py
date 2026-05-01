import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPainter, QPen, QColor
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
        self._plot_widget = pg.PlotWidget(background="w")
        pi = self._plot_widget.plotItem
        pi.getAxis("left").setPen(pg.mkPen("#4a5568"))
        pi.getAxis("left").setTextPen(pg.mkPen("#2d3748"))
        self._view_box = pi.vb

        pi.invertY(True)
        pi.setYRange(self._top_depth, self._bottom_depth)
        pi.setXRange(0, 1)
        pi.hideAxis("bottom")
        pi.showGrid(y=True, alpha=0.3)
        pi.setLabel("left", "Depth", units="m")
        # Prevent Qt FreeType crash on font merging
        left_axis = pi.getAxis("left")
        if hasattr(left_axis, 'label') and left_axis.label is not None:
            safe_font = QFont(left_axis.label.font())
            safe_font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
            left_axis.label.setFont(safe_font)
        return self._plot_widget

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
        """Render depth axis as vector for SVG/PDF export."""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # White background
        painter.fillRect(0, 0, width, height, QColor("white"))

        y_min = self._top_depth
        y_max = self._bottom_depth
        span = y_max - y_min
        if span <= 0:
            return

        # Draw depth ticks and labels
        font = QFont("Noto Sans CJK SC", 8)
        font.setStyleStrategy(QFont.StyleStrategy.NoFontMerging)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#2d3748"), 1))

        # Calculate tick interval based on height
        tick_interval = 10  # meters
        if height / (span / tick_interval) < 20:
            tick_interval = 50
        if height / (span / tick_interval) < 20:
            tick_interval = 100

        depth = int(y_min / tick_interval) * tick_interval
        while depth <= y_max:
            y = (depth - y_min) / span * height
            # Tick mark
            painter.drawLine(width - 8, int(y), width, int(y))
            # Label
            painter.drawText(
                0, int(y) - 8, width - 10, 16,
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{depth:.0f}",
            )
            depth += tick_interval

        # Border
        painter.setPen(QPen(QColor("#a0aec0"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(0, 0, width - 1, height - 1)
