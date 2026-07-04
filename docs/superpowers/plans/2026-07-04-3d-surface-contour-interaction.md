# Phase 29-C Implementation Plan: 3D Surface & Dynamic Contour Interaction (v0.17.0)

## Overview
Implement fault-barrier IDW interpolation, interactive 2D control point dragging in `SurfaceWidget`, and real-time synchronized 3D horizon VBO updates with isoline highlights.

---

## Tasks & Sub-Phases

### Task 1: Fault-Barrier IDW Interpolation Algorithm
- **Files**: `packages/geoviz_plots/geoviz_plots/interpolation/idw.py`
- **Work**:
  - Implement segment intersection algorithm `segments_intersect(p1, p2, q1, q2)`.
  - Add `fault_polylines` support to `interpolate_idw()`.
  - Zero-out weights when interpolation line segment crosses any fault barrier.
- **Tests**: `tests/test_idw_fault_barriers.py`

### Task 2: 2D SurfaceWidget Control Point Interaction & Contour Picking
- **Files**: `packages/geoviz_plots/geoviz_plots/surface/surface_widget.py`
- **Work**:
  - Add `set_control_points()`, `add_control_point()`, `set_fault_polylines()`.
  - Implement mouse press/move/release handlers for point selection and 2D dragging.
  - Draw control point markers (circles + Z labels) and fault polylines (dashed red lines).
  - Add contour level hover / Shift-click picking and signal `contour_selected`.
- **Tests**: `tests/test_surface_widget_interaction.py`

### Task 3: 3D Horizon Dynamic Sync & 3D Contour Overlay
- **Files**: `packages/geoviz_seismic/geoviz_seismic/interactive_horizon.py`
- **Work**:
  - Add `update_heightmap(grid_x, grid_y, grid_z)` method for fast VBO updating.
  - Extract 3D isolines and render 3D contour lines over the surface mesh.
- **Tests**: `tests/test_3d_contour_sync.py`

---

## Verification Criteria

1. All new unit tests in `tests/test_idw_fault_barriers.py`, `tests/test_surface_widget_interaction.py`, and `tests/test_3d_contour_sync.py` pass.
2. Full test suite passes without regressions.
