# Paleogeography Map Enhancement Design

**Date:** 2026-05-11
**Scope:** Visual quality and functional improvements for the paleogeography map page
**Approach:** Enhance existing ECharts renderer (bundled locally)

---

## Background

The paleo map feature (shipped v0.3.0) renders GeoJSON polygons with SVG facies pattern fills using ECharts 5.x inside a `QWebEngineView`. Current capabilities: drag-and-drop GeoJSON loading, pan/zoom, hover tooltips, PNG export. 16 SVG patterns covering common Chinese geological facies.

Target users: geological researchers preparing paleogeographic maps for publications and presentations.

---

## Design Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Rendering engine | Keep ECharts, bundle locally | Least disruptive, leverages well log export pattern, ECharts handles the feature set |
| Offline support | Bundle `echarts.min.js` (~1MB) in `src/resources/js/` | Must work without internet |
| Color palette | Muted pastels on light background | Better for print/publication, SVG patterns more visible on lighter fills |
| Label style | Inline bold, auto-positioned at polygon centroid | Simple, most common in Chinese geological maps |
| Legend style | Pattern swatches + boundary line types + well marker | Full publication legend |
| Data format | GeoJSON (existing) + CSV/Excel (new) | Researchers have both formats |
| Multi-period | Period-tagged feature dict, toolbar dropdown | Users flip between epochs in one session |
| Compare mode | Split-screen QSplitter with two ECharts instances | Side-by-side period comparison |
| Export | SVG + PDF + PNG | SVG via `getDataURL`, PDF via `printToPdf`, PNG via `grab()` |

---

## Components

### 1. Bundled ECharts

Ship `echarts.min.js` (v5.5.x, ~1MB) in `src/resources/js/`. The HTML template in `paleo_map_renderer.py` references it via `file://` URL instead of CDN. No functional changes to ECharts configuration — same `registerMap` + `type: 'map'` series approach.

### 2. PaleoDataLoader (`src/data/paleo_loader.py`)

Pure data transformation module (no Qt dependency). Handles:

- **CSV/Excel input**: Accepts `.csv` and `.xlsx` files with columns:
  - `period` (str): Geological time period name (e.g. "奥陶纪特马豆克期")
  - `facies` (str): Facies keyword matching `PATTERN_MAP` (e.g. "砂质陆棚")
  - `boundary_type` (str, optional): One of `confirmed`, `inferred`, `fault`
  - `geometry` (str, optional): WKT polygon string
  - Or simplified columns: `lon_min`, `lon_max`, `lat_min`, `lat_max` for rectangular polygons
  - `name` (str, optional): Display name for the feature

- **GeoJSON input**: Existing flow unchanged. New optional properties recognized:
  - `boundary_type`: Line style for the feature's border
  - `period`: Time period tag (enables multi-period if multiple periods exist)

- **Output**: `dict[str, list[dict]]` keyed by period name. Each value is a list of GeoJSON-style features.

- **Auto-detection**: File extension + column header check routes to appropriate parser. Invalid formats produce a clear error message with expected column schema.

### 3. Multi-Period Management

`PaleoMapPage` stores a `dict[str, list[Feature]]` mapping period names to feature lists. Loading behavior:

- Loading a single-period GeoJSON (no `period` property): all features go under one entry named from the file's `title` property or filename.
- Loading a multi-period GeoJSON (features have `period` property): features grouped by period.
- Loading a CSV: features grouped by the `period` column.
- Loading additional files merges into the existing dict (new periods added, existing periods replaced if same name).

The toolbar dropdown lists all loaded period names. Selecting a period calls `paleo_map_renderer.set_period(period_name)` which updates the ECharts chart via `setOption()` without full page reload.

### 4. Enhanced Renderer (`src/renderers/paleo_map_renderer.py`)

**4.1 Color Palette**

A `FACIES_COLORS` dict maps each facies keyword to a muted pastel color. New property added to `pattern_map.py`. Example mapping:

