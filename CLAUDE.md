# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GeoViz Engine — 地质数据可视化桌面引擎. Single-process desktop app built with PySide6 (Qt for Python). Target users: geological engineers and researchers.

**Previous web architecture** (Tauri + React + FastAPI) is preserved at git tag `v0.1-web`.

## Development Commands

```bash
# Create venv and install dependencies (first time)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run desktop app
source .venv/bin/activate && python -m src.main

# Run tests
source .venv/bin/activate && pytest

# Run tests with verbose output
source .venv/bin/activate && pytest -v

# Build production binary
source .venv/bin/activate && python scripts/build.py
```

## Architecture

```
PySide6 (Qt for Python) — Single Process
├── MainWindow (app.py)
│   ├── Sidebar (7 icon+text buttons)
│   └── QStackedWidget (7 pages)
│       ├── MapPage        → QPainter (via geoviz-map package)
│       ├── PaleoMapPage   → QPainter (via geoviz-paleo-map package)
│       ├── WellLogPage    → ECharts (via geoviz-well-log package)
│       ├── CrossWellPage  → QPainter (via geoviz-cross-well package)
│       ├── SeismicPage    → pyqtgraph OpenGL + CuPy
│       ├── DataPage       → QTableWidget + file dialogs
│       └── ToolsPage      → Standalone utilities (e.g. XML Converter)
├── packages/
│   ├── geoviz-well-log/   → Independent ECharts-based well log visualization engine
│   │   ├── chart_engine.py      → ChartEngine widget (QWebEngineView + Bridge)
│   │   ├── payload_builder.py   → WellLogData → ECharts JSON transforms
│   │   ├── track_manager.py     → Track ordering/visibility/merge/split
│   │   ├── export.py            → SVG/PDF/PNG vector export
│   │   ├── pattern_map.py       → Lithology/Facies → SVG pattern mapping
│   │   ├── models.py            → Pydantic data models
│   │   ├── sync_manager.py      → Multi-well zoom sync
│   │   └── connection_overlay.py → Cross-well correlation polygons
│   ├── geoviz-seismic/    → Independent pyqtgraph-based seismic visualization engine
│   │   ├── renderer_3d.py       → Renderer3D (pyqtgraph GLViewWidget + interactive slice planes)
│   │   ├── seismic_view.py      → SeismicView (3D + 2D profile + toolbar)
│   │   ├── loader.py            → SeismicLoader (segyio on-demand slicing)
│   │   ├── profile_vd.py        → VD heatmap profile rendering
│   │   ├── profile_wiggle.py    → Wiggle trace rendering (QPainter)
│   │   ├── profile_widget.py    → Unified VD/Wiggle switcher
│   │   ├── gpu_ops.py           → CuPy GPU acceleration (optional, NumPy fallback)
│   │   ├── horizon.py           → HorizonParser (nearest/RBF fill)
│   │   ├── colormap.py          → ColormapManager (seismic/gray/jet/hsv)
│   │   ├── cache.py             → SeismicCache (LRU slice cache)
│   │   ├── models.py            → SeismicVolumeMeta, SliceInfo, HorizonData, BinGridGeometry
│   │   └── well_tie_panel.py    → WellTiePanel (wavelet controls, auto-tie, export)
│   ├── geoviz-well-tie/   → Independent well-seismic tie library (pure NumPy)
│   │   ├── calibration.py       → WellTieCalibration (T-D conversion, resample)
│   │   ├── synthetic.py         → Ricker/Ormsby wavelet + synthetic seismogram
│   │   └── auto_tie.py          → auto_tie cross-correlation (shift + CC)
│   ├── geoviz-map/        → Independent QPainter-based geographic map engine
│   │   ├── canvas.py            → MapCanvas (QWidget composite layers)
│   │   ├── projection.py        → Web Mercator (MapLibre-compatible)
│   │   ├── viewport.py          → MapViewport (center+zoom → pixel mapping)
│   │   ├── zoom_pan.py          → ZoomPanHandler (drag pan + wheel zoom)
│   │   └── layers/              → Background, Graticule, GeoJsonPolygon, Reference, Wells
│   └── geoviz-paleo-map/  → Independent QPainter-based paleogeographic map engine
│       ├── canvas.py            → PaleoMapCanvas (QWidget composite of 8 layers)
│       ├── projection.py        → Plate Carrée (identity lng/lat → x/y)
│       ├── viewport.py          → PaleoMapViewport (center+zoom → pixel mapping)
│       ├── zoom_pan.py          → ZoomPanHandler
│       ├── style.py             → FaciesStyleResolver (per-facies brush cache)
│       ├── topology.py          → TopologyModel, TopologyBuilder
│       ├── edit_commands.py     → EditCommand hierarchy, UndoManager
│       ├── edit_engine.py       → EditEngine (selection, drag, CRUD)
│       ├── edit_overlay.py      → EditOverlayLayer
│       ├── save_export.py       → save/export functions
│       └── layers/              → Background, FaciesPolygons, RegionLabels, WellsScatter, Title, NorthArrow, ScaleBar, Legend
│   └── geoviz-cross-well/  → Independent cross-well correlation engine (composes geoviz-well-log)
│       ├── canvas.py            → CrossWellCanvas + PickingOverlay (composes CrossWellWidget)
│       ├── tops_model.py        → FormationTopsModel (CSV I/O, color palette)
│       ├── picks_model.py       → HorizonPicksModel + PicksUndoManager (two-stack undo)
│       ├── correlation_layer.py → CorrelationLayer (bezier tie lines)
│       ├── dtw_engine.py        → DTWEngine (banded DTW with Sakoe-Chiba)
│       └── seismic_tie.py       → SeismicTie (checkshot T-D conversion)
├── src/data/              → (loaders, models, cache, well_registry)
└── src/pages/             → (each page in its own subfolder with renderer/loader)
```

