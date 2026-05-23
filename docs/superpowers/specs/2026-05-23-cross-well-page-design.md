# CrossWellPage Design Spec

> **Date:** 2026-05-23
> **Status:** Approved

## Goal

Implement the `CrossWellPage` (连井对比) — a fully functional application page that lets users select multiple wells, display them side-by-side with synchronized depth, and create correlation links between wells.

## Current State

- **Library layer** (`geoviz_well_log`): `CrossWellWidget` is complete — multi-canvas container with depth sync, auto/manual linking, connection overlay, and composite vector export.
- **Data layer** (`src/data/`): `well_registry.py` provides `list_wells()`, `get_well_data()`. `loaders.py` handles Excel → `WellLogData` conversion.
- **App layer** (`src/pages/cross_well/page.py`): 7-line stub — `class CrossWellPage(CrossWellWidget): pass`

## Scope

Full-featured page with:
1. Multi-well selection dialog
2. Async data loading (QThread)
3. Auto-correlation linking
4. Manual correlation linking (toggle mode)
5. Per-well track visibility control (context menu)
6. Composite vector export (SVG/PDF/PNG)
7. Clear all wells

## Architecture

Single file replaces the stub: `src/pages/cross_well/page.py` (~300 lines). No new files needed — the library provides all rendering and interaction logic.

```
CrossWellPage (QWidget)
├── _toolbar (QWidget)
│   ├── "添加井" QPushButton → _WellSelectDialog
│   ├── "自动连井" QPushButton → auto_link()
│   ├── "手动连井" QPushButton (checkable) → toggle_manual_link()
│   ├── "清除" QPushButton → clear_all()
│   └── "导出" QPushButton → QFileDialog → export_composite()
├── CrossWellWidget (inherited from library)
│   ├── QScrollArea → QHBoxLayout
│   │   ├── WellLogCanvas × N
│   │   └── stretch
│   ├── ConnectionOverlay
│   ├── QPainterSyncManager
│   └── DepthRuler
├── _load_thread (QThread, background)
└── _placeholder (QLabel, empty state)
```

## Components

### 1. Well Selection Dialog (`_WellSelectDialog`)

- `QDialog` with `QListWidget` (checkable items)
- Items populated from `list_wells()` (sorted)
- OK / Cancel buttons
- Returns `list[str]` of selected well names
- No multi-select mode on the list itself — use checkmarks instead (consistent with Qt conventions)

### 2. Data Loader Thread (`_WellLoadWorker`)

- `QObject` subclass with `run()` method
- Input: `list[str]` well names
- For each well:
  1. Call `get_well_data(well_name)` → `(loader_fn, xls_path, config)`
  2. Call `loader_fn(xls_path, well_name=well_name)` → `WellLogData`
  3. Call `build_qpainter_tracks(data)` → list of tracks
  4. Create `WellLogCanvas`, call `set_tracks(tracks)`
  5. Emit `progress(i, name)` after each well
- Output signal: `finished(list[WellLogCanvas])`
- Error signal: `error(str)`

### 3. Toolbar

Styled identically to `WellLogPage` toolbar (same background, border, spacing).

Buttons:
| Button | Style | Action |
|--------|-------|--------|
| 添加井 | Default (outlined) | Opens `_WellSelectDialog` |
| 自动连井 | Default | Calls `auto_link()` on widget |
| 手动连井 | Checkable toggle | Calls `toggle_manual_link()` |
| 清除 | Danger (red-ish) | Calls `clear_all()`, resets state |
| 导出 | Primary (blue) | QFileDialog → `export_composite()` |

### 4. Empty State

When `canvas_count == 0`, show a centered placeholder label:
```
点击"添加井"开始对比
```

When wells are loaded, hide the placeholder.

### 5. Track Visibility (Context Menu)

Right-click on a `WellLogCanvas` shows a context menu listing all tracks with checkmarks. Toggling a check calls `set_track_visible(canvas, index, visible)`.

Implementation: Override `contextMenuEvent` on `CrossWellPage`. Build menu from `canvas.tracks` list.

## Data Flow

```
1. User clicks "添加井"
2. _WellSelectDialog opens, user checks HZ25-10-1, 老龙1, clicks OK
3. _WellLoadWorker created, moved to QThread
4. Worker loads each well sequentially (Excel → WellLogData → tracks → canvas)
5. Progress signal updates toolbar status or progress dialog
6. finished signal → main thread iterates result:
   - For first canvas: store reference for depth ruler init
   - Call add_canvas(canvas, well_name) for each
7. DepthRuler auto-syncs to first canvas's depth range
8. ConnectionOverlay auto-updates geometry
```

## Error Handling

- If `get_well_data()` returns `None` for a well, skip it and continue with others
- If `loader_fn()` raises, catch and skip, continue loading remaining wells
- If all wells fail to load, show `QMessageBox.warning`
- If no wells are selected in dialog, do nothing (dialog just closes)

## Testing

- Unit test `_WellSelectDialog` returns correct selection
- Unit test `_WellLoadWorker` signal emission (mock loaders)
- Unit test toolbar button enable/disable states based on `canvas_count`
- Unit test empty state visibility toggle
- Integration test: load well, verify canvas added to widget
