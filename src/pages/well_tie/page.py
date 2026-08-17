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
        self._last_tie = None

    def _load_sample_data(self):
        n = 200
        depths = np.linspace(1000, 3000, n)
        twt = np.linspace(800, 2400, n)
        sonic = 250 + 50 * np.sin(np.linspace(0, 20, n))
        density = 2.2 + 0.3 * np.cos(np.linspace(0, 20, n))
        seismic = np.random.randn(n)

        self._canvas.set_tie_data(depths, twt, sonic, density, seismic)

    def _on_auto_tie(self):
        from geoviz_well_tie.auto_tie import correlate_synthetic_to_trace

        syn = self._canvas._synthetic
        seis = self._canvas._seismic
        if syn is None or seis is None:
            self._sidebar.set_quality_metrics(None, None)
            self._last_tie = None
            return
        shift, r_score = correlate_synthetic_to_trace(syn, seis)
        twt = self._canvas._twt
        if twt is not None and len(twt) > 1:
            dt_ms = float(twt[1] - twt[0])
        else:
            dt_ms = 0.0
        lag_ms = float(shift) * dt_ms
        self._last_tie = {
            "r_score": float(r_score),
            "lag_ms": lag_ms,
            "wavelet": self._sidebar.wavelet_description(),
        }
        self._sidebar.set_quality_metrics(r_score, lag_ms)

    def _on_export_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出井震标定报告", "Well_Seismic_Tie_Report.pdf", "PDF Documents (*.pdf);;SVG Vector (*.svg)")
        if path:
            metrics = self._last_tie or {}
            export_well_tie_pdf(
                path,
                wavelet=metrics.get("wavelet"),
                r_score=metrics.get("r_score"),
                lag_ms=metrics.get("lag_ms"),
            )