- **No IPC, no HTTP, no token auth** — all data flows through direct Python function calls within a single process.
- **Independent Package**: `geoviz-well-log` is a fully decoupled rendering engine. It contains all data transformation (`payload_builder`), track management (`TrackManager`), vector export (`export`), and rendering (`ChartEngine`) logic. It can be `pip install`-ed and used in any PySide6 project.
- **Independent Package**: `geoviz-seismic` is a fully decoupled seismic visualization engine. It contains 3D volume rendering (`Renderer3D`), SEGY loading (`SeismicLoader`), 2D profile display (`ProfileVD`/`ProfileWiggle`), horizon parsing (`HorizonParser`), and composite widget (`SeismicView`). It can be `pip install`-ed and used in any PySide6 project.
- **Independent Package**: `geoviz-map` is a fully decoupled geographic map engine using only QPainter. Web Mercator projection compatible with MapLibre GL. Layer-based architecture for offline GeoJSON rendering, well markers, reference labels. Can be `pip install`-ed and used in any PySide6 project.
- **Independent Package**: `geoviz-paleo-map` is a fully decoupled paleogeographic map engine using only QPainter. Plate Carrée projection. Per-feature composite SVG pattern fills via `geoviz-well-log.PatternEngine` extensions (`get_composite_brush`, `get_color_fuzzy`). 8 layers: 4 data-driven + 4 chrome. Can be `pip install`-ed and used in any PySide6 project.
- **Independent Package**: `geoviz-cross-well` is a fully decoupled cross-well correlation engine that composes `geoviz_well_log.WellLogCanvas` for rendering. Adds formation tops database (CSV I/O), manual horizon picking with undo/redo (PicksUndoManager), DTW auto-correlation (banded Sakoe-Chiba), bezier correlation ties, and seismic tie (checkshot T-D conversion). Can be `pip install`-ed and used in any PySide6 project.
- **Independent Package**: `geoviz-well-tie` is a pure-NumPy well-seismic tie library with no Qt dependency. Provides Ricker/Ormsby wavelet generation, synthetic seismogram computation, WellTieCalibration (T-D conversion via sonic integration), auto-tie cross-correlation (shift + quality), and seismic grid resampling. Can be `pip install`-ed and used in any Python project.
- **WellLogPage is thin**: Only ~350 lines of UI orchestration. Calls `build_tracks_from_data()` and `TrackManager` from the package. AI prediction business logic (API calls, Excel writing) stays in the page layer.
- **Data layer**: `src/data/loaders.py` handles lasio (LAS), segyio (SEGY), openpyxl (Excel), and JSON loading. `src/data/models.py` defines Pydantic models. `src/data/cache.py` provides in-memory caching. `src/data/well_registry.py` maps well names to loader functions.
- **Well log rendering flow**: `WellLogData` → `build_tracks_from_data()` → track pool → `TrackManager.build_payload()` → JSON → `ChartEngine.render_data()` → ECharts SVG rendering.
- **Map**: Native QPainter via `geoviz-map` package. World/China GeoJSON loaded once at init into cached `QPainterPath` (per-feature in world coords), then painted with a single world→screen `QTransform` per frame. Viewport bbox culling skips off-screen polygons. Well click events emitted via Qt `Signal(str)` (`MapCanvas.well_clicked`).
- **PaleoMap**: Native QPainter via `geoviz-paleo-map` package. Per-feature `FaciesStyle` resolved from facies name → base color + composite QBrush (from PatternEngine). Tooltip hit-test runs bbox prefilter then `QPainterPath.contains`. Tempfile-based GeoJSON middleware is gone — `load_features(features, period_name, wells)` accepts a Python dict directly.
- **Seismic**: pyqtgraph OpenGL renders 3D volumes and slices. Supports SEGY loading via segyio. Well-tie panel (WellTiePanel) toggled from toolbar provides wavelet controls, synthetic trace generation, auto-tie cross-correlation, and T-D calibration export. Synthetic overlay renders as QPainter wiggle trace on ProfileVD. BinGridGeometry maps well XY coordinates to seismic inline/crossline indices.

