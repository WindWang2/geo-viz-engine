# Seismic Display Interaction Enhancement

## Context

The seismic module (geoviz_seismic) can load SEGY volumes, render 3D volumes with slice planes, and display 2D profiles (VD heatmap, wiggle trace). Annotation and attribute features were added recently. However, the profile panels lack basic navigation: no zoom, no pan, no slice browsing, no cross-panel cursor linking. Users cannot efficiently inspect a volume — they can only view static slices at whatever position the 3D sliders happen to be on.

This spec adds the display interaction layer: zoom/pan on profiles, slice browsing via keyboard shortcuts and toolbar sliders, four-panel cursor linkage, and 3D-to-2D jump navigation.

## Requirements

### 1. Profile Zoom and Pan

ProfileVD gains a viewport state that tracks which portion of the seismic data is visible.

**Zoom:**
- Mouse wheel zooms in/out centered on the cursor position, factor 1.2x per tick
- Zoom range: 0.25x (zoomed out to 4x full view) to 32x (zoomed in to 1/32 of data)
- Zoom applies to both axes independently based on cursor position ratio
- `Ctrl+0` or double-click resets to full view

**Pan:**
- Middle mouse button drag pans the viewport
- Pan clamps so the viewport never goes beyond data boundaries (with 10% overscroll margin)
- During pan, cursor crosshair and amplitude readout continue working in data coordinates

**Rendering:**
- On zoom/pan, compute the visible data rectangle `(h_start, h_end, v_start, v_end)` in sample indices
- Extract the subarray, render only that portion to the display pixmap
- Axis tick labels update to reflect the visible data range
- All overlays (crosshair, annotations, picked points, polyline) are drawn in data coordinates, so they move naturally with zoom/pan

**State:**
- `_view_rect: QRectF` in data coordinates (h_range, v_range), initialized to full data extent
- `_zoom_level: float` for display in status bar
- `view_changed()` signal emitted on zoom/pan for external consumers

### 2. Slice Browsing

Two mechanisms to change which slice is displayed in each profile panel.

**Shift+Wheel:**
- In ProfileVD, when Shift modifier is detected in `wheelEvent`, emit `slice_step(direction)` signal (direction = +1 or -1)
- SeismicView connects each panel's `slice_step` signal to its slice navigation handler
- Handler increments/decrements the slice index, clamped to valid range, loads the new slice from cache or loader, updates the panel and the corresponding 3D slider

**Toolbar Slice Sliders:**
- Three QSlider widgets added to the toolbar, one per slice type (IL, XL, T)
- Range: `[0, n-1]` for each dimension
- Label shows actual coordinate value (e.g., "Inline 1200")
- Dragging a slider immediately loads and displays the corresponding slice
- Slider value changes also update the 3D slice plane position (bidirectional sync with existing 3D sliders)
- Sliders are disabled until SEGY data is loaded

**Integration:**
- New slice loading reuses existing `_render_slice()` method and LRU cache
- 3D slice plane sliders and toolbar slice sliders stay synchronized through a shared signal handler
- Shift+wheel on one panel only changes that panel's slice type (e.g., Shift+wheel on IL panel changes inline number only)

### 3. Four-Panel Cursor Linkage

When the cursor moves on any profile panel, the other three panels update their crosshair positions to reflect the same 3D point.

**Signal enhancement:**
- New signal `cursor_moved_3d(float h, float v, str slice_type)` added alongside existing `cursor_moved(float, float)`. The existing signal is unchanged for backward compatibility (amplitude readout still uses it). The new signal carries slice context for linkage.
- Handler in SeismicView connects to `cursor_moved_3d` and receives `(h_value, v_value, slice_type)`
- Converts `(h_value, v_value, slice_type)` + current slice position to `(il, xl, t)` 3D coordinates
- Updates each other panel's crosshair: e.g., if cursor moved on IL panel at (xl=50, t=200ms) while viewing IL 100, then XL panel shows crosshair at (il=100, t=200ms) and T panel shows crosshair at (il=100, xl=50)

**3D sync:**
- 3D view shows a small yellow sphere (GLScatterPlotItem, single point, size=12) at the linked cursor position
- Sphere position updates in real-time with cursor movement (throttled via same 16ms QTimer)

**Edge cases:**
- Arbitrary panel does not emit linkage signals (its coordinate system is non-orthogonal)
- If cursor moves outside the data range of another panel, that panel's crosshair hides

### 4. 3D Click-to-Jump

Clicking a point in the 3D view jumps all profile panels to that location.

**Mechanism:**
- Renderer3D gains `mouseReleaseEvent` handler
- On left-click (not drag), compute 3D position via ray casting through the clicked screen point against the volume bounding box
- Emit `jump_to_position(il_idx, xl_idx, t_idx)` signal
- SeismicView handler: update all three slice sliders → load new slices → update 3D plane positions

**Visual feedback:**
- Brief white flash at the clicked position (fades over 300ms using QTimer)
- Jump marker: a persistent small yellow diamond (separate from the cursor sphere) that shows where the last jump landed

**Threshold:**
- If mouse moved more than 5px between press and release, treat as camera rotation (not a jump). This prevents accidental jumps during 3D navigation.

## Files to Modify

| File | Changes |
|------|---------|
| `geoviz_seismic/profile_vd.py` | Add `_view_rect`, zoom/pan logic, viewport-clipped rendering, `wheelEvent` dispatch (zoom vs shift+slice), `slice_step` signal, enhanced `cursor_moved` with slice_type |
| `geoviz_seismic/profile_widget.py` | Passthrough zoom/pan/reset API to active ProfileVD |
| `geoviz_seismic/seismic_view.py` | Add 3 slice sliders to toolbar, connect `slice_step` signals, implement cursor linkage handler, connect 3D `jump_to_position`, bidirectional slider sync |
| `geoviz_seismic/renderer_3d.py` | Add `jump_to_position` signal, mouse click → ray-box intersection → 3D coordinate mapping, jump marker visual, cursor sphere visual |

## Performance Constraints

- Zoom rendering: only extract and colormap the visible subarray, never the full slice. For a 200x800 slice at 8x zoom, render ~25x100 pixels instead of 200x800.
- Cursor linkage: existing 16ms QTimer throttle is sufficient — no change needed.
- Slice browsing via Shift+wheel: cache miss loads happen synchronously from memory (data is already loaded). For SEGY-on-disk access, the loader reads single traces — fast enough for interactive browsing.
- 3D cursor sphere: single GLScatterPlotItem point, zero GPU overhead.

## Out of Scope

- Arbitrary angle rotation profiles (already have polyline cutting)
- Animated slice browsing (Shift+wheel is sufficient)
- ProfileWiggle zoom/pan (only VD heatmap gets zoom for now — wiggle can follow later)
- Time-depth conversion display
- Multi-SEGY management
- Large-volume streaming/LOD (separate performance spec)
