import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from src.data.models import CurveData


class CurveRenderer(QWidget):
    def __init__(self, curve: CurveData, width: int = 120, color: str = "#63b3ed"):
        super().__init__()
        self.curve_name = curve.name
        self.setFixedWidth(width)
        self._build(curve, color)

    def _build(self, curve: CurveData, color: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel(f"{curve.name}\n{curve.unit}")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(40)
        header.setStyleSheet("background: #2d3748; color: #e2e8f0; font-size: 10px; font-weight: bold;")
        layout.addWidget(header)

        # Plot
        self.plot_widget = pg.PlotWidget()
        self.plot_item = self.plot_widget.plotItem
        self.plot_item.plot(curve.values, curve.depth, pen=pg.mkPen(color, width=1.5))
        self.plot_item.invertY(True)
        self.plot_item.showGrid(x=True, alpha=0.3)
        self.plot_item.setLabel("left", "Depth", units="m")
        layout.addWidget(self.plot_widget)