## Key Code Patterns

- **Package API surface** (`geoviz_well_log/__init__.py`): All public APIs exported — `ChartEngine`, `TrackManager`, `build_tracks_from_data`, `build_ai_prediction_tracks`, `PATTERN_MAP`, `export_dialog`, etc.
- **Track building** (`payload_builder.py`): Pure functions, no Qt dependency. `build_tracks_from_data(data: WellLogData) -> dict[str, dict]` auto-detects converted vs legacy format.
- **Track management** (`track_manager.py`): `TrackManager` wraps a track pool dict. `build_payload(metadata, display_items)` resolves grouped tracks (地层系统, 沉积相) and merged curves into flat JSON.
- **Vector export** (`export.py`): SVG via ECharts `getDataURL({type:'svg'})` — identical to display. PDF via `QWebEngineView.printToPdf()` — vector from same SVG renderer. PNG via `grab()` — raster fallback.
- **Map well markers**: MapLibre GL renders GeoJSON well features as circles. Click events sent via Qt WebChannel bridge (`MapBridge.onWellClicked`).
- **Well selection**: Two paths — map click (`_on_well_clicked`) or combo box in toolbar (`_on_well_selected`). Both call `WellLogPage.load_well()`.
- **Seismic rendering**: `SeismicView` (in `geoviz-seismic` package) combines `Renderer3D` (pyqtgraph GLViewWidget 3D volume + interactive slice planes) with `ProfileWidget` (VD heatmap / Wiggle trace) and toolbar. `SeismicPage` is a thin wrapper (~5 lines) inheriting `SeismicView`. Data transposed from segyio convention `(n_traces, n_samples)` to display convention `(n_samples, n_traces)` before rendering. Optional CuPy GPU acceleration for volume slicing and colormapping.
- **Data models**: Pydantic `BaseModel` — `WellLogData`, `CurveData`, `LithologyInterval`, `FaciesInterval`, `WellCoordinates`. Seismic models (`SeismicVolumeMeta`, `SliceInfo`, `HorizonData`, `BinGridGeometry`) live in `geoviz-seismic` package.
- **Navigation**: `MainWindow._switch_page(index)` — sidebar buttons are checkable, clicking switches `QStackedWidget` index.
- **Tests**: pytest + pytest-qt. Test files in `tests/`. Qt widget tests use `qtbot` fixture.

## Project Layout

