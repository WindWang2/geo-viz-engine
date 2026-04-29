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
│   ├── Sidebar (4 icon buttons)
│   └── QStackedWidget (4 pages)
│       ├── MapPage        → QWebEngineView + MapLibre GL
│       ├── WellLogPage    → pyqtgraph + QGraphicsScene
│       ├── SeismicPage    → PyVista + VTK
│       └── DataPage       → QTableWidget + file dialogs
├── data/ (loaders, models, cache)
└── renderers/
    ├── well_log/ (curve, lithology, facies, depth, chart_engine)
    ├── map_renderer.py
    └── seismic_renderer.py
```

- **No IPC, no HTTP, no token auth** — all data flows through direct Python function calls within a single process.
- **Data layer**: `src/data/loaders.py` handles lasio (LAS), segyio (SEGY), openpyxl (Excel), and JSON loading. `src/data/models.py` defines Pydantic models. `src/data/cache.py` provides in-memory caching.
- **Well log rendering**: Hybrid approach — pyqtgraph for curve tracks (GPU-accelerated), QGraphicsScene + SVG for lithology and facies tracks. `chart_engine.py` orchestrates multi-track layout and scroll sync.
- **Map**: QWebEngineView embeds MapLibre GL JS. Well click events relay from JS → Qt WebChannel → Python.
- **Seismic**: PyVista Qt interactor renders VTK volumes and slices. Supports SEGY loading via segyio.

## Key Code Patterns

- **Well log chart engine** (modular, data-driven): `src/renderers/well_log/chart_engine.py` — orchestrates multiple track renderers (CurveRenderer, LithologyRenderer, FaciesRenderer, DepthRenderer) in a horizontal layout with QScrollArea. Each renderer is an independent QWidget.
  - 7 column types from legacy engine now mapped to: curves (pyqtgraph), lithology (QGraphicsScene+SVG), facies (QGraphicsScene+SVG), depth (pyqtgraph axis), intervals/description/systems_tract (future)
  - Lithology SVG patterns (6 types): sandstone, siltstone, mudstone, shale, limestone, dolomite — SVG files in `src/patterns/`
  - Sedimentary facies SVG patterns (10 types): tidal_flat, shelf, sand_flat, mud_flat, mixed, clastic_shelf, dolomitic_flat, muddy_shelf, sandy_shelf, sand_mud_shelf
  - Pattern spec: GB/T 勘探管理图件图册编制规范 附录M (岩石图式) + 附录O (沉积相图式)
- **Map well markers**: MapLibre GL renders GeoJSON well features as circles. Click events sent via Qt WebChannel bridge (`MapBridge.onWellClicked`).
- **Seismic rendering**: `SeismicRenderer` wraps `pyvistaqt.QtInteractor`. `load_volume()` for 3D volumes, `add_slice()` for inline/crossline/timeline sections.
- **Data models**: Pydantic `BaseModel` — `WellLogData`, `CurveData`, `LithologyInterval`, `FaciesInterval`, `WellCoordinates`, `SeismicVolumeMeta`.
- **Navigation**: `MainWindow._switch_page(index)` — sidebar buttons are checkable, clicking switches `QStackedWidget` index.
- **Tests**: pytest + pytest-qt. Test files in `tests/`. Qt widget tests use `qtbot` fixture.

## Project Layout

- `src/` — Main application code
  - `main.py` — Entry point (QApplication)
  - `app.py` — MainWindow + sidebar navigation
  - `pages/` — 4 page widgets (map, well_log, seismic, data)
  - `renderers/` — Rendering components
    - `well_log/` — chart_engine, curve/lithology/facies/depth renderers
    - `map_renderer.py` — QWebEngineView + MapLibre
    - `seismic_renderer.py` — PyVista Qt interactor
  - `data/` — loaders, Pydantic models, cache
  - `patterns/` — SVG pattern files (lithology + facies)
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
