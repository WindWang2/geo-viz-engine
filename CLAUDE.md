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
│   ├── Sidebar (6 icon+text buttons)
│   └── QStackedWidget (6 pages)
│       ├── MapPage        → QWebEngineView + MapLibre GL
│       ├── WellLogPage    → ECharts (via geoviz-well-log package)
│       ├── CrossWellPage  → Multi-ECharts + Correlation Polygons
│       ├── SeismicPage    → PyVista + VTK
│       ├── DataPage       → QTableWidget + file dialogs
│       └── ToolsPage      → Standalone utilities (e.g. XML Converter)
├── packages/
│   └── geoviz-well-log/   → Independent ECharts-based well log visualization engine
│       ├── chart_engine.py      → ChartEngine widget (QWebEngineView + Bridge)
│       ├── payload_builder.py   → WellLogData → ECharts JSON transforms
│       ├── track_manager.py     → Track ordering/visibility/merge/split
│       ├── export.py            → SVG/PDF/PNG vector export
│       ├── pattern_map.py       → Lithology/Facies → SVG pattern mapping
│       ├── models.py            → Pydantic data models
│       ├── sync_manager.py      → Multi-well zoom sync
│       └── connection_overlay.py → Cross-well correlation polygons
├── src/data/              → (loaders, models, cache, well_registry)
└── src/pages/             → (Page UI implementations)
```

- **No IPC, no HTTP, no token auth** — all data flows through direct Python function calls within a single process.
- **Independent Package**: `geoviz-well-log` is a fully decoupled rendering engine. It contains all data transformation (`payload_builder`), track management (`TrackManager`), vector export (`export`), and rendering (`ChartEngine`) logic. It can be `pip install`-ed and used in any PySide6 project.
- **WellLogPage is thin**: Only ~350 lines of UI orchestration. Calls `build_tracks_from_data()` and `TrackManager` from the package. AI prediction business logic (API calls, Excel writing) stays in the page layer.
- **Data layer**: `src/data/loaders.py` handles lasio (LAS), segyio (SEGY), openpyxl (Excel), and JSON loading. `src/data/models.py` defines Pydantic models. `src/data/cache.py` provides in-memory caching. `src/data/well_registry.py` maps well names to loader functions.
- **Well log rendering flow**: `WellLogData` → `build_tracks_from_data()` → track pool → `TrackManager.build_payload()` → JSON → `ChartEngine.render_data()` → ECharts SVG rendering.
- **Map**: QWebEngineView embeds MapLibre GL JS. Well click events relay from JS → Qt WebChannel → Python.
- **Seismic**: PyVista Qt interactor renders VTK volumes and slices. Supports SEGY loading via segyio.

## Key Code Patterns

- **Package API surface** (`geoviz_well_log/__init__.py`): All public APIs exported — `ChartEngine`, `TrackManager`, `build_tracks_from_data`, `build_ai_prediction_tracks`, `PATTERN_MAP`, `export_dialog`, etc.
- **Track building** (`payload_builder.py`): Pure functions, no Qt dependency. `build_tracks_from_data(data: WellLogData) -> dict[str, dict]` auto-detects converted vs legacy format.
- **Track management** (`track_manager.py`): `TrackManager` wraps a track pool dict. `build_payload(metadata, display_items)` resolves grouped tracks (地层系统, 沉积相) and merged curves into flat JSON.
- **Vector export** (`export.py`): SVG via ECharts `getDataURL({type:'svg'})` — identical to display. PDF via `QWebEngineView.printToPdf()` — vector from same SVG renderer. PNG via `grab()` — raster fallback.
- **Map well markers**: MapLibre GL renders GeoJSON well features as circles. Click events sent via Qt WebChannel bridge (`MapBridge.onWellClicked`).
- **Well selection**: Two paths — map click (`_on_well_clicked`) or combo box in toolbar (`_on_well_selected`). Both call `WellLogPage.load_well()`.
- **Seismic rendering**: `SeismicRenderer` wraps `pyvistaqt.QtInteractor`. `load_volume()` for 3D volumes, `add_slice()` for inline/crossline/timeline sections.
- **Data models**: Pydantic `BaseModel` — `WellLogData`, `CurveData`, `LithologyInterval`, `FaciesInterval`, `WellCoordinates`, `SeismicVolumeMeta`.
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
- `src/` — Main application code
  - `main.py` — Entry point (QApplication)
  - `app.py` — MainWindow + sidebar navigation
  - `pages/` — Page widgets (map, well_log, cross_well, seismic, data, tools)
  - `renderers/` — Rendering components (map, seismic, paleo_map)
  - `data/` — loaders, Pydantic models, cache, well_registry
  - `utils/` — constants (re-exports PATTERN_MAP from package)
  - `resources/` — Icons, Qt resource files
- `data/` — Well coordinates JSON, well log Excel, XML data files
- `tests/` — pytest test files
- `scripts/` — build.py (PyInstaller)
- `docs/` — Design specs, methodology documents

## Development Notes

- **Lithology pattern reference**: SVG patterns follow GB/T 勘探管理图件图册编制规范 附录M (岩石图式).
- **Sedimentary facies patterns**: Based on 附录O (沉积相图式). Carbonate platform facies (潮坪/陆棚/砂坪 etc.) use composite patterns reflecting their lithologic character.
- **PyVista offscreen**: On headless CI, set `PYVISTA_OFFSCREEN=true`. For local dev, PyVista uses Qt interactor directly.
- **QWebEngineView**: Requires `PySide6.QtWebEngineWidgets`. MapLibre GL JS loads from CDN — first load requires internet.
- **Package can be used standalone**: `from geoviz_well_log import ChartEngine, TrackManager, build_tracks_from_data` works without the main app.

## gstack
Use the /browse skill from gstack for all web browsing.
Available skills: /office-hours, /plan-ceo-review, /plan-eng-review, /plan-design-review, /design-consultation, /design-shotgun, /design-html, /review, /ship, /land-and-deploy, /canary, /benchmark, /browse, /connect-chrome, /qa, /qa-only, /design-review, /setup-browser-cookies, /setup-deploy, /setup-gbrain, /retro, /investigate, /document-release, /codex, /cso, /autoplan, /plan-devex-review, /devex-review, /careful, /freeze, /guard, /unfreeze, /gstack-upgrade, /learn.
