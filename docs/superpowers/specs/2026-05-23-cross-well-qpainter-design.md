# Cross-Well QPainter Migration Design

## Goal

Migrate the cross-well comparison page from ECharts (ChartEngine/QWebEngineView) to QPainter rendering, matching the single-well architecture. Add well reordering, depth ruler, crosshair, and per-well track control.

## Architecture

```
CrossWellPage (QVBoxLayout)
├── Toolbar (QHBoxLayout)
│   ├── Add Well (QMenu)
│   ├── Auto Link / Manual Link buttons
│   ├── Flatten combo (depth / TVDSS / marker)
│   ├── Clear All / Export buttons
│   └── Per-well track config button
├── QScrollArea (horizontal)
│   └── Container QWidget (QHBoxLayout)
│       ├── WellLogCanvas_1
│       ├── WellLogCanvas_2
│       ├── ...
│       └── WellLogCanvas_N
├── ConnectionOverlay (transparent, paints correlation polygons)
├── DepthRuler (right edge, shared)
└── LocationMapWidget (bottom-left, mini-map)
```

Each well is a standalone `WellLogCanvas` with its own `set_tracks()` — same API as single-well. The container is a plain QWidget with QHBoxLayout holding the canvases with spacing for correlation polygons.

## Data Flow

Well data loading is unchanged — `get_well_data()` returns `WellLogData`.

Per-well rendering pipeline:
1. `WellLogData` → `build_qpainter_tracks(data)` → `list[BaseTrack]` (existing builder)
2. `canvas.set_tracks(tracks)` (existing API)
3. `canvas.paintEvent()` renders via QPainter

Cross-well orchestration:
1. Load well data → cache in `_well_data_cache[well_name]`
2. For each well: `build_qpainter_tracks()` → `canvas.set_tracks()`
3. Sync depth ranges via `QPainterSyncManager`
4. Compute correlation links → `ConnectionOverlay.set_links()`

Per-well track control: each canvas has independent track visibility/order state. Toggling a track re-runs `build_qpainter_tracks()` with filtered subset for that canvas only.

## Correlation Polygons

`ConnectionOverlay` is a transparent QWidget on the container, painting polygons between adjacent wells.

Polygon vertices:
- Source left/right edges = source canvas x position and width in container
- Target left/right edges = target canvas x position and width
- Y positions = depth → pixel using each canvas's depth range and header height

Polygon color follows existing logic: facies-based (yellow=delta/channel, orange=marine, blue=lake, green=fan/beach). Manual links use red.

Auto-link algorithm unchanged: match interval names across adjacent wells at sequence → member → formation levels.

Links refresh on: well add/remove/reorder, canvas resize, scroll, link add/remove.

## Interactions

### Zoom/Pan Sync

`QPainterSyncManager` replaces the JS-based `SyncManager`:

- Connects to each canvas's `depth_range_changed` signal
- When one canvas changes range, updates all others
- `_is_syncing` flag prevents infinite recursion

### Well Reordering

Drag-and-drop on well headers in the container widget:

- `QDragEnterEvent` / `QDropEvent` on container
- `QMimeData` carries well name
- On drop: reorder canvases in layout, rebuild polygon coordinates, update auto-link associations

### Per-well Track Control

Each canvas header has a config button (gear icon). Clicking opens a popup with checkboxes for each track type (depth, curves, lithology, facies, systems tract, etc.). Toggling calls `canvas.set_tracks()` with filtered subset.

### Crosshair

When hovering any canvas, a shared crosshair line is drawn across all canvases at the same depth. Each canvas has its own `CrosshairOverlay` instance sharing the same cursor depth value. The `CrosshairOverlay.depth_at_y()` maps Y to depth; all canvases use the same depth range, so the line aligns.

## Export

Vector export uses `export_qpainter` module directly:

1. Create a `QPicture` or `QImage` target
2. Paint each canvas at its computed x-offset
3. Paint correlation polygons on top
4. Paint depth ruler on right edge
5. Export composite result as SVG/PDF/PNG

Replaces the current ECharts SVG extraction + stitching approach.

## Files to Create/Modify

### New files
- `packages/geoviz_well_log/geoviz_well_log/cross_well_page.py` — Cross-well page widget (replaces `src/pages/cross_well/page.py`)
- `packages/geoviz_well_log/geoviz_well_log/painter_sync_manager.py` — QPainter-based zoom sync

### Modified files
- `packages/geoviz_well_log/geoviz_well_log/renderer/connection_overlay.py` — Adapt for QPainter canvases (coordinate mapping)
- `packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py` — Add crosshair property (already done)
- `packages/geoviz_well_log/geoviz_well_log/__init__.py` — Export new classes
- `src/pages/cross_well/page.py` — Thin wrapper calling package

### Removed (replaced)
- `packages/geoviz_well_log/geoviz_well_log/sync_manager.py` — JS-based sync replaced by `painter_sync_manager.py`
- `packages/geoviz_well_log/geoviz_well_log/location_map.py` — Reintegrated into new page

## Testing

- Unit tests for `QPainterSyncManager` (signal-based sync, recursion guard)
- Unit tests for `ConnectionOverlay` polygon vertex computation
- Integration test: render 2-well section, verify polygon painting
- Visual test: compare QPainter output with existing ECharts output for same data
