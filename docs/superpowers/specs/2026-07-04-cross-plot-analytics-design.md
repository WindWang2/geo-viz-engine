# Technical Design Spec: Cross-Plot Analytics & Lithology Clustering (Phase 31 / v0.19.0)

## 1. Executive Summary

The **Cross-Plot Analytics & Lithology Clustering Toolbox (`CrossPlotTab`)** introduces an interactive, multi-dimensional scatter plotting workspace to `geoviz-plots` and `PlotsPage`. It features freehand polygon lasso selection, automated SciPy convex hull polygon enclosure calculation, dual-mode Z-axis colormapping (continuous gradient with colorbar / discrete lithology swatches), cross-view depth highlighting, and 300 DPI vector PDF/SVG report generation matching Chinese petroleum exploration standards.

---

## 2. System Architecture & Component Breakdown

```
+-----------------------------------------------------------------------------+
|                         PlotsPage (src/pages/plots/page.py)                 |
|                                                                             |
|  - Tab 1: 2D General Chart (PlotWidget)                                     |
|  - Tab 2: Spatial Surface Contouring (SurfaceWidget)                        |
|  - Tab 3 (New): Cross-Plot Analytics Workspace (CrossPlotWidget)            |
+------------------------------------+----------------------------------------+
                                     |
                                     v
+------------------------------------+----------------------------------------+
|            geoviz_plots (Package: Cross-Plot Engine & Widgets)              |
|                                                                             |
|  1. CrossPlotWidget (packages/geoviz_plots/geoviz_plots/cross_plot_widget.py)|
|     - Scatter data rendering (X, Y, Z arrays)                               |
|     - Freehand Polygon Lasso mouse handler (QPolygonF)                      |
|     - SciPy ConvexHull region calculator & transparent polygon overlays     |
|                                                                             |
|  2. ColorbarWidget (packages/geoviz_plots/geoviz_plots/colorbar.py)          |
|     - Continuous colormap LUT rendering (Viridis, CNPC Strat, Thermal)      |
|     - Discrete lithology legend swatches                                    |
+------------------------------------+----------------------------------------+
                                     |
                                     v
+------------------------------------+----------------------------------------+
|              Cross-View Synchronization & Vector Exporter                   |
|                                                                             |
|  - Global Selection Signal: points_selected(indices, depth_bounds)          |
|  - WellLogPage & MapPage integration for cross-view highlighting             |
|  - 300 DPI Vector PDF / SVG Exporter (QPrinter / QSvgGenerator)             |
+-----------------------------------------------------------------------------+
```

### Module Responsibilities
1. `packages/geoviz_plots/geoviz_plots/cross_plot_widget.py`: Dedicated `CrossPlotWidget` supporting scatter rendering, mouse lasso polygon tracing, point-in-polygon filtering, and SciPy `ConvexHull` bounding polygon overlays.
2. `packages/geoviz_plots/geoviz_plots/colorbar.py`: `ColorbarWidget` for rendering continuous gradient spectrums and discrete lithology swatches.
3. `src/pages/plots/page.py`: Integrates `CrossPlotWidget` as a dedicated tab within `PlotsPage` with parameter controls and export actions.

---

## 3. Lasso ROI & Convex Hull Specifications

- **Polygon Lasso Tracing**: Tracks mouse dragging points in data coordinates `(x_i, y_i)` as a closed `QPolygonF`.
- **Point-in-Polygon Testing**: Ray-casting algorithm on NumPy arrays to filter enclosed points subset $(X_{sel}, Y_{sel})$ in sub-millisecond execution.
- **SciPy Convex Hull**: Computes `scipy.spatial.ConvexHull` over $(X_{sel}, Y_{sel})$, producing a smooth bounding polygon rendered with semi-transparent fill (`#1f66d4`, alpha 40) and high-contrast stroke (`#1f66d4`, 2px).
- **Cluster Regions**: Stores named ROI clusters `[{"name": "Sandstone Unit", "hull": polygon, "indices": array, "color": QColor}]` for toggling and editing.

---

## 4. Z-Axis Color Mapping & Cross-View Sync

### Dual Colorbar Modes
- **Continuous Gradient Mode**: Maps $Z \in [Z_{min}, Z_{max}]$ to colormaps (`Viridis`, `CNPC Strat`, `Thermal`) and renders a vertical colorbar with numeric ticks.
- **Discrete Categorical Mode**: Maps discrete facies/lithology codes to CNPC standard lithology colors (Sandstone `#ffdc5f`, Shale `#646e78`, Limestone `#5ab0ff`, Evaporite `#b45309`) with swatch labels.

### Cross-View Linking
- Emits `points_selected(indices, depth_bounds)` signal.
- `WellLogPage` receives signal to highlight corresponding depth range bands in well tracks.

---

## 5. Verification Plan

1. **Unit Tests**:
   - `tests/test_cross_plot_widget.py`: `CrossPlotWidget` point initialization, lasso selection, point-in-polygon filtering.
   - `tests/test_convex_hull.py`: SciPy ConvexHull calculation and polygon boundary generation.
   - `tests/test_colorbar.py`: Continuous & discrete colorbar widget rendering.
2. **Integration Tests**:
   - `tests/test_cross_plot_page_export.py`: Full `PlotsPage` tab switching, cross-view signal propagation, and 300 DPI PDF/SVG export.
