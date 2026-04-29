from PySide6.QtWidgets import QWidget, QHBoxLayout
from src.data.models import WellLogData
from src.renderers.well_log.curve_renderer import CurveRenderer


class ChartEngine(QWidget):
    def __init__(self, data: WellLogData):
        super().__init__()
        self.data = data
        self._build()

    def _build(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        colors = ["#63b3ed", "#f6ad55", "#68d391", "#fc8181", "#d6bcfa", "#fbd38d"]
        for i, curve in enumerate(self.data.curves):
            renderer = CurveRenderer(curve, color=colors[i % len(colors)])
            layout.addWidget(renderer)
