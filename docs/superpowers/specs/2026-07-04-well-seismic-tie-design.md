# Technical Design Spec: Well-Seismic Tie Workspace (Phase 30 / v0.18.0)

## 1. Executive Summary

The **Well-Seismic Tie Workspace (`WellTiePage`)** provides an interactive, professional multi-track desktop interface for calibrating well logs (Sonic, Density) with 2D/3D seismic data. It features a high-performance 7-track QPainter canvas, real-time T-D curve stretching with checkshot control points, cross-correlation auto-tie, wavelet parameterization, and 300 DPI vector PDF/SVG report generation matching Chinese petroleum exploration standards (国标规范).

---

## 2. System Architecture & Component Responsibilities

```
+-----------------------------------------------------------------------------+
|                            GeoViz Main App (src/)                           |
|                                                                             |
|  - Navigation: /well_tie (Sidebar item: well_tie.svg)                       |
|  - WellTiePage: Main window layout, header toolbar, left control panel       |
+------------------------------------+----------------------------------------+
                                     |
                                     v
+------------------------------------+----------------------------------------+
|              geoviz_well_tie (Packages: Core Engine & GUI)                  |
|                                                                             |
|  1. Core Domain Engine (Pure NumPy/SciPy):                                  |
|     - CheckshotTable & WellTieCalibration (T-D warping & depth conversion)  |
|     - WaveletEngine (Ricker, Ormsby, Statistical extraction)                |
|     - SyntheticGenerator (AI -> RC -> Convolve wavelet)                     |
|     - TieEvaluator (Cross-correlation R, lag shift, residual envelope)      |
|                                                                             |
|  2. WellTieCanvas (QPainter High-Performance Rendering Widget):             |
|     - Static QPixmap Layer (7-track backgrounds, grid lines, static curves) |
|     - Dynamic Layer (Hover crosshair, active T-D handle dragging, markers)  |
+------------------------------------+----------------------------------------+
                                     |
                                     v
+------------------------------------+----------------------------------------+
|              Publishing Cartography & Vector Export Engine                  |
|                                                                             |
|  - WellTieReportExporter: 300 DPI Vector PDF / SVG generator                |
|  - Includes standard title block (国标责任表), wavelet spectrum & R-score    |
+-----------------------------------------------------------------------------+
```

### Module Breakdown
1. `geoviz_well_tie/well_tie_calibration.py`: `WellTieCalibration` class for managing discrete T-D checkshot pairs and 1D monotone spline interpolation.
2. `geoviz_well_tie/wavelet_engine.py`: Wavelet generation (Ricker, Ormsby) and statistical extraction from seismic trace arrays.
3. `geoviz_well_tie/synthetic_generator.py`: Calculates Acoustic Impedance ($AI = V_p \times \rho$), Reflectivity Series ($RC$), and performs 1D convolution with the active wavelet.
4. `geoviz_well_tie/tie_evaluator.py`: Windowed cross-correlation coefficient $R(t)$, lag shift estimation, and amplitude residual calculation.
5. `geoviz_well_tie/canvas.py`: `WellTieCanvas` 7-track QPainter canvas with static `QPixmap` buffering.
6. `geoviz_well_tie/sidebar.py`: `WellTieSidebar` collapsible control panel for wavelet sliders, checkshot tools, and quality readouts.
7. `src/pages/well_tie/page.py`: `WellTiePage` main navigation page integrated into `MainWindow` (`src/app.py`).

---

## 3. 7-Track Canvas Specification

| Track # | Name | Content | Render Style | Default Width |
|---|---|---|---|---|
| **Track 1** | **Depth & TWT Axis** | Dual depth (m) and TWT (ms) grid ticks & T-D drag handles | Ticks left/right, gridlines `#e5eaf1` | 80px |
| **Track 2** | **Logs (DT & RHOB)** | Sonic DT ($\mu s/m$) and Density RHOB ($g/cm^3$) curves | DT blue (`#1f66d4`), RHOB red (`#d63838`) | 140px |
| **Track 3** | **Impedance (AI)** | Acoustic Impedance $AI = V_p \times \rho$ | Light warm fill (`#fffbeb`), brown stroke | 110px |
| **Track 4** | **Reflectivity (RC)** | Vertical spike series $RC_i = \frac{AI_{i+1}-AI_i}{AI_{i+1}+AI_i}$ | Positive spikes blue (`+#1f66d4`), Negative red (`-#d63838`) | 70px |
| **Track 5** | **Synthetic Trace** | Convolved synthetic seismogram trace | Positive peak blue/black fill, negative dashed | 100px |
| **Track 6** | **Seismic Traces** | Extracted real seismic traces (3-5 traces) | Peak gray/blue fill, side-by-side match | 120px |
| **Track 7** | **Correlation & Residual** | Windowed correlation $R(t)$ and amplitude residual | Green (`#10b981`) match / Red (`#ef4444`) discrepancy | 90px |

---

## 4. Key Interactive Workflows

### 4.1 T-D Checkshot Stretching
- Clicking and dragging a checkshot point handle on Track 1 updates `WellTieCalibration`.
- Sonic and Density data are resampled on the fly to TWT time steps.
- Synthetic seismogram is re-convolved and re-drawn on `WellTieCanvas` in `< 1ms`.

### 4.2 Auto-Tie Alignment
- Auto-Tie button triggers `TieEvaluator.auto_tie()`.
- Computes cross-correlation function $C(\tau) = \sum S(t) \cdot X(t+\tau)$.
- Shifts checkshot T-D curve by optimal lag $\tau_{max}$ and reports correlation coefficient $R$.

### 4.3 300 DPI Publishing Vector Export
- Generates publication-grade A4/A3 vector PDF (`QPrinter`) and SVG (`QSvgGenerator`).
- Includes standard 3-column Chinese Petroleum Title Block (国标责任表), wavelet spectrum inset, and correlation quality scorecard.

---

## 5. Verification Plan

1. **Unit Tests**:
   - `tests/test_well_tie_calibration.py`: Checkshot interpolation, T-D monotonicity, handle dragging updates.
   - `tests/test_wavelet_engine.py`: Ricker/Ormsby synthesis, statistical extraction.
   - `tests/test_synthetic_generator.py`: AI -> RC -> synthetic trace convolution.
   - `tests/test_well_tie_canvas.py`: 7-track widget creation, geometry calculations, static QPixmap buffer invalidation.
2. **Integration Tests**:
   - `tests/test_well_tie_page.py`: Full page initialization, sidebar toggle, auto-tie execution, PDF/SVG export.
