# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

GeoViz Engine — 地质数据可视化桌面引擎. Three-layer desktop app: Tauri 2.x (Rust) shell + React 18 frontend + Python FastAPI backend. Target users: geological engineers and researchers.

## Development Commands

```bash
# Frontend dev server (port 5173)
cd src-web && npm run dev

# Python backend (port 8000)
cd src-python && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Full desktop app (Python + Vite + Tauri)
./scripts/dev.sh

# Production build
./scripts/build.sh

# Frontend tests
cd src-web && npm test              # run once
cd src-web && npm run test:watch    # watch mode
cd src-web && npm run test:coverage # with coverage

# Python tests
cd src-python && source venv/bin/activate && pytest

# Rust check
cd src-tauri && cargo check

# Frontend lint (no separate lint command — tsc + vitest cover it)
cd src-web && npx tsc --noEmit
```

## Architecture

```
Tauri (Rust) ──WebView──> React (TypeScript) ──HTTP+JSON──> FastAPI (Python)
     │                          │                                 │
  token gen              D3.js + MapLibre GL                  numpy, lasio
  sidecar mgmt           Zustand stores                     Pydantic models
```

- **Security**: Tauri generates 32-char random API token at startup, injects via env var. All API calls need `X-API-Token` header. Auth validated by `AuthTokenMiddleware` in `src-python/app/auth.py`.
- **Frontend→Backend**: `src-web/src/hooks/useApi.ts` handles all HTTP calls with token from Tauri invoke or `.env.development`.
- **State**: Zustand stores in `src-web/src/stores/` (useWellStore, useSettingsStore, useMapStore).
- **Routing**: `src-web/src/router.tsx` — nested layout routes under AppLayout. Key pages: `/` (dashboard), `/well-log` (map+table), `/laolong1` (D3 chart), `/map` (map with star markers), `/well-detail/:wellName` (well detail with data/chart tabs).

## Key Code Patterns

- **Well log chart engine** (modular, config-driven): `src-web/src/components/well-log/engine/` — generic D3.js + SVG rendering engine accepting `WellLogData` + `ChartConfig`. `LaoLong1Chart.tsx` is now a thin wrapper passing `laolong1Config` from `configs/laolong1.ts`.
  - Engine modules: `WellLogChart.tsx` (component), `renderers.ts` (8 draw functions), `patterns.ts` (16 SVG patterns + lookup), `interaction.ts` (crosshair + tooltip), `export.ts` (SVG/PNG/PDF), `utils.ts` (interpolation, text wrap, coords), `types.ts` (Config types)
  - 7 column types: `intervals`, `curves`, `depth`, `lithology`, `description`, `facies`, `systems_tract`
  - Lithology SVG patterns (6 types): sandstone, siltstone, mudstone, shale, limestone, dolomite — SVG files in `src-web/src/components/well-log/patterns/`
  - Sedimentary facies SVG patterns (10 types): tidal_flat, shelf, sand_flat, mud_flat, mixed, clastic_shelf, dolomitic_flat, muddy_shelf, sandy_shelf, sand_mud_shelf
  - SVG viewBox height: `bodyStart(120) + gridHeight + 2` where bodyStart = titleOffset(40) + HEADER_TOTAL(80)
  - Methodology doc: `docs/methodology-well-log-visualization.md`
- **Map star markers**: `src-web/src/components/map/WellMap.tsx` uses MapLibre GL with `ImageData` (Uint8Array) star icons. Red stars for wells with data (LaoLong1), gray for others. Click red star → navigate to well detail page.
- **Well detail page**: `src-web/src/pages/WellDetailPage.tsx` — two tabs (Data table + Chart). Route: `/well-detail/:wellName`.
- **Data loading**: `src-python/app/services/laolong1_loader.py` parses 11 Excel sheets for real well log data. `data_generator.py` creates synthetic well data.
- **Map**: `src-web/src/components/map/WellMap.tsx` uses MapLibre GL. Well coordinates converted from EPSG:2436 to WGS84 via `scripts/convert_coordinates.py`. 57 wells in `data/well_coordinates.json`.
- **i18n**: `src-web/src/i18n/` with en.json/zh.json. Use i18next keys for all user-facing strings.
- **Tests**: Frontend uses vitest + @testing-library/react with Tauri API mocks in `src-web/src/__mocks__/`. Python uses pytest with fixtures in `conftest.py`.

## Monorepo Layout

- `src-tauri/` — Rust/Tauri desktop shell (window, sidecar, token)
- `src-web/` — React + Vite + TypeScript frontend
- `src-python/` — FastAPI backend with venv
- `scripts/` — dev.sh, build.sh, coordinate conversion
- `data/` — well_coordinates.json (57 wells), design reference, generated data
- `docs/` — methodology document, design references

## Development Notes

- **Port conflicts**: Default backend port 8000 may be occupied (CLodop print service). Use port 8002 via `.env.development` `VITE_API_BASE_URL=http://localhost:8002`.
- **Lithology pattern reference**: SVG patterns follow GB/T 勘探管理图件图册编制规范 附录M (岩石图式). Standalone SVGs saved in `patterns/` directory.
- **Sedimentary facies patterns**: Based on 附录O (沉积相图式). Carbonate platform facies (潮坪/陆棚/砂坪 etc.) use composite patterns reflecting their lithologic character.
