"""Collapsible control panel for Well-Seismic Tie Workspace."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QComboBox, QSlider, QLabel, QPushButton,
)

from geoviz_well_tie.wavelet_engine import generate_ricker_wavelet, generate_ormsby_wavelet

class WellTieSidebar(QWidget):
    """Control panel for wavelet parameters, auto-tie, and quality metrics."""

    wavelet_changed = Signal(object)
    auto_tie_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(280)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        # Wavelet parameters group
        wl_group = QGroupBox("子波控制 (Wavelet)")
        wl_layout = QFormLayout(wl_group)

        self._type_combo = QComboBox()
        self._type_combo.addItems(["Ricker", "Ormsby"])
        self._type_combo.currentTextChanged.connect(self._on_wavelet_changed)
        wl_layout.addRow("类型:", self._type_combo)

        self._freq_slider = QSlider(Qt.Orientation.Horizontal)
        self._freq_slider.setRange(5, 80)
        self._freq_slider.setValue(30)
        self._freq_label = QLabel("30 Hz")
        self._freq_slider.valueChanged.connect(self._on_freq_slider_changed)

        freq_row = QHBoxLayout()
        freq_row.addWidget(self._freq_slider)
        freq_row.addWidget(self._freq_label)
        wl_layout.addRow("主频:", freq_row)

        layout.addWidget(wl_group)

        # Auto-Tie Group
        tie_group = QGroupBox("自动井震标定 (Auto-Tie)")
        tie_layout = QVBoxLayout(tie_group)

        self._auto_tie_btn = QPushButton("⚡ 执行一键自动标定 (Auto-Tie)")
        self._auto_tie_btn.setStyleSheet(
            "QPushButton { background: #1f66d4; color: white; font-weight: bold; padding: 6px; border-radius: 6px; }"
            "QPushButton:hover { background: #1852b0; }"
        )
        self._auto_tie_btn.clicked.connect(lambda: self.auto_tie_clicked.emit())
        tie_layout.addWidget(self._auto_tie_btn)

        self._score_label = QLabel("相关系数 R: 0.85\n时移量 Lag: 0 ms")
        self._score_label.setStyleSheet("font-size: 12px; color: #586878; font-weight: bold;")
        tie_layout.addWidget(self._score_label)

        layout.addWidget(tie_group)
        layout.addStretch()

    def _on_freq_slider_changed(self, val: int):
        self._freq_label.setText(f"{val} Hz")
        self._on_wavelet_changed()

    def _on_wavelet_changed(self):
        w_type = self._type_combo.currentText()
        freq = self._freq_slider.value()

        if w_type == "Ricker":
            _, w = generate_ricker_wavelet(freq=float(freq))
        else:
            _, w = generate_ormsby_wavelet(f1=5, f2=10, f3=float(freq), f4=float(freq)+10)

        self.wavelet_changed.emit(w)

    def set_quality_metrics(self, r_score: float, lag_ms: float):
        self._score_label.setText(f"相关系数 R: {r_score:.3f}\n时移量 Lag: {lag_ms:.1f} ms")
