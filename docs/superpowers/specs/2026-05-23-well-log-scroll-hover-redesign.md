# Well Log Scrolling & Hover Redesign

## Overview

Redesign the QPainter well log renderer's scrolling and hover/tooltip behavior to match the old ECharts version's UX patterns, while fixing the current broken implementation.

## Problem Statement

The current QPainter renderer has two broken features:

1. **Scrolling**: `QScrollArea` intercepts wheel events for its vertical scrollbar, stealing them from `ZoomPanHandler`. The vertical scrollbar was added as a workaround but creates a conflict — wheel events should always zoom, not scroll.

2. **Hover panel**: The crosshair overlay has coordinate mapping issues — `depth_at_y()` expects canvas-relative Y but receives viewport-relative Y after scroll offset conversion. The hover info panel shows wrong depth values and renders at incorrect positions.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Crosshair line orientation | Horizontal (keep current) | User preference |
| Wheel events | Always zoom (via ZoomPanHandler) | Matches ECharts `dataZoom: 'inside'` behavior |
| Vertical scrollbar | Removed (replaced by depth ruler) | Eliminates wheel event conflict |
| Horizontal scrollbar | Kept (QScrollArea) | Handles track overflow naturally |
| Tooltip style | White semi-transparent panel | User preference |
| Depth reference | Custom depth ruler widget on right edge | Replaces scrollbar, shows depth labels |
| Initial view | Full depth range | User preference |
| Value interpolation | Linear interpolation between depth points | Matches ECharts tooltip behavior |

## Architecture

### Component Overview

```
QPainterWidget (QScrollArea)
├── WellLogCanvas (QWidget) — fills viewport, paints tracks
├── DepthRuler (QWidget) — right edge, depth labels + tick marks
├── _CrosshairOverlayWidget (QWidget) — transparent, paints crosshair + info panel
├── ZoomPanHandler (QObject) — event filter for wheel zoom, drag pan
├── CrosshairOverlay — data model for cursor position, depth calculation, value collection
└── LayoutCoordinator — track layout management
```

### Scrolling Architecture

**No vertical scrollbar.** Vertical navigation is purely depth-range-based:

| Action | Mechanism | Effect |
|--------|-----------|--------|
| Mouse wheel | `ZoomPanHandler._handle_wheel` | Zoom in/out (20% factor), cursor depth stays fixed |
| Middle-drag / Ctrl+drag | `ZoomPanHandler._handle_move` | Pan up/down (depth range shifts) |
| Double-click | `ZoomPanHandler._handle_double_click` | Reset to full depth range |
| Horizontal scroll | QScrollArea scrollbar | Scrolls tracks left/right when wider than viewport |

**Canvas sizing:**
- `setWidgetResizable(True)` — canvas fills viewport height
- `setMinimumWidth(max(total_track_width, viewport_width))` — horizontal overflow handled by QScrollArea
- No `setFixedSize` — canvas height = viewport height

**Wheel event forwarding:**
- `QPainterWidget.wheelEvent` override creates a new `QWheelEvent` in canvas-local coordinates
- Sends via `QApplication.sendEvent(self._canvas, new_event)`
- `ZoomPanHandler` event filter on canvas receives the event and handles zoom
- QScrollArea never consumes wheel events for scrolling

### Depth Ruler

New `DepthRuler` widget on the right edge of the viewport.

**Layout:**
- Width: 50px fixed
- Height: matches viewport height
- Background: `#f8fafc`
- Left border: 2px solid `#cbd5e1`

**Content:**
- Depth labels at regular intervals
- Tick marks on left edge (6px wide, `#94a3b8`)
- Cursor depth indicator: highlighted band at current mouse depth

**Smart label spacing:**
- Compute ideal interval from `(depth_span / viewport_height) * target_pixel_spacing`
- Round to nice numbers: 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000
- At full range (0-3000m): labels every 500m
- At zoomed range (1000-1100m): labels every 10m

**Data flow:**
1. `CrosshairOverlay` stores canvas-relative cursor Y and computes depth via `depth_at_y()`
2. `QPainterWidget._on_mouse_moved` calls `CrosshairOverlay.depth_at_y(canvas_y)` to get depth
3. `DepthRuler` receives depth value via signal, maps depth to viewport Y position for indicator
4. `DepthRuler.paintEvent` draws labels, ticks, and cursor indicator at the mapped Y position

### Hover/Crosshair

**Crosshair line:**
- Horizontal dashed line at cursor Y position (viewport-relative)
- Color: `#ef4444`, style: `DashLine`, width: 1px
- Spans full width of track area (excluding depth ruler)

**Info panel:**
- White semi-transparent background (`rgba(255,255,255,0.92)`)
- Border: `1px solid #94a3b8`, rounded corners (6px)
- Shadow: `0 2px 8px rgba(0,0,0,0.1)`
- Position: follows cursor Y, clamped to viewport bounds
- First line: `深度: X.X m` (bold, with bottom border separator)
- Subsequent lines: `{curve_name}: {value}` — values colored by curve color

**Value interpolation:**
- For `CurveTrack`: linear interpolation between adjacent depth points
  - Find bracketing depths via `bisect_left`
  - Lerp: `value = v0 + (target_depth - d0) / (d1 - d0) * (v1 - v0)`
- For interval tracks (lithology/facies): no interpolation (categorical, nearest match)

**Coordinate mapping:**
- `cursor_y` stored as canvas-relative Y (for `depth_at_y` calculation)
- `paint_overlay` receives `scroll_offset` parameter, converts to viewport Y for rendering
- With no vertical scrollbar: `scroll_offset = 0`, so `canvas_y == viewport_y`

## Files to Modify

| File | Change |
|------|--------|
| `packages/geoviz_well_log/geoviz_well_log/renderer/depth_ruler.py` | **NEW** — DepthRuler widget |
| `packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py` | Add linear interpolation to `_collect_values` |
| `packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py` | Add `depth_range_changed` signal forwarding |
| `packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py` | Export DepthRuler |
| `packages/geoviz_well_log/geoviz_well_log/__init__.py` | Export DepthRuler |
| `src/pages/well_log/qpainter_widget.py` | Remove vertical scrollbar, add DepthRuler, fix wheelEvent, simplify canvas sizing |

## Testing

- All existing 213 tests must pass
- Manual verification: wheel zoom works, depth ruler shows labels, hover panel shows correct depth
- Test depth ruler label spacing at different zoom levels
- Test hover panel value interpolation for curve tracks
