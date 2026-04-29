from PySide6.QtWidgets import QWidget, QHBoxLayout, QScrollArea, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from src.data.models import WellLogData
from src.renderers.well_log.curve_renderer import CurveRenderer
from src.renderers.well_log.lithology_renderer import LithologyRenderer
from src.renderers.well_log.facies_renderer import FaciesRenderer
from src.renderers.well_log.depth_renderer import DepthRenderer


CURVE_COLORS = ["#63b3ed", "#f6ad55", "#68d391", "#fc8181", "#d6bcfa", "#fbd38d"]


class ChartEngine(QWidget):
    def __init__(self, data: WellLogData):
        super().__init__()
        self.data = data
        self.chart_height = 800
        self._build()

    def _build(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Title
        title = QLabel(self.data.well_name)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #e2e8f0; padding: 8px;")

        # Depth track
        depth = DepthRenderer(self.data.top_depth, self.data.bottom_depth, height=self.chart_height)
        layout.addWidget(depth)

        # Curve tracks
        for i, curve in enumerate(self.data.curves):
            renderer = CurveRenderer(curve, color=CURVE_COLORS[i % len(CURVE_COLORS)])
            renderer.plot_widget.setFixedHeight(self.chart_height)
            layout.addWidget(renderer)

        # Lithology track
        if self.data.lithology:
            lith = LithologyRenderer(self.data.lithology, height=self.chart_height)
            layout.addWidget(lith)

        # Facies track
        if self.data.facies:
            fac = FaciesRenderer(self.data.facies, height=self.chart_height)
            layout.addWidget(fac)

        layout.addStretch()
        scroll.setWidget(container)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(title)
        outer.addWidget(scroll)
