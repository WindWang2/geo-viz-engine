# Cross-Well Multi-Curve Overlay & Interactive Picking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement dynamic curve overlay configurations, multi-scale color-coded headers, vertical feature snapping (max/min), real-time hover previews, and a collapsible right control sidebar in the well correlation page.

**Architecture:**
- Extend `packages/geoviz_well_log`'s `CurveTrack` to draw multi-scale side-by-side ranges.
- Extend `packages/geoviz_cross_well`'s `CrossWellCanvas` to hold pick/snap state, dynamic `_curve_groups` settings, and run snapping calculations.
- Create `src/pages/cross_well/sidebar.py` containing the right collapsible configuration panel.
- Update `src/pages/cross_well/page.py` to integrate the sidebar, handle toggle events, and rebuild well tracks dynamically.

**Tech Stack:** PySide6 (Qt for Python), NumPy, pytest + pytest-qt.

**Spec:** `docs/superpowers/specs/2026-07-04-cross-well-interactive-picking-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py` | Draw multiple color-coded display ranges side-by-side in track content |
| `packages/geoviz_cross_well/geoviz_cross_well/canvas.py` | Core canvas holding snap settings, active curve, and implementing snapping math |
| `src/pages/cross_well/sidebar.py` | New Sidebar widget managing active horizon, snapping controls, and curve overlays |
| `src/pages/cross_well/page.py` | Sidebar placement, collapsible animation/layout, and dynamic track rebuilding |
| `tests/test_cross_well_picking.py` | New unit and integration tests for snapping, overlays, and sidebar |

---

## Tasks

### Task 1: Multi-Scale Header Rendering

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py`

- [ ] **Step 1: Write/Update unit test for multi-scale header rendering**
  - Verify that when multiple curves are present in `CurveTrack`, multiple range strings are drawn with respective coordinates and colors.
  
- [ ] **Step 2: Modify `CurveTrack.paint_content` to draw range labels side-by-side**
  - Slice the width of the track into $K$ columns where $K$ is the number of curves in `self._curves`.
  - Draw `lo` at the top and `hi` at the bottom for each column using the corresponding curve's color.

---

### Task 2: Snapping State & Snapping Logic

**Files:**
- Modify: `packages/geoviz_cross_well/geoviz_cross_well/canvas.py`

- [ ] **Step 1: Add state variables to `CrossWellCanvas`**
  - Add `_active_curve`, `_active_formation`, `_snap_type` ("max", "min", "none"), and `_snap_window_m` properties.
  - Implement getters and setters for these fields.
  
- [ ] **Step 2: Add snapping calculation function `_get_snapped_depth()`**
  - Extract the active curve data (depths, values) for the given canvas.
  - Find the local maximum or minimum index of values within the vertical range `[clicked_depth - snap_window_m, clicked_depth + snap_window_m]`.
  - Return the corresponding depth.

- [ ] **Step 3: Update `_handle_pick_click()` to use `_get_snapped_depth()`**
  - Calculate `snapped_depth = self._get_snapped_depth(canvas, clicked_depth)`.
  - Pass the `snapped_depth` to `self._picks_model.add_pick()` or `connect_picks()`.

---

### Task 3: Interactive Hover Snapping Preview

**Files:**
- Modify: `packages/geoviz_cross_well/geoviz_cross_well/canvas.py`

- [ ] **Step 1: Update `_handle_pick_hover()` to compute snapped depth**
  - When in picking mode and hovering over a well canvas, compute the snapped depth of the cursor.
  - Store it as `self._hover_snapped_depth` and emit update/repaint requests.

- [ ] **Step 2: Update `PickingOverlay.paintEvent` to render hover visual feedback**
  - Draw a thin dashed line across the canvas width at the hover snapped depth.
  - Draw a small highlighted filled circle at the coordinate corresponding to the curve's value at that depth.

---

### Task 4: Right Collapsible Sidebar Panel

**Files:**
- Create: `src/pages/cross_well/sidebar.py`
- Modify: `src/pages/cross_well/page.py`

- [ ] **Step 1: Create `CrossWellSidebar` widget in `src/pages/cross_well/sidebar.py`**
  - Implement a widget with a vertical layout:
    - Horizon list manager with dropdown, plus, and minus buttons.
    - Snapping parameters section (dropdown for active curve, radio buttons for snap type, spinbox for search window).
    - Curve grouping checklist/table mapping available curves to target overlays.
    - DTW quick-trigger section.
  - Expose signals when configuration parameters or curve groupings change.

- [ ] **Step 2: Add collapsible layouts in `CrossWellPage.__init__`**
  - Create a middle layout combining the scroll area and sidebar widget.
  - Implement a thin vertical toggle button (`◀` / `▶`) at the edge of the sidebar.
  - Add `QPropertyAnimation` targeting the sidebar's `maximumWidth` to animate transitions between `280px` (expanded) and `0px` (collapsed).

---

### Task 5: Dynamic Track Rebuilding & Integration

**Files:**
- Modify: `src/pages/cross_well/page.py`

- [ ] **Step 1: Update `_on_load_finished` and track assembly**
  - Connect the sidebar's signals to handlers in `CrossWellPage`.
  - When curve groupings change in the sidebar, update `canvas._curve_groups`.
  - Call `_rebuild_canvases()` to dynamically construct and filter track configurations based on `canvas._curve_groups` and re-apply them to each well's `WellLogCanvas`.

- [ ] **Step 2: Verify DTW integration**
  - Ensure DTW propagation uses the sidebar's selected active curve instead of hardcoded lists.

---

### Task 6: TDD Testing & Validation

**Files:**
- Create: `tests/test_cross_well_picking.py`

- [ ] **Step 1: Create tests for snapping and overlays**
  - Verify `_get_snapped_depth` correctly identifies peak/trough depths.
  - Verify track reconstruction correctly merges curves and sets active headers.
  - Verify sidebar collapse/expand toggles and layout dimensions.
  
- [ ] **Step 2: Run all tests**
  - Command: `source .venv/bin/activate && pytest tests/test_cross_well_picking.py -v`
  - Ensure all 878+ tests pass and no regression occurs.
