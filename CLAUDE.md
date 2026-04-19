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
- **Routing**: `src-web/src/router.tsx` — nested layout routes under AppLayout. Key pages: `/` (dashboard), `/well-log` (map+table), `/laolong1` (D3 chart).

## Key Code Patterns

- **Well log charts**: D3.js + SVG rendering in `src-web/src/components/well-log/LaoLong1Chart.tsx`. Uses `<clipPath>` per column, `getScreenCTM()` for coordinate conversion, event namespace `.laolong1` to avoid conflicts.
- **Data loading**: `src-python/app/services/laolong1_loader.py` parses 11 Excel sheets for real well log data. `data_generator.py` creates synthetic well data.
- **Map**: `src-web/src/components/map/WellMap.tsx` uses MapLibre GL. Well coordinates converted from EPSG:2436 to WGS84 via `scripts/convert_coordinates.py`.
- **i18n**: `src-web/src/i18n/` with en.json/zh.json. Use i18next keys for all user-facing strings.
- **Tests**: Frontend uses vitest + @testing-library/react with Tauri API mocks in `src-web/src/__mocks__/`. Python uses pytest with fixtures in `conftest.py`.

## Monorepo Layout

- `src-tauri/` — Rust/Tauri desktop shell (window, sidecar, token)
- `src-web/` — React + Vite + TypeScript frontend
- `src-python/` — FastAPI backend with venv
- `scripts/` — dev.sh, build.sh, coordinate conversion
- `data/` — well_coordinates.json, design reference, generated data
