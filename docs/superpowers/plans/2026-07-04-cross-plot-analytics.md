# Implementation Plan: Cross-Plot Analytics & Lithology Clustering (Phase 31 / v0.19.0)

## Overview
Implement the **Cross-Plot Analytics & Lithology Clustering Workspace (`CrossPlotTab`)** in `geoviz-plots` and `PlotsPage`. Features include freehand polygon lasso selection, SciPy convex hull polygon calculation, dual-mode Z-axis colormapping (continuous gradient / discrete lithology), cross-view depth linking, and 300 DPI vector PDF/SVG export.

---

## Tasks & Sub-Phases

### Task 1: SciPy Convex Hull & Lasso Geometry Math
- **Files**: `packages/geoviz_plots/geoviz_plots/chart/convex_hull.py`
- **Work**:
  - Implement point-in-polygon filtering for `QPolygonF` and NumPy arrays.
  - Implement `compute_convex_hull(x, y)` wrapping `scipy.spatial.ConvexHull`.
- **Tests**: `tests/test_convex_hull.py`

### Task 2: Dual-Mode Colorbar Widget
- **Files**: `packages/geoviz_plots/geoviz_plots/chart/colorbar.py`
- **Work**:
  - Implement `ColorbarWidget` supporting continuous gradient spectrum rendering and discrete lithology swatches.
- **Tests**: `tests/test_colorbar.py`

### Task 3: CrossPlotWidget Interactive Scatter Canvas
- **Files**: `packages/geoviz_plots/geoviz_plots/chart/cross_plot_widget.py`
- **Work**:
  - Implement `CrossPlotWidget` with scatter rendering, mouse polygon lasso tracing, and convex hull polygon overlays.
  - Emit `points_selected` signal.
- **Tests**: `tests/test_cross_plot_widget.py`

### Task 4: PlotsPage Integration & 300 DPI Vector PDF Exporter
- **Files**: `src/pages/plots/page.py`
- **Work**:
  - Integrate `CrossPlotWidget` as a dedicated tab in `PlotsPage`.
  - Add 300 DPI vector PDF/SVG report exporter.
- **Tests**: `tests/test_cross_plot_page_export.py`

---

## Verification Criteria

1. All unit & integration tests in `tests/test_convex_hull.py`, `tests/test_colorbar.py`, `tests/test_cross_plot_widget.py`, and `tests/test_cross_plot_page_export.py` pass.
2. Full test suite executes cleanly with 0 failures.