| Facies | Color | Category |
|--------|-------|----------|
| 砂岩 | `#f0d9b5` | Clastic |
| 粉砂岩 | `#e6c9a8` | Clastic |
| 泥岩 | `#d4c5a9` | Clastic |
| 页岩 | `#c9bfa0` | Clastic |
| 灰岩 | `#b5d4c1` | Carbonate |
| 白云岩 | `#a8cdb8` | Carbonate |
| 砂质陆棚 | `#f0d9b5` | Shelf |
| 泥质陆棚 | `#d4c5a9` | Shelf |
| 三角洲 | `#e6c9a8` | Deltaic |
| 深水盆地 | `#9bb5cf` | Deep water |
| 碳酸盐台地 | `#b5d4c1` | Carbonate platform |

Colors are the base fill. SVG patterns overlay on top with adjustable opacity.

**4.2 Facies Pattern Rendering**

The current approach (base64 data URIs for SVG patterns injected into HTML) is preserved but enhanced:

- Pattern fill opacity is configurable via `fill-opacity` on the SVG pattern element.
- A JS function applies the pattern as a Canvas pattern fill on top of the base color.
- ECharts `itemStyle.areaColor` uses the base color; the pattern is overlaid via a custom `renderItem` function (ECharts custom series) for per-feature pattern control integrated with the map coordinate system.

**4.3 Polygon Labels**

ECharts `label` config on the map series:

```javascript
label: {
  show: true,
  formatter: '{b}',
  fontSize: 12,
  fontWeight: 'bold',
  color: autoContrast(featureColor) // dark text on light fills, light on dark
}
```

Auto-contrast: compute luminance from the RGB values. If luminance > 0.5, use dark text (`#2d3748`); else use light text (`#f7fafc`).

Labels can be toggled on/off via a toolbar button. When toggled off, labels hide via `setOption` update.

**4.4 Boundary Line Styles**

Each feature's `boundary_type` property maps to an ECharts `itemStyle`:

| boundary_type | borderColor | borderWidth | borderType |
|---------------|-------------|-------------|------------|
| `confirmed` | `#555555` | 1.5 | `solid` |
| `inferred` | `#555555` | 1.5 | `dashed` (6,3) |
| `fault` | `#e53e3e` | 2.0 | `solid` |
| default (none) | `#555555` | 1.0 | `solid` |

Applied via ECharts `data[i].itemStyle` per-feature configuration.

**4.5 Well Marker Overlay**

A second ECharts series (`type: 'scatter'`) overlaid on the map. Data sourced from the existing `data/well_coordinates.json`. Each point:

```javascript
{
  type: 'scatter',
  coordinateSystem: 'geo',
  data: wells.map(w => ({
    name: w.name,
    value: [w.longitude, w.latitude],
    itemStyle: { color: '#e53e3e', borderColor: '#fff', borderWidth: 2 }
  })),
  symbolSize: 8,
  label: { show: true, formatter: '{b}', position: 'right', fontSize: 10 }
}
```

Well overlay can be toggled on/off via toolbar button. Only wells within the current map's coordinate extent are shown.

**4.6 Legend**

Custom HTML legend positioned bottom-right. Not ECharts' built-in legend (too limited for pattern display). Built as a floating `<div>` containing:

- **Facies entries**: For each distinct facies in the current map, show a small rectangle filled with the actual pattern (base color + SVG pattern). Facies name next to it.
- **Boundary types**: Line samples (solid, dashed, red fault).
- **Well marker**: Red circle with white border.

Legend is regenerated each time the map data changes.

**4.7 Map Dress-up**

- **Title**: Centered `<div>` above the ECharts canvas. Content: `{period}岩相古地理图` or custom title from GeoJSON `properties.title`. Font: 16px bold.
- **North arrow**: SVG element positioned top-right. Simple arrow + "N" label.
- **Scale bar**: SVG element positioned bottom-left. Length computed from the coordinate extent of the current map data. Shows distance in km.
- **Coordinate grid**: Optional lat/lon grid lines rendered as ECharts `graphic` lines. Grid interval auto-computed from extent (e.g., every 1°, 2°, or 5° depending on zoom). Labels on edges. Toggle on/off via toolbar.

