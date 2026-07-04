# 3D Seismic Horizon Interactive Sculpting & Attribute Mapping — Design Spec

**Date:** 2026-07-04  
**Status:** Approved  
**Branch target:** feat/seismic-3d-sculpting  
**Version:** v0.15.0  

---

## 1. Problem Statement

GeoViz Engine's 3D Seismic View (`geoviz-seismic`) currently supports GPU-accelerated volume rendering, GLSL normal hillshading, and horizon-based volume sculpting (discarding volume data above/below static horizons). However, it lacks interactive 3D horizon manipulation and real-time attribute mapping on horizon surfaces:
1. **Static Horizon Surfaces:** Horizons cannot be interactively modified or fine-tuned directly in the 3D viewport.
2. **Missing Attribute Surface Mapping:** Horizon surfaces are only colored uniformly or by simple static depth values, without dynamic extraction of 3D seismic volume attributes (e.g. RMS amplitude, instantaneous frequency, coherence) along the horizon geometry.
3. **Lack of Instant Feedback:** Editing horizon boundaries requires offline manual editing or re-importing data.

To solve these pain points, we will implement **3D Horizon Interactive Gaussian Sculpting & Real-time Attribute Mapping** in the `geoviz-seismic` package.

---

## 2. Scope

### In Scope
1. **Interactive 3D Horizon Mesh (`InteractiveHorizonGLItem`):** Custom OpenGL mesh rendering with 60 FPS VBO incremental updates.
2. **3D Raycasting & Ray-Grid Intersection:** Unprojecting 3D viewport mouse coordinates to find grid surface intersection points $(X_0, Y_0, Z_0)$.
3. **3D Gaussian Radius Brush:** Interactive elevation manipulation with mouse drag (Left-Click to elevate, Shift + Left-Click to lower) with smooth Gaussian weight falloff.
4. **GLSL Dual-Sampling Shader:** Real-time 3D volume texture attribute sampling along horizon $Z(x,y)$ overlaid with directional lighting (Hillshading).
5. **ROI-based Undo/Redo System:** Efficient patch-based undo history for 3D brush operations.
6. **Volume Sculpting Synchronization:** Real-time updating of `DualGLVolumeItem`'s GPU sculpting texture when the horizon is edited.

### Out of Scope
- Multi-surface fault line snapping (focusing on continuous layer horizon surfaces).
- Automatic AI horizon tracking from raw seismic traces (staying focused on interactive refinement and visual display).

---

## 3. Architecture & Class Design

The changes reside in `packages/geoviz_seismic/geoviz_seismic/` and the seismic page UI.

```
packages/geoviz_seismic/geoviz_seismic/
├── renderer_3d.py          # UPDATED: Integrates InteractiveHorizonGLItem & Brush controller
├── horizon.py              # UPDATED: Gaussian deformation math and ROI diff patch logic
├── interactive_horizon.py  # NEW: Custom GLSL Item with 3D texture sampling & brush cursor
└── seismic_view.py         # UPDATED: Adds 3D Brush toolbar (radius, strength, mode toggles)
```

### Key Components

1. **`InteractiveHorizonGLItem`** (`gl.GLGraphicsItem`):
   - Maintains VBOs for mesh vertices $(x, y, z)$, normals $(n_x, n_y, n_z)$, and 3D texture coordinates $(u, v, w)$.
   - Renders 3D brush ring indicator on the surface at the raycast intersection point.
   - Executes GLSL dual-sampling shader (attribute texture vs depth colormap).

2. **`HorizonSculptController`**:
   - Intercepts 3D mouse events (`mouseMoveEvent`, `mousePressEvent`, `mouseReleaseEvent`).
   - Unprojects viewport screen coordinates $(x, y)$ using Camera View/Projection matrices.
   - Computes ray-surface intersection and updates the horizon grid elevation in NumPy.
   - Pushes ROI diff patches to the `QUndoStack`.

3. **`DualGLVolumeItem` Integration**:
   - Emits `horizon_modified` signal when editing finishes.
   - `DualGLVolumeItem` re-uploads `_sculpt_horizon_tex` to sync volume clipping seamlessly.

---

## 4. Detailed Technical Design

### 4.1. 3D Raycasting & Surface Intersection

Given mouse pixel coordinate $(x_s, y_s)$ and viewport dimensions $(W, H)$:
1. Normalized Device Coordinates (NDC):
   $$x_{ndc} = \frac{2 x_s}{W} - 1, \quad y_{ndc} = 1 - \frac{2 y_s}{H}$$
2. Unproject ray using inverse Camera View-Projection Matrix $M_{inv} = (P \cdot V)^{-1}$:
   $$P_{near} = M_{inv} \cdot [x_{ndc}, y_{ndc}, -1, 1]^T, \quad P_{far} = M_{inv} \cdot [x_{ndc}, y_{ndc}, 1, 1]^T$$
   Ray direction $D = \text{normalize}(P_{far} - P_{near})$, Ray origin $O = P_{near}$.
3. Ray Marching / Binary Search over grid surface $Z = H(i, j)$ to locate intersection $(X_0, Y_0, Z_0)$.

### 4.2. Gaussian Brush Deformation

For grid nodes $(i, j)$ within radius $d = \sqrt{(x_i - X_0)^2 + (y_j - Y_0)^2} \le 3\sigma$:
$$\Delta Z = A \cdot \exp\left(-\frac{d^2}{2\sigma^2}\right)$$
- Left-Click drag: $Z_{new} = Z_{old} + \Delta Z$
- Shift + Left-Click drag: $Z_{new} = Z_{old} - \Delta Z$
- Radius $\sigma$ adjustable via Toolbar spinbox or `Alt + Scroll`.
- Strength $A$ adjustable via Toolbar slider.

### 4.3. GLSL Dual-Sampling Shader

```glsl
// Fragment Shader for InteractiveHorizonGLItem
uniform sampler3D u_seismic_vol;     // 3D seismic volume texture
uniform sampler1D u_colormap;        // Attribute or depth LUT
uniform vec3 u_light_dir;            // Hillshading direction
uniform float u_mode;                // 0: Elevation Depth, 1: Volume Attribute

varying vec3 v_world_pos;
varying vec3 v_normal;
varying vec3 v_tex_coord;

void main() {
    float val;
    if (u_mode > 0.5) {
        val = texture3D(u_seismic_vol, v_tex_coord).r;
    } else {
        val = v_tex_coord.z;
    }
    
    vec4 color = texture1D(u_colormap, val);
    float diff = max(dot(normalize(v_normal), normalize(u_light_dir)), 0.2);
    color.rgb *= (0.3 + 0.7 * diff);
    
    gl_FragColor = color;
}
```

---

## 5. Performance & Testing Strategy

### Performance
- Use `glBufferSubData` to upload only modified vertex regions during dragging.
- Keep ROI patch memory lightweight for 20-step undo history.

### Testing Strategy
- Unit and integration tests in `tests/test_seismic_3d_sculpting.py`:
  1. `test_gaussian_sculpting_math()`: Verify elevation offsets match Gaussian formula.
  2. `test_ray_grid_intersection()`: Test 3D ray unprojection onto known grid.
  3. `test_undo_redo_roi_patch()`: Verify grid state restoration after undo/redo.
  4. `test_horizon_sculpting_glsl_sync()`: Verify volume sculpt texture update triggers correctly.