- `packages/geoviz_well_log/` — Independent well log visualization package
  - `geoviz_well_log/chart_engine.py` — ChartEngine + Bridge
  - `geoviz_well_log/payload_builder.py` — Data → ECharts JSON transforms
  - `geoviz_well_log/track_manager.py` — Track ordering/visibility/merge/split
  - `geoviz_well_log/export.py` — SVG/PDF/PNG vector export
  - `geoviz_well_log/pattern_map.py` — PATTERN_MAP (lithology/facies → SVG ID)
  - `geoviz_well_log/models.py` — WellLogData, CurveData, etc.
  - `geoviz_well_log/sync_manager.py` — Multi-well zoom sync
  - `geoviz_well_log/connection_overlay.py` — Cross-well correlation overlay
  - `geoviz_well_log/assets/patterns/` — 16 SVG pattern files
  - `geoviz_well_log/web_dist/` — ECharts + custom well-log JS
  - `geoviz_well_log/configs/` — Preset configs (laolong1)
- `packages/geoviz_seismic/` — Independent seismic visualization package
  - `geoviz_seismic/renderer_3d.py` — Renderer3D (pyqtgraph OpenGL 3D + slice planes)
  - `geoviz_seismic/gpu_ops.py` — CuPy GPU acceleration (optional, NumPy fallback)
  - `geoviz_seismic/seismic_view.py` — SeismicView composite widget
  - `geoviz_seismic/loader.py` — SeismicLoader (segyio on-demand slicing)
  - `geoviz_seismic/profile_vd.py` — VD heatmap rendering
  - `geoviz_seismic/profile_wiggle.py` — Wiggle trace rendering (QPainter)
  - `geoviz_seismic/profile_widget.py` — Unified VD/Wiggle switcher
  - `geoviz_seismic/horizon.py` — HorizonParser (nearest/RBF fill)
  - `geoviz_seismic/colormap.py` — ColormapManager (seismic/gray/jet/hsv)
  - `geoviz_seismic/cache.py` — SeismicCache (LRU slice cache)
  - `geoviz_seismic/models.py` — SeismicVolumeMeta, SliceInfo, HorizonData, BinGridGeometry
  - `geoviz_seismic/well_tie_panel.py` — WellTiePanel (wavelet controls, auto-tie, export)
  - `packages/geoviz_well_tie/` — Independent well-seismic tie library (pure NumPy, no Qt)
  - `geoviz_well_tie/calibration.py` — WellTieCalibration (T-D conversion, resample)
  - `geoviz_well_tie/synthetic.py` — Ricker/Ormsby wavelet + synthetic seismogram
  - `geoviz_well_tie/auto_tie.py` — auto_tie cross-correlation (shift + CC)
- `packages/geoviz_map/` — Independent geographic map visualization package
  - `geoviz_map/canvas.py` — MapCanvas (QWidget composite of all layers)
  - `geoviz_map/projection.py` — Web Mercator projection
  - `geoviz_map/viewport.py` — center+zoom → screen pixel mapping
  - `geoviz_map/zoom_pan.py` — Drag pan + cursor-anchored wheel zoom
  - `geoviz_map/layers/` — Background, Graticule, GeoJsonPolygon, ReferenceLabels, Wells
  - `geoviz_map/models.py` — WellMarker, ReferenceLabel
- `packages/geoviz_paleo_map/` — Independent paleogeographic map visualization package
  - `geoviz_paleo_map/canvas.py` — PaleoMapCanvas (8-layer composite)
  - `geoviz_paleo_map/projection.py` — Plate Carrée
  - `geoviz_paleo_map/viewport.py` — center+zoom → screen pixel mapping
  - `geoviz_paleo_map/zoom_pan.py` — Drag pan + cursor-anchored wheel zoom
  - `geoviz_paleo_map/style.py` — FaciesStyleResolver
  - `geoviz_paleo_map/topology.py` — TopologyModel, TopologyBuilder
  - `geoviz_paleo_map/edit_commands.py` — EditCommand hierarchy, UndoManager
  - `geoviz_paleo_map/edit_engine.py` — EditEngine (selection, drag, CRUD)
  - `geoviz_paleo_map/edit_overlay.py` — EditOverlayLayer
  - `geoviz_paleo_map/save_export.py` — save/export functions
  - `geoviz_paleo_map/layers/` — Background, FaciesPolygons, RegionLabels, WellsScatter, Title, NorthArrow, ScaleBar, Legend
