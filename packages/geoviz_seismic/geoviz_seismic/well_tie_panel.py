"""Well-seismic tie panel: wavelet controls, auto-tie, and calibration export."""
from __future__ import annotations

import logging
import csv
import io

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QSlider, QLabel, QPushButton, QGroupBox,
    QFileDialog,
)
from PySide6.QtCore import Signal

logger = logging.getLogger(__name__)

_STYLE_BTN = (
    "QPushButton { background: #edf2f7; border: 1px solid #cbd5e1; "
    "border-radius: 4px; padding: 4px 10px; font-size: 12px; }"
    "QPushButton:hover { background: #e2e8f0; }"
)
_STYLE_ACCENT = (
    "QPushButton { background: #ebf8ff; border: 1px solid #90cdf4; "
    "border-radius: 4px; padding: 4px 10px; font-size: 12px; color: #2b6cb0; }"
    "QPushButton:hover { background: #bee3f8; }"
)
_STYLE_GROUP = "QGroupBox { font-weight: bold; font-size: 12px; }"


class WellTiePanel(QWidget):
    """Persistent panel for well-seismic tie workflow.

    Contains wavelet selection + parameter sliders, auto-tie button,
    correlation readout, and export controls.

    Signals:
        synthetic_changed: Emitted when synthetic trace is regenerated.
            Payload: (twt_array, values_array) as numpy arrays.
    """

    synthetic_changed = Signal(object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._calibration = None
        self._depths = None
        self._sonic = None
        self._density = None
        self._synthetic = None
        self._synthetic_twt = None
        self._shift_samples = None
        self._correlation_coeff = None

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)

        # --- Wavelet controls ---
        wavelet_group = QGroupBox("子波参数")
        wavelet_group.setStyleSheet(_STYLE_GROUP)
        wl_layout = QFormLayout(wavelet_group)

        self._wavelet_combo = QComboBox()
        self._wavelet_combo.addItems(["Ricker", "Ormsby"])
        self._wavelet_combo.currentTextChanged.connect(self._on_wavelet_type_changed)
        wl_layout.addRow("类型:", self._wavelet_combo)

        # Ricker: peak frequency
        self._peak_freq_slider = QSlider(Qt.Orientation.Horizontal)
        self._peak_freq_slider.setRange(5, 80)
        self._peak_freq_slider.setValue(25)
        self._peak_freq_label = QLabel("25 Hz")
        self._peak_freq_slider.valueChanged.connect(
            lambda v: self._peak_freq_label.setText(f"{v} Hz")
        )
        freq_row = QHBoxLayout()
        freq_row.addWidget(self._peak_freq_slider)
        freq_row.addWidget(self._peak_freq_label)
        wl_layout.addRow("主频:", freq_row)

        # Ormsby: f1-f4 sliders
        self._f1_slider = QSlider(Qt.Orientation.Horizontal)
        self._f2_slider = QSlider(Qt.Orientation.Horizontal)
        self._f3_slider = QSlider(Qt.Orientation.Horizontal)
        self._f4_slider = QSlider(Qt.Orientation.Horizontal)
        for s, default in [(self._f1_slider, 5), (self._f2_slider, 10),
                           (self._f3_slider, 40), (self._f4_slider, 50)]:
            s.setRange(1, 100)
            s.setValue(default)
        self._f1_label = QLabel("5")
        self._f2_label = QLabel("10")
        self._f3_label = QLabel("40")
        self._f4_label = QLabel("50")
        for s, lbl in [(self._f1_slider, self._f1_label), (self._f2_slider, self._f2_label),
                        (self._f3_slider, self._f3_label), (self._f4_slider, self._f4_label)]:
            s.valueChanged.connect(lambda v, l=lbl: l.setText(str(v)))

        self._ormsby_row = QWidget()
        ormsby_layout = QFormLayout(self._ormsby_row)
        ormsby_layout.setContentsMargins(0, 0, 0, 0)
        for name, slider, lbl in [("f1:", self._f1_slider, self._f1_label),
                                   ("f2:", self._f2_slider, self._f2_label),
                                   ("f3:", self._f3_slider, self._f3_label),
                                   ("f4:", self._f4_slider, self._f4_label)]:
            row = QHBoxLayout()
            row.addWidget(slider)
            row.addWidget(lbl)
            ormsby_layout.addRow(name, row)
        self._ormsby_row.setVisible(False)
        wl_layout.addRow(self._ormsby_row)

        # Generate button
        self._generate_btn = QPushButton("生成合成记录")
        self._generate_btn.setStyleSheet(_STYLE_ACCENT)
        self._generate_btn.clicked.connect(self._on_generate)
        wl_layout.addRow(self._generate_btn)

        layout.addWidget(wavelet_group)

        # --- Auto-tie ---
        tie_group = QGroupBox("自动标定")
        tie_group.setStyleSheet(_STYLE_GROUP)
        tie_layout = QVBoxLayout(tie_group)

        self._auto_tie_btn = QPushButton("Auto-Tie (互相关)")
        self._auto_tie_btn.setStyleSheet(_STYLE_BTN)
        tie_layout.addWidget(self._auto_tie_btn)

        self._cc_label = QLabel("CC: --")
        self._cc_label.setStyleSheet("font-size: 12px; color: #4a5568;")
        tie_layout.addWidget(self._cc_label)

        self._shift_label = QLabel("Shift: -- samples")
        self._shift_label.setStyleSheet("font-size: 12px; color: #4a5568;")
        tie_layout.addWidget(self._shift_label)

        layout.addWidget(tie_group)

        # --- Export ---
        export_group = QGroupBox("导出")
        export_group.setStyleSheet(_STYLE_GROUP)
        export_layout = QVBoxLayout(export_group)

        self._export_btn = QPushButton("导出标定 T-D 表")
        self._export_btn.setStyleSheet(_STYLE_BTN)
        self._export_btn.clicked.connect(self._on_export)
        export_layout.addWidget(self._export_btn)

        layout.addWidget(export_group)
        layout.addStretch()

    def _on_wavelet_type_changed(self, text: str):
        self._ormsby_row.setVisible(text == "Ormsby")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_calibration(self, calibration):
        """Store a WellTieCalibration instance."""
        self._calibration = calibration

    def set_well_logs(self, depths, sonic, density):
        """Store well log arrays for synthetic generation."""
        self._depths = np.asarray(depths, dtype=np.float64)
        self._sonic = np.asarray(sonic, dtype=np.float64)
        self._density = np.asarray(density, dtype=np.float64)

    def generate_synthetic(self, dt_ms: float = 4.0):
        """Generate synthetic seismogram from stored logs and wavelet params."""
        if self._calibration is None or self._sonic is None:
            return

        from geoviz_well_tie.synthetic import compute_reflectivity, generate_synthetic_twt

        rc = compute_reflectivity(self._sonic, self._density)
        mid_depths = (self._depths[:-1] + self._depths[1:]) / 2.0
        mid_twt = self._calibration.depth_to_twt(mid_depths)
        from geoviz_well_tie.calibration import WellTieCalibration
        mid_cal = WellTieCalibration(mid_depths, np.asarray(mid_twt))
        rc_twt = mid_cal.resample_to_twt(rc, dt_ms=dt_ms)

        if self._wavelet_combo.currentText() == "Ormsby":
            synth = generate_synthetic_twt(
                rc_twt, wavelet_type="ormsby", dt_ms=dt_ms,
                f1=float(self._f1_slider.value()),
                f2=float(self._f2_slider.value()),
                f3=float(self._f3_slider.value()),
                f4=float(self._f4_slider.value()),
            )
        else:
            synth = generate_synthetic_twt(
                rc_twt, wavelet_type="ricker", dt_ms=dt_ms,
                peak_freq=float(self._peak_freq_slider.value()),
            )

        self._synthetic = synth
        t_max = float(mid_cal.twt[-1])
        self._synthetic_twt = np.arange(len(synth), dtype=np.float64) * dt_ms

        self._shift_samples = None
        self._correlation_coeff = None
        self._cc_label.setText("CC: --")
        self._shift_label.setText("Shift: -- samples")
        self.synthetic_changed.emit(self._synthetic_twt, self._synthetic)

    def auto_tie(self, seismic_trace: np.ndarray):
        """Run auto-tie against a seismic trace and update readout."""
        if self._synthetic is None:
            return

        from geoviz_well_tie.auto_tie import auto_tie_with_quality
        shift, cc = auto_tie_with_quality(seismic_trace, self._synthetic)
        self._shift_samples = shift
        self._correlation_coeff = cc
        self._cc_label.setText(f"CC: {cc:.3f}")
        self._shift_label.setText(f"Shift: {shift} samples")

    def _on_generate(self):
        self.generate_synthetic(dt_ms=4.0)

    def _on_export(self):
        if self._calibration is None:
            return
        pairs = self._calibration.to_td_pairs()
        path, _ = QFileDialog.getSaveFileName(
            self, "导出标定 T-D 表", "calibration_td.csv", "CSV (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["depth_m", "twt_ms"])
            for d, t in zip(pairs["depth_m"], pairs["twt_ms"]):
                writer.writerow([f"{d:.2f}", f"{t:.2f}"])
        logger.info("Exported calibration to %s", path)
