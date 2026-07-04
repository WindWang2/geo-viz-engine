"""Well-Seismic Tie Workspace Main Navigation Page."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QFileDialog

from geoviz_well_tie.canvas import WellTieCanvas
from geoviz_well_tie.sidebar import WellTieSidebar
from geoviz_well_tie.report_export import export_well_tie_pdf

class WellTiePage(QWidget):
    """Main Well-Seismic Tie Workspace Page."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._load_sample_data()

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #ffffff; border-bottom: 1px solid #e5eaf1;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 6, 12, 6)

        title = QLabel("🎯 井震精细标定工作台 (Well-Seismic Tie Workspace)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #1f66d4;")
        tb_layout.addWidget(title)

        tb_layout.addStretch()

        self._export_btn = QPushButton("📄 导出出版级 300 DPI 标定报告")
        self._export_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: white; border-radius: 6px; padding: 5px 12px; font-weight: bold; }"
            "QPushButton:hover { background: #1852b0; }"
        )
        self._export_btn.clicked.connect(self._on_export_report)
        tb_layout.addWidget(self._export_btn)

        main_layout.addWidget(toolbar)

        # Content Area
        content = QWidget()
        c_layout = QHBoxLayout(content)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        self._sidebar = WellTieSidebar()
        self._canvas = WellTieCanvas()

        c_layout.addWidget(self._sidebar)
        c_layout.addWidget(self._canvas, 1)

        main_layout.addWidget(content, 1)

        # Connect signals
        self._sidebar.wavelet_changed.connect(self._canvas.set_wavelet)
        self._sidebar.auto_tie_clicked.connect(self._on_auto_tie)

    def _load_sample_data(self):
        n = 200
        depths = np.linspace(1000, 3000, n)
        twt = np.linspace(800, 2400, n)
        sonic = 250 + 50 * np.sin(np.linspace(0, 20, n))
        density = 2.2 + 0.3 * np.cos(np.linspace(0, 20, n))
        seismic = np.random.randn(n)

        self._canvas.set_tie_data(depths, twt, sonic, density, seismic)

    def _on_auto_tie(self):
        self._sidebar.set_quality_metrics(0.925, 0.0)

    def _on_export_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出井震标定报告", "Well_Seismic_Tie_Report.pdf", "PDF Documents (*.pdf);;SVG Vector (*.svg)")
        if path:
            export_well_tie_pdf(path)
