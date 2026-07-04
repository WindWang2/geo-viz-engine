# Phase 29-C Technical Design: 3D Surface & Dynamic Contour Interaction (v0.17.0)

## Overview
Phase 29-C connects 2D spatial contouring (`geoviz-plots`) with 3D seismic horizon rendering (`geoviz-seismic`). It introduces interactive control-point editing on 2D contour maps with real-time 3D surface VBO updates, fault polyline barrier IDW interpolation, and cross-view contour line picking.

---

## Architecture & Data Flow

```
+-----------------------------------------------------------+
|               2D SurfaceWidget (geoviz-plots)             |
|                                                           |
|  - Scattered Control Points: (x, y, z)                    |
|  - Fault Polyline Barriers: List[Polyline]                |
|  - Interactive Point Dragging & Elevation Editing          |
+-----------------------------+-----------------------------+
                              | Signal: control_points_changed / grid_updated
                              v
+-----------------------------------------------------------+
|               Fault-Barrier IDW Interpolator              |
|               (geoviz_plots.interpolation.idw)            |
|                                                           |
|  - Fast line-segment intersection test                    |
|  - Zero-weighting for ray-fault crossed pairs             |
+-----------------------------+-----------------------------+
                              | Output: grid_z (H x W)
                              v
+-----------------------------------------------------------+
|            InteractiveHorizonGLItem (geoviz-seismic)      |
|                                                           |
|  - Dynamic OpenGL VBO position re-upload                  |
|  - Synchronized 3D Isoline / Contour overlay              |
+-----------------------------------------------------------+
```

---

## Detailed Specifications

### 1. Fault Barrier Interpolation (`geoviz_plots.interpolation.idw`)
- **API Extension**:
  `interpolate_idw(x, y, z, grid_x, grid_y, power=2.0, fault_polylines=None)`
- **Line Intersection Math**:
  For each grid cell center $(X_{i,j}, Y_{i,j})$ and control point $(x_k, y_k)$, test line segment $S = ((X_{i,j}, Y_{i,j}), (x_k, y_k))$ against all line segments in `fault_polylines`.
  If $S$ intersects any fault segment, set `weights[i, j, k] = 0.0`.
- **Vectorized / Numba/NumPy optimization**:
  Use 2D bounding box pre-filtering before cross-product segment intersection calculations to maintain sub-50ms grid calculations.

### 2. Interactive Control Points in `SurfaceWidget` (`geoviz_plots.surface.surface_widget`)
- **Control Point State**:
  - `control_points`: List of dict `{"id": str, "x": float, "y": float, "z": float}`.
  - `fault_polylines`: List of list of `QPointF` / tuple coordinates.
- **Interactions**:
  - Left click + drag: Drag existing control point $(x, y)$.
  - Double click: Add new control point at mouse coordinate.
  - Shift + Left Click: Select active contour line level and highlight matching isolines.
- **Signals**:
  - `grid_updated(grid_x, grid_y, grid_z)`
  - `contour_highlighted(float_level)`

### 3. Synchronized 3D Surface & Contour Overlay (`geoviz_seismic.interactive_horizon`)
- **Heightmap Dynamic Updates**:
  `set_horizon_data(x_grid, y_grid, z_grid)` triggers dynamic VBO buffer re-upload without resetting camera or view parameters.
- **3D Isolines**:
  Extract 3D polyline contours at specified levels and draw them as OpenGL line loops over the 3D surface mesh.

---

## Verification Plan

1. **Unit Tests (`tests/test_idw_fault_barriers.py`)**:
   - Test IDW without faults matches baseline interpolation.
   - Test IDW with fault barrier yields step-discontinuity across the fault line.
2. **Widget Tests (`tests/test_surface_widget_interaction.py`)**:
   - Test control point addition, selection, and dragging.
   - Test signal emission on drag completion.
3. **Integration Tests (`tests/test_3d_contour_sync.py`)**:
   - Test grid update signal propagation from `SurfaceWidget` to `InteractiveHorizonGLItem`.
