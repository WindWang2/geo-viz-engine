# Implementation Plan: Well-Seismic Tie Workspace (Phase 30 / v0.18.0)

## Overview
Implement the dedicated **Well-Seismic Tie Workspace (`WellTiePage`)** with a high-performance 7-track QPainter canvas (`WellTieCanvas`), interactive checkshot T-D curve stretching, auto-tie cross-correlation alignment, wavelet parameterization, and 300 DPI publishing vector report exporter (PDF/SVG).

---

## Tasks & Sub-Phases

### Task 1: Core Domain Engine (`geoviz_well_tie`)
- **Files**:
  - `packages/geoviz_well_tie/geoviz_well_tie/wavelet_engine.py`
  - `packages/geoviz_well_tie/geoviz_well_tie/synthetic_generator.py`
  - `packages/geoviz_well_tie/geoviz_well_tie/tie_evaluator.py`
- **Work**:
  - Implement Ricker/Ormsby wavelet synthesis and statistical wavelet extraction from trace arrays.
  - Implement Acoustic Impedance $AI$, Reflectivity $RC$, and 1D convolution synthetic generator.
  - Implement windowed cross-correlation $R(t)$, lag shift, and residual calculation.
- **Tests**: `tests/test_well_tie_core.py`

### Task 2: 7-Track Canvas & Interactive T-D Stretching (`WellTieCanvas`)
- **Files**: `packages/geoviz_well_tie/geoviz_well_tie/canvas.py`
- **Work**:
  - Implement 7-track layout rendering (Depth/TWT, Logs, AI, RC, Synthetic, Seismic, Residual).
  - Implement static `QPixmap` double-buffering cache.
  - Implement mouse drag events on Checkshot handles with real-time waveform updates.
- **Tests**: `tests/test_well_tie_canvas.py`

### Task 3: Collapsible Sidebar & Navigation Page (`WellTiePage`)
- **Files**:
  - `packages/geoviz_well_tie/geoviz_well_tie/sidebar.py`
  - `src/pages/well_tie/page.py`
  - `src/app.py`
- **Work**:
  - Implement `WellTieSidebar` with wavelet sliders, checkshot tools, and auto-tie trigger.
  - Create `WellTiePage` with header controls and integrate into `app.py` main navigation sidebar with icon `well_tie.svg`.
- **Tests**: `tests/test_well_tie_page.py`

### Task 4: 300 DPI Publishing Vector Report Exporter
- **Files**: `packages/geoviz_well_tie/geoviz_well_tie/report_export.py`
- **Work**:
  - Implement 300 DPI vector PDF (`QPrinter`) and SVG (`QSvgGenerator`) exporter.
  - Include standard 3-column Chinese Petroleum Title Block (国标责任表), wavelet spectrum inset, and R-score scorecard.
- **Tests**: `tests/test_well_tie_export.py`

---

## Verification Criteria

1. All unit & integration tests in `tests/test_well_tie_core.py`, `tests/test_well_tie_canvas.py`, `tests/test_well_tie_page.py`, and `tests/test_well_tie_export.py` pass.
2. Full test suite executes cleanly with 0 failures.