All dress-up elements are included in SVG/PDF export (they're part of the HTML page).

### 5. Compare Mode

A toolbar button toggles compare mode. Implementation:

- The `PaleoMapPage` layout switches from a single `PaleoMapRenderer` to a `QSplitter` containing two renderers.
- Each renderer is an independent `PaleoMapRenderer` instance with its own ECharts.
- Two dropdowns above the splitter let users pick period A (left) and period B (right).
- Toggling compare mode off restores the single renderer.
- The toolbar export button exports the currently focused panel (left or right).

### 6. Export Dialog

A `QDialog` with format options:

- **SVG**: Calls ECharts `getDataURL({type: 'svg'})` via `page().runJavaScript()`. Composites the HTML dress-up elements (title, north arrow, scale bar, legend) into the SVG. Saves to file.
- **PDF**: `QWebEngineView.printToPdf()` — captures the full page as vector PDF including all overlays.
- **PNG**: `QWebEngineView.grab()` → `QPixmap.save()` — existing raster approach.

Dialog also offers DPI/resolution setting for PNG (default 300 DPI).

### 7. Per-Facies Color Picker

A settings panel (accessible via toolbar gear icon) shows a list of all recognized facies types. Each has a color swatch that opens a `QColorDialog` when clicked. Changes apply immediately via `setOption()`.

Color presets can be saved/loaded as JSON files. Default preset uses the muted pastel palette.

### 8. Expanded SVG Patterns

Add 8-10 new SVG pattern files to `src/patterns/` and corresponding entries in `PATTERN_MAP`:

| New Pattern | Facies Keyword | Category |
|-------------|---------------|----------|
| `shoreface.svg` | 滨岸, 前滨, 临滨 | Clastic |
| `reef.svg` | 生物礁, 礁 | Carbonate |
| `evaporite.svg` | 蒸发岩, 膏盐 | Chemical |
| `glacial.svg` | 冰川, 冰碛 | Glacial |
| `volcanic.svg` | 火山岩, 熔岩 | Volcanic |
| `metamorphic.svg` | 变质岩 | Metamorphic |
| `alluvial.svg` | 冲积扇, 洪积扇 | Clastic |
| `lagoon.svg` | 潟湖, 局限台地 | Carbonate |

Patterns follow the same GB/T standard style as existing ones.

---

## File Structure

| File | Status | Purpose |
|------|--------|---------|
| `src/resources/js/echarts.min.js` | New | Bundled ECharts v5.5 |
| `src/renderers/paleo_map_renderer.py` | Major rewrite | Enhanced ECharts renderer with labels, patterns, dress-up |
| `src/pages/paleo_map_page.py` | Major rewrite | Multi-period, CSV loading, compare mode, export, settings |
| `src/data/paleo_loader.py` | New | CSV/Excel → GeoJSON, period extraction |
| `packages/geoviz_well_log/geoviz_well_log/pattern_map.py` | Minor update | Add `FACIES_COLORS` palette mapping + new pattern entries |
| `src/patterns/*.svg` | New (8-10 files) | Additional geological SVG patterns |
| `tests/test_paleo_map.py` | Expand | New tests for CSV loader, multi-period, boundary styles, export |

---

## Data Flow

```
User loads file (GeoJSON or CSV)
  → PaleoMapPage detects format
  → GeoJSON: parsed directly
  → CSV/Excel: PaleoDataLoader converts to feature dict
  → Features grouped by period name
  → Stored in period dict

User selects period from dropdown
  → PaleoMapRenderer.set_period(period_name)
  → Builds ECharts option with:
    - Map series (polygons with colors, patterns, boundary styles)
    - Scatter series (well markers)
    - Labels (inline bold, auto-contrast)
    - Custom HTML legend (pattern swatches + boundary types)
    - Dress-up overlays (title, north arrow, scale bar, grid)
  → ECharts setOption() updates without full reload

User exports
  → Export dialog → format selection
  → SVG: getDataURL + composite dress-up → save
  → PDF: printToPdf → save
  → PNG: grab → save

User toggles compare mode
  → QSplitter with two renderers
  → Each shows a different period
  → Independent pan/zoom/labels/export
```

---

## Testing Strategy

- **PaleoDataLoader unit tests**: CSV parsing, WKT conversion, period extraction, auto-detection, error handling
- **Renderer config tests**: Verify ECharts option structure for labels, colors, boundary styles, well overlay
- **Integration tests**: Load sample GeoJSON + CSV, verify multi-period dict, verify period switching
- **Export tests**: SVG output contains expected elements, PDF generates valid file
- **Existing tests**: 6 existing test cases preserved and expanded
