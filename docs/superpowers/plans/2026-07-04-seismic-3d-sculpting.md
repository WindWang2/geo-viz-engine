# 3D Seismic Horizon Interactive Sculpting & Attribute Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 3D interactive horizon sculpting with a Gaussian radius brush, GLSL 3D volume texture attribute mapping along the surface, real-time volume clipping synchronization, and interactive brush controls in the 3D Seismic View.

**Architecture:**
- Create `packages/geoviz_seismic/geoviz_seismic/interactive_horizon.py` containing `InteractiveHorizonGLItem` (VBO updates, 3D brush cursor, GLSL dual-sampling shader).
- Extend `packages/geoviz_seismic/geoviz_seismic/horizon.py` with 3D raycasting, Gaussian deformation math, and ROI undo patch logic.
- Extend `packages/geoviz_seismic/geoviz_seismic/seismic_view.py` and `src/pages/seismic/page.py` with 3D Brush toolbar controls (radius, strength, mode toggles).
- Create `tests/test_seismic_3d_sculpting.py` for full test validation.

**Tech Stack:** PySide6, PyQtGraph OpenGL, PyOpenGL, NumPy, pytest + pytest-qt.

**Spec:** `docs/superpowers/specs/2026-07-04-seismic-3d-sculpting-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `packages/geoviz_seismic/geoviz_seismic/horizon.py` | 3D raycasting math, Gaussian grid deformation, ROI undo history patches |
| `packages/geoviz_seismic/geoviz_seismic/interactive_horizon.py` | New GLSL OpenGL item rendering 3D surface, attribute sampling & brush cursor |
| `packages/geoviz_seismic/geoviz_seismic/renderer_3d.py` | Integration with `Seismic3DRenderer` & volume sculpting texture synchronization |
| `packages/geoviz_seismic/geoviz_seismic/seismic_view.py` | 3D view toolbar additions (brush radius slider, strength, mode toggle) |
| `tests/test_seismic_3d_sculpting.py` | Unit & integration test suite for raycasting, sculpting math, shader, and undo |

---

## Tasks

### Task 1: 3D Raycasting & Surface Intersection Math

**Files:**
- Modify: `packages/geoviz_seismic/geoviz_seismic/horizon.py`

- [ ] **Step 1: Write unit tests for raycasting math**
  - Verify ray unprojection from screen coordinates $(x, y)$ using view-projection matrix.
  - Verify ray-grid intersection locating correct grid index $(i, j)$ on known heightmap.

- [ ] **Step 2: Implement `unproject_ray()` and `intersect_ray_grid()`**
  - Add camera unprojection math using inverse MVP matrix.
  - Implement ray marching / binary search over heightmap grid $Z = H(i, j)$.

---

### Task 2: 3D Gaussian Sculpting Engine & ROI Undo System

**Files:**
- Modify: `packages/geoviz_seismic/geoviz_seismic/horizon.py`

- [ ] **Step 1: Write unit tests for Gaussian deformation math**
  - Test elevation calculation $\Delta Z = A \cdot \exp(-d^2 / (2\sigma^2))$ for center and boundary points.
  - Test ROI patch creation and undo restoration.

- [ ] **Step 2: Implement `apply_gaussian_sculpt()` and `HorizonROIPatch`**
  - Implement NumPy vectorized elevation offset computation.
  - Implement ROI bounding box diff capturing for undo/redo stack.

---

### Task 3: Interactive Horizon GLSL Item & Shader

**Files:**
- Create: `packages/geoviz_seismic/geoviz_seismic/interactive_horizon.py`

- [ ] **Step 1: Write unit test for `InteractiveHorizonGLItem` initialization**
  - Verify item creation, VBO allocation, and attribute mode properties.

- [ ] **Step 2: Implement `InteractiveHorizonGLItem`**
  - Build OpenGL mesh VBO with dynamic `glBufferSubData` updates.
  - Write GLSL dual-sampling shader for 3D volume attribute texture lookup + depth colormap.
  - Draw 3D ring cursor at the raycast intersection point.

---

### Task 4: UI Toolbar Integration & Volume Synchronization

**Files:**
- Modify: `packages/geoviz_seismic/geoviz_seismic/seismic_view.py`
- Modify: `src/pages/seismic/page.py`

- [ ] **Step 1: Add 3D Brush Controls to Seismic View Toolbar**
  - Add brush toggle button (Brush ON/OFF), radius slider (1-50m), strength slider, and attribute mode selector.

- [ ] **Step 2: Wire `horizon_modified` signal to `DualGLVolumeItem`**
  - Automatically re-upload `_sculpt_horizon_tex` when horizon sculpting finishes.

---

### Task 5: TDD Testing & Full Regression Verification

**Files:**
- Create: `tests/test_seismic_3d_sculpting.py`

- [ ] **Step 1: Write full integration tests**
  - Test end-to-end brush interaction, attribute colormap switching, and volume sculpt sync.

- [ ] **Step 2: Run test suite**
  - Command: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src:packages/geoviz_map:packages/geoviz_paleo_map:packages/geoviz_well_log:packages/geoviz_cross_well:packages/geoviz_seismic:packages/geoviz_well_tie:packages/geoviz_plots pytest tests/test_seismic_3d_sculpting.py -v`