- `packages/geoviz_cross_well/` — Independent cross-well correlation package
  - `geoviz_cross_well/canvas.py` — CrossWellCanvas + PickingOverlay (composes CrossWellWidget)
  - `geoviz_cross_well/tops_model.py` — FormationTopsModel (CSV I/O, color palette)
  - `geoviz_cross_well/picks_model.py` — HorizonPicksModel + PicksUndoManager (two-stack undo)
  - `geoviz_cross_well/correlation_layer.py` — CorrelationLayer (bezier tie lines)
  - `geoviz_cross_well/dtw_engine.py` — DTWEngine (banded DTW with Sakoe-Chiba)
  - `geoviz_cross_well/seismic_tie.py` — SeismicTie (checkshot T-D conversion)
- `src/` — Main application code
  - `main.py` — Entry point (QApplication)
  - `app.py` — MainWindow + sidebar navigation
  - `pages/` — Page widgets, each in its own subfolder
    - `map/` — MapPage + MapRenderer
    - `paleo_map/` — PaleoMapPage + PaleoDataLoader
    - `well_log/` — WellLogPage (calls geoviz-well-log package)
    - `cross_well/` — CrossWellPage (uses geoviz-cross-well package)
    - `seismic/` — SeismicPage (thin wrapper around SeismicView)
    - `data/` — DataPage
    - `tools/` — ToolsPage
  - `data/` — loaders, Pydantic models, cache, well_registry
  - `utils/` — constants (re-exports PATTERN_MAP from package)
  - `resources/` — Icons, Qt resource files
- `data/` — Well coordinates JSON, well log Excel, XML data files
- `samples/` — Demo assets and example GeoJSON
- `tests/` — pytest test files
- `scripts/` — build.py (PyInstaller), build_with_conda.bat (Windows)
- `docs/` — Design specs, methodology documents
  - `docs/screenshots/references/` — Reference images (lithology layouts, mockups)
  - `docs/screenshots/qa/` — QA / regression screenshots
  - `docs/releases/` — Per-version release notes
- `archive/` — Retired code kept for reference, not built or imported
  - `archive/scripts/` — Ad-hoc debug/probe scripts from earlier dev cycles
  - `archive/web-echarts/` — Older standalone ECharts web experiment (full Tauri+React+FastAPI architecture lives at git tag `v0.1-web`)
  - `archive/web-deps/` — Leftover `package.json` / `package-lock.json` from the web era
  - `archive/misc/` — Stale one-shot artifacts (`diff.txt`, `.coverage`)

## Development Notes

- **Lithology pattern reference**: SVG patterns follow GB/T 勘探管理图件图册编制规范 附录M (岩石图式).
- **Sedimentary facies patterns**: Based on 附录O (沉积相图式). Carbonate platform facies (潮坪/陆棚/砂坪 etc.) use composite patterns reflecting their lithologic character.
- **pyqtgraph OpenGL**: Uses pyqtgraph.opengl.GLViewWidget (inherits QOpenGLWidget) for 3D seismic rendering. Must be initialized before any QWebEngineView on Windows to avoid GPU context conflicts.
- **QWebEngineView**: Requires `PySide6.QtWebEngineWidgets`. MapLibre GL JS loads from CDN — first load requires internet.
- **Package can be used standalone**: `from geoviz_well_log import ChartEngine, TrackManager, build_tracks_from_data` works without the main app.
- **Seismic package can be used standalone**: `from geoviz_seismic import SeismicView, SeismicLoader, Renderer3D` works without the main app. Optional CuPy acceleration for GPU-accelerated volume slicing. Well-tie panel and synthetic overlay included.
- **Well-tie package can be used standalone**: `from geoviz_well_tie import WellTieCalibration, generate_synthetic_twt, auto_tie_with_quality` works without the main app or Qt. Pure NumPy.

## gstack
Use the /browse skill from gstack for all web browsing.
Available skills: /office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /design-consultation, /design-shotgun, /design-html, /review, /ship, /land-and-deploy, /canary, /benchmark, /browse, /connect-chrome, /qa, /qa-only, /design-review, /setup-browser-cookies, /setup-deploy, /setup-gbrain, /retro, /investigate, /document-release, /codex, /cso, /autoplan, /plan-devex-review, /devex-review, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade, /learn.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore
