import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class DepthRenderer(QWidget):
    def __init__(self, top_depth: float, bottom_depth: float, width: int = 60, height: int = 600):
        super().__init__()
        self.setFixedWidth(width)
        self.setFixedHeight(height)
        self._build(top_depth, bottom_depth)

    def _build(self, top_depth: float, bottom_depth: float):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("深度\n(m)")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setFixedHeight(40)
        header.setStyleSheet("background: #2d3748; color: #e2e8f0; font-size: 10px; font-weight: bold;")
        layout.addWidget(header)

        axis = pg.PlotWidget()
        axis.plotItem.invertY(True)
        axis.plotItem.setYRange(top_depth, bottom_depth)
        axis.plotItem.setXRange(0, 1)
        axis.plotItem.hideAxis("bottom")
        axis.plotItem.showGrid(y=True, alpha=0.3)
        axis.plotItem.setLabel("left", "Depth", units="m")
        layout.addWidget(axis)
