import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QFileDialog

from src.renderers.seismic_renderer import SeismicRenderer


class SeismicPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        toolbar = QHBoxLayout()
        load_btn = QPushButton("加载 SEGY 文件")
        load_btn.clicked.connect(self._load_segy)
        demo_btn = QPushButton("加载示例数据")
        demo_btn.clicked.connect(self._load_demo)
        toolbar.addWidget(load_btn)
        toolbar.addWidget(demo_btn)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 3D viewer
        self.renderer = SeismicRenderer()
        layout.addWidget(self.renderer)

    def _load_segy(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 SEGY 文件", "", "SEGY Files (*.sgy *.segy)")
        if path:
            import segyio
            with segyio.open(path, "r", strict=False) as f:
                data = segyio.tools.cube(f)
            self.renderer.load_volume(data)

    def _load_demo(self):
        data = np.random.randn(50, 50, 50).astype(np.float32)
        self.renderer.load_volume(data)
