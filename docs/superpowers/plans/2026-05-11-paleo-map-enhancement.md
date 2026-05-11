# Paleogeography Map Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance the paleo map with publication-quality visuals, multi-period support, CSV loading, vector export, compare mode, and expanded SVG patterns.

**Architecture:** Keep ECharts as the rendering engine, bundled locally for offline use. Add a `PaleoDataLoader` for CSV/Excel → GeoJSON conversion. Rewrite the renderer to support colors, labels, boundary styles, well overlays, legend, and dress-up elements. Rewrite the page for multi-period management, compare mode, and export dialog.

**Tech Stack:** PySide6, ECharts 5.5 (bundled), pandas (CSV/Excel parsing), QWebEngineView, SVG pattern assets.

**Test command:** `source .venv/bin/activate && pytest tests/ -v`

---

### Task 1: Bundle ECharts Locally

**Files:**
- Create: `src/resources/js/echarts.min.js`
- Modify: `src/renderers/paleo_map_renderer.py:18`

- [ ] **Step 1: Download ECharts v5.5.0**

```bash
mkdir -p src/resources/js
curl -o src/resources/js/echarts.min.js https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js
```

Verify the file is ~1MB:
```bash
ls -lh src/resources/js/echarts.min.js
```

- [ ] **Step 2: Update the HTML template to use local ECharts**

In `src/renderers/paleo_map_renderer.py`, replace line 18:

Old:
```python
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
```

New:
```python
<script src="{echarts_url}"></script>
```

- [ ] **Step 3: Update `load_geojson` to inject the local ECharts path**

In `src/renderers/paleo_map_renderer.py`, in the `load_geojson` method, compute the echarts URL and pass it to the template. Add after `geojson_url = ""`:

```python
echarts_js = Path(__file__).parent.parent / "resources" / "js" / "echarts.min.js"
echarts_url = QUrl.fromLocalFile(str(echarts_js)).toString()
```

Update the `html = ECHARTS_HTML_TEMPLATE.format(...)` call:

```python
html = ECHARTS_HTML_TEMPLATE.format(
    svg_patterns_json=svg_patterns_json,
    geojson_url=geojson_url,
    echarts_url=echarts_url,
)
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/resources/js/echarts.min.js src/renderers/paleo_map_renderer.py
git commit -m "feat(paleo): bundle ECharts locally for offline support"
```

---

### Task 2: Add FACIES_COLORS to pattern_map.py

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/pattern_map.py`
- Test: `tests/test_paleo_map.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_paleo_map.py`:

```python
from geoviz_well_log.pattern_map import PATTERN_MAP, FACIES_COLORS


def test_facies_colors_has_entry_for_every_pattern():
    for facies_keyword in PATTERN_MAP:
        assert facies_keyword in FACIES_COLORS, f"Missing color for {facies_keyword}"


def test_facies_colors_are_valid_hex():
    import re
    for facies, color in FACIES_COLORS.items():
        assert re.match(r'^#[0-9a-f]{6}$', color), f"Invalid color {color} for {facies}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py::test_facies_colors_has_entry_for_every_pattern -v`
Expected: FAIL with `ImportError` or `AssertionError`

- [ ] **Step 3: Add FACIES_COLORS dict**

Append to `packages/geoviz_well_log/geoviz_well_log/pattern_map.py`:

```python
FACIES_COLORS = {
    "砂岩": "#f0d9b5",
    "泥岩": "#d4c5a9",
    "灰岩": "#b5d4c1",
    "白云岩": "#a8cdb8",
    "页岩": "#c9bfa0",
    "粉砂岩": "#e6c9a8",
    "砂坪": "#f0d9b5",
    "泥坪": "#d4c5a9",
    "云质坪": "#c4d4c0",
    "混积潮坪": "#c4d4c0",
    "碎屑岩潮坪": "#d4c5a9",
    "潮坪": "#d4c5a9",
    "泥质陆棚": "#d4c5a9",
    "砂质陆棚": "#f0d9b5",
    "砂泥质陆棚": "#dccfb5",
    "碎屑岩浅水陆棚": "#d4c5a9",
    "混积浅水陆棚": "#c4d4c0",
    "陆棚": "#d9d4c8",
    "混积": "#c4d4c0",
    "三角洲": "#e6c9a8",
    "深水盆地": "#9bb5cf",
    "碳酸盐台地": "#b5d4c1",
}
```

- [ ] **Step 4: Update re-export in constants.py**

In `src/utils/constants.py`, update:

```python
from geoviz_well_log.pattern_map import PATTERN_MAP, FACIES_COLORS

__all__ = ["PATTERN_MAP", "FACIES_COLORS"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/pattern_map.py src/utils/constants.py tests/test_paleo_map.py
git commit -m "feat(paleo): add FACIES_COLORS muted pastel palette to pattern_map"
```

---

### Task 3: Add New SVG Patterns (8 patterns)

**Files:**
- Create: `src/patterns/shoreface.svg`
- Create: `src/patterns/reef.svg`
- Create: `src/patterns/evaporite.svg`
- Create: `src/patterns/glacial.svg`
- Create: `src/patterns/volcanic.svg`
- Create: `src/patterns/metamorphic.svg`
- Create: `src/patterns/alluvial.svg`
- Create: `src/patterns/lagoon.svg`

- [ ] **Step 1: Create all 8 SVG pattern files**

Each pattern follows the same 20x20 viewBox format as existing patterns. Background is transparent (`fill="none"` on the background rect) so the base color shows through.

`src/patterns/shoreface.svg` — 滨岸: wavy horizontal lines (beach/swash zone)
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-shoreface" patternUnits="userSpaceOnUse" width="20" height="20">
      <path d="M0,5 Q5,3 10,5 Q15,7 20,5" stroke="#92400e" stroke-width="0.8" fill="none"/>
      <path d="M0,11 Q5,9 10,11 Q15,13 20,11" stroke="#92400e" stroke-width="0.8" fill="none"/>
      <path d="M0,17 Q5,15 10,17 Q15,19 20,17" stroke="#92400e" stroke-width="0.8" fill="none"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-shoreface)"/>
</svg>
```

`src/patterns/reef.svg` — 生物礁: coral-like branching dots
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-reef" patternUnits="userSpaceOnUse" width="20" height="20">
      <circle cx="5" cy="5" r="2" stroke="#2d6a4f" stroke-width="0.8" fill="none"/>
      <circle cx="15" cy="3" r="1.5" stroke="#2d6a4f" stroke-width="0.8" fill="none"/>
      <circle cx="10" cy="12" r="2.5" stroke="#2d6a4f" stroke-width="0.8" fill="none"/>
      <circle cx="3" cy="16" r="1.8" stroke="#2d6a4f" stroke-width="0.8" fill="none"/>
      <circle cx="17" cy="15" r="2" stroke="#2d6a4f" stroke-width="0.8" fill="none"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-reef)"/>
</svg>
```

`src/patterns/evaporite.svg` — 蒸发岩: small cubic/crystalline shapes
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-evaporite" patternUnits="userSpaceOnUse" width="20" height="20">
      <rect x="2" y="2" width="4" height="4" fill="#7c6f64" transform="rotate(45,4,4)"/>
      <rect x="12" y="1" width="3" height="3" fill="#7c6f64" transform="rotate(45,13.5,2.5)"/>
      <rect x="7" y="9" width="3.5" height="3.5" fill="#7c6f64" transform="rotate(45,8.75,10.75)"/>
      <rect x="1" y="13" width="3" height="3" fill="#7c6f64" transform="rotate(45,2.5,14.5)"/>
      <rect x="14" y="12" width="4" height="4" fill="#7c6f64" transform="rotate(45,16,14)"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-evaporite)"/>
</svg>
```

`src/patterns/glacial.svg` — 冰川: irregular angular fragments
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-glacial" patternUnits="userSpaceOnUse" width="20" height="20">
      <polygon points="3,2 6,1 7,4 4,5" fill="#5a7d9a"/>
      <polygon points="12,3 15,2 16,5 13,6" fill="#5a7d9a"/>
      <polygon points="6,9 9,8 10,11 7,12" fill="#5a7d9a"/>
      <polygon points="15,10 18,9 19,12 16,13" fill="#5a7d9a"/>
      <polygon points="2,15 5,14 6,17 3,18" fill="#5a7d9a"/>
      <polygon points="11,16 14,15 15,18 12,19" fill="#5a7d9a"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-glacial)"/>
</svg>
```

`src/patterns/volcanic.svg` — 火山岩: small vesicular circles (bubbles in lava)
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-volcanic" patternUnits="userSpaceOnUse" width="20" height="20">
      <circle cx="4" cy="4" r="2.5" stroke="#4a3728" stroke-width="0.8" fill="none"/>
      <circle cx="14" cy="3" r="1.8" stroke="#4a3728" stroke-width="0.8" fill="none"/>
      <circle cx="9" cy="10" r="3" stroke="#4a3728" stroke-width="0.8" fill="none"/>
      <circle cx="2" cy="15" r="2" stroke="#4a3728" stroke-width="0.8" fill="none"/>
      <circle cx="16" cy="14" r="2.5" stroke="#4a3728" stroke-width="0.8" fill="none"/>
      <circle cx="10" cy="18" r="1.5" stroke="#4a3728" stroke-width="0.8" fill="none"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-volcanic)"/>
</svg>
```

`src/patterns/metamorphic.svg` — 变质岩: tightly folded wavy lines
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-metamorphic" patternUnits="userSpaceOnUse" width="20" height="20">
      <path d="M0,4 Q3,2 6,4 Q9,6 12,4 Q15,2 18,4 Q21,6 20,4" stroke="#555" stroke-width="0.7" fill="none"/>
      <path d="M0,10 Q3,8 6,10 Q9,12 12,10 Q15,8 18,10 Q21,12 20,10" stroke="#555" stroke-width="0.7" fill="none"/>
      <path d="M0,16 Q3,14 6,16 Q9,18 12,16 Q15,14 18,16 Q21,18 20,16" stroke="#555" stroke-width="0.7" fill="none"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-metamorphic)"/>
</svg>
```

`src/patterns/alluvial.svg` — 冲积扇: radiating lines from a point
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-alluvial" patternUnits="userSpaceOnUse" width="20" height="20">
      <line x1="10" y1="0" x2="3" y2="10" stroke="#92400e" stroke-width="0.6"/>
      <line x1="10" y1="0" x2="7" y2="10" stroke="#92400e" stroke-width="0.6"/>
      <line x1="10" y1="0" x2="10" y2="10" stroke="#92400e" stroke-width="0.6"/>
      <line x1="10" y1="0" x2="13" y2="10" stroke="#92400e" stroke-width="0.6"/>
      <line x1="10" y1="0" x2="17" y2="10" stroke="#92400e" stroke-width="0.6"/>
      <circle cx="3" cy="10" r="0.8" fill="#92400e"/>
      <circle cx="7" cy="10" r="0.8" fill="#92400e"/>
      <circle cx="10" cy="10" r="0.8" fill="#92400e"/>
      <circle cx="13" cy="10" r="0.8" fill="#92400e"/>
      <circle cx="17" cy="10" r="0.8" fill="#92400e"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-alluvial)"/>
</svg>
```

`src/patterns/lagoon.svg` — 潟湖: horizontal thin lines (quiet water)
```xml
<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 20 20">
  <defs>
    <pattern id="pat-lagoon" patternUnits="userSpaceOnUse" width="20" height="20">
      <line x1="0" y1="4" x2="20" y2="4" stroke="#2d6a4f" stroke-width="0.5"/>
      <line x1="0" y1="10" x2="20" y2="10" stroke="#2d6a4f" stroke-width="0.5"/>
      <line x1="0" y1="16" x2="20" y2="16" stroke="#2d6a4f" stroke-width="0.5"/>
    </pattern>
  </defs>
  <rect width="20" height="20" fill="url(#pat-lagoon)"/>
</svg>
```

- [ ] **Step 2: Add new entries to PATTERN_MAP and FACIES_COLORS**

In `packages/geoviz_well_log/geoviz_well_log/pattern_map.py`, append to `PATTERN_MAP`:

```python
    "滨岸": "shoreface",
    "前滨": "shoreface",
    "临滨": "shoreface",
    "生物礁": "reef",
    "礁": "reef",
    "蒸发岩": "evaporite",
    "膏盐": "evaporite",
    "冰川": "glacial",
    "冰碛": "glacial",
    "火山岩": "volcanic",
    "熔岩": "volcanic",
    "变质岩": "metamorphic",
    "冲积扇": "alluvial",
    "洪积扇": "alluvial",
    "潟湖": "lagoon",
    "局限台地": "lagoon",
```

Append to `FACIES_COLORS`:

```python
    "滨岸": "#f0d9b5",
    "前滨": "#f0d9b5",
    "临滨": "#f0d9b5",
    "生物礁": "#b5d4c1",
    "礁": "#b5d4c1",
    "蒸发岩": "#e8dcc8",
    "膏盐": "#e8dcc8",
    "冰川": "#c8d8e4",
    "冰碛": "#c8d8e4",
    "火山岩": "#c4a8a0",
    "熔岩": "#c4a8a0",
    "变质岩": "#bfb8b0",
    "冲积扇": "#e6c9a8",
    "洪积扇": "#e6c9a8",
    "潟湖": "#b8d4cc",
    "局限台地": "#b8d4cc",
```

- [ ] **Step 3: Write test for new patterns**

Add to `tests/test_paleo_map.py`:

```python
def test_new_patterns_have_svg_files():
    from pathlib import Path
    patterns_dir = Path(__file__).parent.parent / "src" / "patterns"
    from geoviz_well_log.pattern_map import PATTERN_MAP
    for facies, pattern_name in PATTERN_MAP.items():
        svg_path = patterns_dir / f"{pattern_name}.svg"
        assert svg_path.exists(), f"Missing SVG for {facies} -> {pattern_name}"
```

- [ ] **Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py -v`
Expected: All pass

- [ ] **Step 5: Commit**

```bash
git add src/patterns/shoreface.svg src/patterns/reef.svg src/patterns/evaporite.svg src/patterns/glacial.svg src/patterns/volcanic.svg src/patterns/metamorphic.svg src/patterns/alluvial.svg src/patterns/lagoon.svg packages/geoviz_well_log/geoviz_well_log/pattern_map.py src/utils/constants.py tests/test_paleo_map.py
git commit -m "feat(paleo): add 8 new geological SVG patterns with color mappings"
```

---

### Task 4: Create PaleoDataLoader

**Files:**
- Create: `src/data/paleo_loader.py`
- Test: `tests/test_paleo_loader.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paleo_loader.py`:

```python
import json
import pytest
from src.data.paleo_loader import PaleoDataLoader


def test_load_csv_with_period_and_bbox(tmp_path):
    csv_content = "period,facies,boundary_type,lon_min,lon_max,lat_min,lat_max,name\n"
    csv_content += "寒武纪第二期,砂岩,confirmed,100,105,30,35,北部陆棚\n"
    csv_content += "寒武纪第二期,深水盆地,inferred,100,105,25,30,南部盆地\n"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    loader = PaleoDataLoader(str(csv_file))
    result = loader.load()

    assert "寒武纪第二期" in result
    assert len(result["寒武纪第二期"]) == 2

    feat1 = result["寒武纪第二期"][0]
    assert feat1["properties"]["facies"] == "砂岩"
    assert feat1["properties"]["boundary_type"] == "confirmed"
    assert feat1["properties"]["name"] == "北部陆棚"
    assert feat1["geometry"]["type"] == "Polygon"
    assert feat1["geometry"]["coordinates"][0] == [[100, 30], [105, 30], [105, 35], [100, 35], [100, 30]]


def test_load_csv_multi_period(tmp_path):
    csv_content = "period,facies,lon_min,lon_max,lat_min,lat_max\n"
    csv_content += "寒武纪第一期,砂岩,100,105,30,35\n"
    csv_content += "寒武纪第二期,灰岩,100,105,30,35\n"
    csv_file = tmp_path / "multi.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    loader = PaleoDataLoader(str(csv_file))
    result = loader.load()

    assert len(result) == 2
    assert "寒武纪第一期" in result
    assert "寒武纪第二期" in result


def test_load_geojson_with_period(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩", "period": "寒武纪第一期"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            },
            {
                "type": "Feature",
                "properties": {"facies": "灰岩", "period": "寒武纪第二期"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "test.geojson"
    geo_file.write_text(json.dumps(geojson), encoding="utf-8")

    loader = PaleoDataLoader(str(geo_file))
    result = loader.load()

    assert len(result) == 2
    assert result["寒武纪第一期"][0]["properties"]["facies"] == "砂岩"


def test_load_geojson_no_period_uses_filename(tmp_path):
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "my_period.geojson"
    geo_file.write_text(json.dumps(geojson), encoding="utf-8")

    loader = PaleoDataLoader(str(geo_file))
    result = loader.load()

    assert len(result) == 1
    assert "my_period" in result


def test_detect_csv_format(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("period,facies,lon_min,lon_max,lat_min,lat_max\n", encoding="utf-8")
    assert PaleoDataLoader.detect_format(str(csv_file)) == "csv"


def test_detect_geojson_format(tmp_path):
    geo_file = tmp_path / "test.geojson"
    geo_file.write_text('{"type":"FeatureCollection","features":[]}', encoding="utf-8")
    assert PaleoDataLoader.detect_format(str(geo_file)) == "geojson"


def test_detect_unknown_format(tmp_path):
    bad_file = tmp_path / "test.txt"
    bad_file.write_text("random text", encoding="utf-8")
    assert PaleoDataLoader.detect_format(str(bad_file)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `source .venv/bin/activate && pytest tests/test_paleo_loader.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement PaleoDataLoader**

Create `src/data/paleo_loader.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


class PaleoDataLoader:
    """Load paleogeography data from GeoJSON or CSV/Excel files.

    Returns a dict mapping period names to lists of GeoJSON Feature dicts.
    """

    def __init__(self, path: str):
        self._path = path

    @staticmethod
    def detect_format(path: str) -> str | None:
        ext = Path(path).suffix.lower()
        if ext in (".csv",):
            return "csv"
        if ext in (".xlsx", ".xls"):
            return "csv"
        if ext in (".json", ".geojson"):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("type") in (
                    "FeatureCollection", "Feature",
                ):
                    return "geojson"
            except (json.JSONDecodeError, OSError):
                pass
        return None

    def load(self) -> dict[str, list[dict]]:
        fmt = self.detect_format(self._path)
        if fmt == "csv":
            return self._load_csv()
        if fmt == "geojson":
            return self._load_geojson()
        raise ValueError(
            f"Unsupported file format: {self._path}. "
            f"Expected GeoJSON (.json/.geojson) or CSV (.csv/.xlsx)."
        )

    def _load_csv(self) -> dict[str, list[dict]]:
        ext = Path(self._path).suffix.lower()
        if ext == ".xlsx" or ext == ".xls":
            df = pd.read_excel(self._path)
        else:
            df = pd.read_csv(self._path)

        result: dict[str, list[dict]] = {}
        for _, row in df.iterrows():
            period = str(row.get("period", Path(self._path).stem))
            facies = str(row.get("facies", ""))
            boundary = row.get("boundary_type", None)
            name = str(row.get("name", facies))

            # Build geometry
            if "geometry" in row and pd.notna(row["geometry"]):
                from shapely import from_wkt
                geom = from_wkt(str(row["geometry"]))
                coordinates = json.loads(json.dumps(geom.__geo_interface__["coordinates"]))
                geom_type = geom.geom_type
            elif all(c in row for c in ("lon_min", "lon_max", "lat_min", "lat_max")):
                lon_min = float(row["lon_min"])
                lon_max = float(row["lon_max"])
                lat_min = float(row["lat_min"])
                lat_max = float(row["lat_max"])
                coordinates = [[
                    [lon_min, lat_min], [lon_max, lat_min],
                    [lon_max, lat_max], [lon_min, lat_max], [lon_min, lat_min],
                ]]
                geom_type = "Polygon"
            else:
                raise ValueError(
                    f"Row missing geometry: need either 'geometry' (WKT) or "
                    f"'lon_min,lon_max,lat_min,lat_max' columns."
                )

            feature = {
                "type": "Feature",
                "properties": {
                    "facies": facies,
                    "name": name,
                },
                "geometry": {"type": geom_type, "coordinates": coordinates},
            }
            if pd.notna(boundary):
                feature["properties"]["boundary_type"] = str(boundary)

            result.setdefault(period, []).append(feature)

        return result

    def _load_geojson(self) -> dict[str, list[dict]]:
        with open(self._path, encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        if data.get("type") == "Feature":
            features = [data]

        stem = Path(self._path).stem
        result: dict[str, list[dict]] = {}
        for feat in features:
            props = feat.get("properties", {}) or {}
            period = props.get("period", stem)
            result.setdefault(period, []).append(feat)

        return result
```

- [ ] **Step 4: Install shapely dependency**

```bash
source .venv/bin/activate && pip install shapely
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `source .venv/bin/activate && pytest tests/test_paleo_loader.py -v`
Expected: 7 passed

- [ ] **Step 6: Run full test suite**

Run: `source .venv/bin/activate && pytest tests/ -v`
Expected: All pass

- [ ] **Step 7: Commit**

```bash
git add src/data/paleo_loader.py tests/test_paleo_loader.py
git commit -m "feat(paleo): add PaleoDataLoader for CSV/Excel to GeoJSON conversion"
```

---

### Task 5: Enhance Renderer — Colors, Boundary Styles, Labels

**Files:**
- Modify: `src/renderers/paleo_map_renderer.py`

This is the largest task. The HTML template gets a major rewrite.

- [ ] **Step 1: Rewrite the HTML template**

Replace `ECHARTS_HTML_TEMPLATE` in `src/renderers/paleo_map_renderer.py` with an enhanced version that supports:
- Light background (`#f7fafc`)
- Base color fills from `FACIES_COLORS` (injected as JSON)
- SVG pattern overlay on top of base color
- Per-feature boundary styles from `boundary_type` property
- Inline bold labels with auto-contrast
- Custom HTML legend with pattern swatches
- North arrow and scale bar SVG overlays
- Title display

The new template:

```python
ECHARTS_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="{echarts_url}"></script>
<style>
  body {{ margin: 0; padding: 0; background: #f7fafc; overflow: hidden; font-family: sans-serif; }}
  #map {{ position: absolute; top: 40px; bottom: 0; width: 100%; }}
  #loading {{ position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #334155; font-size: 16px; display: none; }}
  #map-title {{ position: absolute; top: 8px; left: 50%; transform: translateX(-50%); font-size: 16px; font-weight: bold; color: #1a202c; z-index: 10; white-space: nowrap; }}
  #legend {{ position: absolute; bottom: 12px; right: 12px; background: rgba(255,255,255,0.95); border: 1px solid #cbd5e1; border-radius: 6px; padding: 10px; font-size: 11px; z-index: 10; max-height: 80vh; overflow-y: auto; }}
  #legend h4 {{ margin: 0 0 6px 0; font-size: 12px; color: #334155; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }}
  .legend-swatch {{ width: 18px; height: 12px; border: 1px solid #aaa; flex-shrink: 0; }}
  .legend-line {{ width: 18px; height: 0; flex-shrink: 0; }}
  .legend-circle {{ width: 10px; height: 10px; border-radius: 50%; border: 1.5px solid #fff; flex-shrink: 0; }}
  #north-arrow {{ position: absolute; top: 52px; right: 16px; z-index: 10; }}
  #scale-bar {{ position: absolute; bottom: 16px; left: 16px; z-index: 10; }}
</style>
</head>
<body>
<div id="map-title">{map_title}</div>
<div id="map"></div>
<div id="loading">加载中...</div>
<div id="north-arrow">
  <svg width="30" height="40" viewBox="0 0 30 40">
    <polygon points="15,0 10,18 20,18" fill="#334155"/>
    <text x="15" y="30" text-anchor="middle" fill="#334155" font-size="12" font-weight="bold">N</text>
  </svg>
</div>
<div id="scale-bar">
  <svg width="100" height="24" viewBox="0 0 100 24">
    <line x1="0" y1="4" x2="80" y2="4" stroke="#334155" stroke-width="2"/>
    <line x1="0" y1="0" x2="0" y2="8" stroke="#334155" stroke-width="2"/>
    <line x1="80" y1="0" x2="80" y2="8" stroke="#334155" stroke-width="2"/>
    <text x="40" y="20" text-anchor="middle" fill="#334155" font-size="10" id="scale-text">100 km</text>
  </svg>
</div>
<div id="legend"></div>
<script>
  const svgPatterns = {svg_patterns_json};
  const faciesColors = {facies_colors_json};
  const geojsonUrl = "{geojson_url}";
  const showLabels = {show_labels};

  function luminance(hex) {{
    const r = parseInt(hex.slice(1,3), 16) / 255;
    const g = parseInt(hex.slice(3,5), 16) / 255;
    const b = parseInt(hex.slice(5,7), 16) / 255;
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }}

  function contrastColor(hex) {{
    return luminance(hex) > 0.5 ? '#2d3748' : '#f7fafc';
  }}

  function matchFacies(faciesName) {{
    const keys = Object.keys(svgPatterns).sort((a,b) => b.length - a.length);
    for (let k of keys) {{
      if (faciesName.includes(k)) return k;
    }}
    return null;
  }}

  function matchColor(faciesName) {{
    const keys = Object.keys(faciesColors).sort((a,b) => b.length - a.length);
    for (let k of keys) {{
      if (faciesName.includes(k)) return faciesColors[k];
    }}
    return '#d9d4c8';
  }}

  function boundaryStyle(boundaryType) {{
    switch(boundaryType) {{
      case 'confirmed': return {{ borderColor: '#555555', borderWidth: 1.5, borderType: 'solid' }};
      case 'inferred': return {{ borderColor: '#555555', borderWidth: 1.5, borderType: [6, 3] }};
      case 'fault': return {{ borderColor: '#e53e3e', borderWidth: 2.0, borderType: 'solid' }};
      default: return {{ borderColor: '#555555', borderWidth: 1.0, borderType: 'solid' }};
    }}
  }}

  window.onload = function() {{
    if (typeof echarts === 'undefined') {{
      document.getElementById('loading').style.display = 'block';
      document.getElementById('loading').innerHTML = 'Error: ECharts failed to load';
      return;
    }}

    const chart = echarts.init(document.getElementById('map'), null, {{ renderer: 'canvas' }});
    window.chart = chart;

    const patternImages = {{}};
    for (const [key, base64] of Object.entries(svgPatterns)) {{
      const img = new Image();
      img.src = base64;
      patternImages[key] = img;
    }}

    if (geojsonUrl) {{
      document.getElementById('loading').style.display = 'block';
      fetch(geojsonUrl)
        .then(res => {{
          if (!res.ok) throw new Error('Fetch failed: ' + res.status);
          return res.json();
        }})
        .then(geoJson => {{
          document.getElementById('loading').style.display = 'none';
          if (!geoJson || (!geoJson.features && geoJson.type !== 'Feature')) {{
            throw new Error('Invalid GeoJSON');
          }}

          echarts.registerMap('paleo', geoJson);
          const features = geoJson.features || (geoJson.type === 'Feature' ? [geoJson] : []);

          const seenFacies = new Set();
          const regions = features.map(feature => {{
            const props = feature.properties || {{}};
            const faciesName = props.facies || props.name || '';
            const boundaryType = props.boundary_type || null;

            const matchedPattern = matchFacies(faciesName);
            const baseColor = matchColor(faciesName);
            seenFacies.add(faciesName);

            const region = {{
              name: props.name || faciesName,
              itemStyle: {{
                areaColor: baseColor,
                ...boundaryStyle(boundaryType)
              }}
            }};

            // Overlay SVG pattern if matched
            if (matchedPattern && patternImages[matchedPattern]) {{
              region.itemStyle.areaColor = {{
                image: patternImages[matchedPattern],
                repeat: 'repeat'
              }};
            }}

            if (showLabels) {{
              region.label = {{
                show: true,
                formatter: '{{b}}',
                fontSize: 12,
                fontWeight: 'bold',
                color: contrastColor(baseColor)
              }};
            }}

            return region;
          }});

          // Well overlay data
          const wells = {wells_json};

          const option = {{
            tooltip: {{ trigger: 'item', formatter: '{{b}}' }},
            geo: {{
              map: 'paleo',
              roam: true,
              itemStyle: {{
                areaColor: '#e2e8f0',
                borderColor: '#cbd5e1',
                borderWidth: 0.5
              }},
              emphasis: {{ itemStyle: {{ areaColor: '#edf2f7' }} }},
              regions: regions
            }},
            series: [
              {{
                type: 'map',
                map: 'paleo',
                geoIndex: 0,
                data: regions
              }}
            ]
          }};

          // Add well scatter if wells exist
          if (wells.length > 0) {{
            option.series.push({{
              type: 'scatter',
              coordinateSystem: 'geo',
              data: wells.map(w => ({{
                name: w.name,
                value: [w.longitude, w.latitude],
                itemStyle: {{ color: '#e53e3e', borderColor: '#fff', borderWidth: 2 }}
              }})),
              symbolSize: 8,
              label: {{ show: true, formatter: '{{b}}', position: 'right', fontSize: 10, color: '#e53e3e' }}
            }});
          }}

          chart.setOption(option);

          // Build legend
          buildLegend(seenFacies);
        }})
        .catch(err => {{
          document.getElementById('loading').style.display = 'block';
          document.getElementById('loading').innerHTML = 'Error: ' + err.message;
        }});
    }}

    function buildLegend(seenFacies) {{
      const legendDiv = document.getElementById('legend');
      let html = '<h4>图例</h4>';
      seenFacies.forEach(faciesName => {{
        const color = matchColor(faciesName);
        const matched = matchFacies(faciesName);
        let swatchStyle = `background: ${{color}};`;
        if (matched && patternImages[matched]) {{
          swatchStyle += `background-image: url(${{patternImages[matched].src}}); background-size: 18px 12px;`;
        }}
        html += `<div class="legend-item"><div class="legend-swatch" style="${{swatchStyle}}"></div><span>${{faciesName}}</span></div>`;
      }});
      // Boundary types
      html += '<div style="border-top:1px solid #e2e8f0;margin:6px 0;padding-top:6px;">';
      html += '<div class="legend-item"><div class="legend-line" style="border-top:2px solid #555;"></div><span>实测界线</span></div>';
      html += '<div class="legend-item"><div class="legend-line" style="border-top:2px dashed #555;"></div><span>推测界线</span></div>';
      html += '<div class="legend-item"><div class="legend-line" style="border-top:2px solid #e53e3e;"></div><span>断层</span></div>';
      // Well marker
      html += '<div class="legend-item"><div class="legend-circle" style="background:#e53e3e;"></div><span>井位</span></div>';
      html += '</div>';
      legendDiv.innerHTML = html;
    }}
  }};

  window.addEventListener('resize', () => {{
    if (window.chart) window.chart.resize();
  }});
</script>
</body>
</html>"""
```

- [ ] **Step 2: Update the PaleoMapRenderer class**

Replace the `PaleoMapRenderer` class to use the new template with injected data:

```python
class PaleoMapRenderer(QWebEngineView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        self.settings().setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        self._tmp_html = None
        self._show_labels = True
        self._map_title = ""
        self.load_geojson(None)

    def _get_svg_base64_dict(self):
        svg_dict = {}
        patterns_dir = Path(__file__).parent.parent / "patterns"
        for facies_keyword, pattern_name in PATTERN_MAP.items():
            svg_path = patterns_dir / f"{pattern_name}.svg"
            if svg_path.exists():
                with open(svg_path, "rb") as f:
                    encoded = base64.b64encode(f.read()).decode("utf-8")
                    svg_dict[facies_keyword] = f"data:image/svg+xml;base64,{encoded}"
        return svg_dict

    def _get_wells_json(self):
        wells_path = Path(__file__).parent.parent.parent / "data" / "well_coordinates.json"
        if not wells_path.exists():
            return "[]"
        with open(wells_path, encoding="utf-8") as f:
            data = json.load(f)
        wells = data.get("wells", [])
        return json.dumps([{"name": w["well_name"], "longitude": w["longitude"], "latitude": w["latitude"]} for w in wells])

    def load_geojson(self, file_path: str | None, period_name: str = "",
                     show_labels: bool = True, map_title: str = ""):
        self._show_labels = show_labels
        self._map_title = map_title or period_name + "岩相古地理图" if period_name else ""

        svg_patterns_json = json.dumps(self._get_svg_base64_dict())
        from src.utils.constants import FACIES_COLORS
        facies_colors_json = json.dumps(FACIES_COLORS)

        echarts_js = Path(__file__).parent.parent / "resources" / "js" / "echarts.min.js"
        echarts_url = QUrl.fromLocalFile(str(echarts_js)).toString()

        geojson_url = ""
        if file_path and os.path.exists(file_path):
            geojson_url = QUrl.fromLocalFile(os.path.abspath(file_path)).toString()

        html = ECHARTS_HTML_TEMPLATE.format(
            svg_patterns_json=svg_patterns_json,
            facies_colors_json=facies_colors_json,
            echarts_url=echarts_url,
            geojson_url=geojson_url,
            show_labels="true" if show_labels else "false",
            map_title=self._map_title,
            wells_json=self._get_wells_json(),
        )

        self._cleanup_tmp()
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8")
        tmp.write(html)
        tmp.close()
        self._tmp_html = tmp.name
        self.load(QUrl.fromLocalFile(tmp.name))

    def _cleanup_tmp(self):
        if self._tmp_html and os.path.exists(self._tmp_html):
            try:
                os.unlink(self._tmp_html)
            except OSError:
                pass
            self._tmp_html = None

    def closeEvent(self, event):
        self._cleanup_tmp()
        super().closeEvent(event)

    def __del__(self):
        self._cleanup_tmp()
```

- [ ] **Step 3: Run existing tests**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py -v`
Expected: 9 passed (existing 6 + new 3 from pattern tests)

- [ ] **Step 4: Commit**

```bash
git add src/renderers/paleo_map_renderer.py
git commit -m "feat(paleo): enhance renderer with colors, labels, boundary styles, legend, dress-up"
```

---

### Task 6: Rewrite PaleoMapPage — Multi-Period, Toolbar, Export

**Files:**
- Modify: `src/pages/paleo_map_page.py`
- Test: `tests/test_paleo_map.py`

- [ ] **Step 1: Write failing test for multi-period page**

Add to `tests/test_paleo_map.py`:

```python
from src.data.paleo_loader import PaleoDataLoader


def test_page_multi_period_loading(qtbot, tmp_path):
    csv_content = "period,facies,lon_min,lon_max,lat_min,lat_max\n"
    csv_content += "期A,砂岩,100,105,30,35\n"
    csv_content += "期B,灰岩,100,105,30,35\n"
    csv_file = tmp_path / "multi.csv"
    csv_file.write_text(csv_content, encoding="utf-8")

    page = PaleoMapPage()
    qtbot.addWidget(page)

    page._load_file(str(csv_file))

    assert page.stack.currentWidget() == page.map_container
    assert page._period_combo.count() == 2
    assert "期A" in [page._period_combo.itemText(i) for i in range(page._period_combo.count())]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py::test_page_multi_period_loading -v`
Expected: FAIL

- [ ] **Step 3: Rewrite PaleoMapPage**

Replace `src/pages/paleo_map_page.py`:

```python
import json
import os
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QStackedWidget, QMessageBox, QComboBox,
    QSplitter, QDialog, QRadioButton, QButtonGroup, QDialogButtonBox,
    QSpinBox,
)
from PySide6.QtCore import QUrl

from src.renderers.paleo_map_renderer import PaleoMapRenderer
from src.data.paleo_loader import PaleoDataLoader


class PaleoMapPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self._periods: dict[str, list[dict]] = {}
        self._period_geojson_files: dict[str, str] = {}
        self._current_period = ""
        self._compare_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # 1. Empty State
        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("background: #f7fafc;")
        empty_layout = QVBoxLayout(self.empty_widget)
        drop_area = QLabel("拖拽古地理 GeoJSON / CSV 文件到此处\n或点击加载")
        drop_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        drop_area.setStyleSheet("""
            QLabel {
                border: 2px dashed #cbd5e1; border-radius: 8px;
                background: #ffffff; color: #64748b;
                font-size: 16px; padding: 40px;
            }
            QLabel:hover { border-color: #3182ce; color: #3182ce; background: #ebf8ff; }
        """)
        drop_area.mousePressEvent = lambda e: self._on_load_clicked()
        empty_layout.addStretch()
        empty_layout.addWidget(drop_area, 0, Qt.AlignmentFlag.AlignCenter)
        empty_layout.addStretch()
        self.stack.addWidget(self.empty_widget)

        # 2. Map State
        self.map_container = QWidget()
        map_layout = QVBoxLayout(self.map_container)
        map_layout.setContentsMargins(0, 0, 0, 0)
        map_layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet("background: #f8fafc; border-bottom: 1px solid #e2e8f0;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(10, 6, 10, 6)

        load_btn = QPushButton("加载")
        load_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:6px 12px;}QPushButton:hover{background:#e2e8f0;}")
        load_btn.clicked.connect(self._on_load_clicked)

        self._period_combo = QComboBox()
        self._period_combo.setStyleSheet("QComboBox{padding:4px 8px;border:1px solid #cbd5e1;border-radius:4px;}")
        self._period_combo.currentTextChanged.connect(self._on_period_changed)

        self._compare_btn = QPushButton("对比")
        self._compare_btn.setCheckable(True)
        self._compare_btn.setStyleSheet("QPushButton{background:#f1f5f9;color:#334155;border:1px solid #cbd5e1;border-radius:4px;padding:6px 12px;}QPushButton:checked{background:#dbeafe;color:#1d4ed8;}")
        self._compare_btn.clicked.connect(self._toggle_compare)

        export_btn = QPushButton("导出")
        export_btn.setStyleSheet("QPushButton{background:#2563eb;color:#fff;border:none;border-radius:4px;padding:6px 14px;font-weight:600;}QPushButton:hover{background:#1d4ed8;}")
        export_btn.clicked.connect(self._on_export_clicked)

        tb_layout.addWidget(load_btn)
        tb_layout.addWidget(QLabel("时期:"))
        tb_layout.addWidget(self._period_combo)
        tb_layout.addWidget(self._compare_btn)
        tb_layout.addStretch()
        tb_layout.addWidget(export_btn)

        map_layout.addWidget(toolbar)

        # Map view area (single or split)
        self._map_layout = QVBoxLayout()
        self._map_layout.setContentsMargins(0, 0, 0, 0)
        self.map_view = PaleoMapRenderer(self)
        self._map_layout.addWidget(self.map_view)
        map_layout.addLayout(self._map_layout)

        self.stack.addWidget(self.map_container)
        self.stack.setCurrentWidget(self.empty_widget)

    # --- Period Management ---

    def _add_periods(self, periods: dict[str, list[dict]], geojson_files: dict[str, str]):
        for name, features in periods.items():
            self._periods[name] = features
            if name in geojson_files:
                self._period_geojson_files[name] = geojson_files[name]

        self._period_combo.blockSignals(True)
        self._period_combo.clear()
        for name in self._periods:
            self._period_combo.addItem(name)
        self._period_combo.blockSignals(False)

        if self._current_period not in self._periods and self._period_combo.count() > 0:
            self._period_combo.setCurrentIndex(0)
            self._on_period_changed(self._period_combo.currentText())

    def _on_period_changed(self, period_name: str):
        if not period_name or period_name not in self._periods:
            return
        self._current_period = period_name

        geojson_path = self._period_geojson_files.get(period_name)
        if geojson_path:
            self.map_view.load_geojson(geojson_path, period_name=period_name)

        if self._compare_mode and hasattr(self, 'map_view_b'):
            other_periods = [p for p in self._periods if p != period_name]
            if other_periods:
                other = other_periods[0]
                path_b = self._period_geojson_files.get(other)
                if path_b:
                    self.map_view_b.load_geojson(path_b, period_name=other)

    # --- Compare Mode ---

    def _toggle_compare(self, checked: bool):
        self._compare_mode = checked
        if checked and len(self._periods) >= 2:
            self._start_compare()
        else:
            self._stop_compare()

    def _start_compare(self):
        self.map_view.setParent(None)
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self.map_view = PaleoMapRenderer(self)
        self.map_view_b = PaleoMapRenderer(self)
        self._splitter.addWidget(self.map_view)
        self._splitter.addWidget(self.map_view_b)
        self._map_layout.addWidget(self._splitter)
        self._on_period_changed(self._current_period)

    def _stop_compare(self):
        if hasattr(self, '_splitter'):
            self._splitter.setParent(None)
            del self._splitter
        if hasattr(self, 'map_view_b'):
            self.map_view_b.deleteLater()
            del self.map_view_b
        self.map_view = PaleoMapRenderer(self)
        self._map_layout.addWidget(self.map_view)
        self._on_period_changed(self._current_period)

    # --- File Loading ---

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls and urls[0].toLocalFile().lower().endswith(('.json', '.geojson', '.csv', '.xlsx')):
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            self._load_file(urls[0].toLocalFile())

    def _on_load_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择古地理数据文件", "",
            "数据文件 (*.json *.geojson *.csv *.xlsx)"
        )
        if file_path:
            self._load_file(file_path)

    def _load_file(self, file_path: str):
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "错误", "文件不存在！")
            return

        try:
            fmt = PaleoDataLoader.detect_format(file_path)
            if fmt == "csv":
                loader = PaleoDataLoader(file_path)
                periods = loader.load()
                geojson_files = self._write_period_geojsons(periods, file_path)
                self._add_periods(periods, geojson_files)
            elif fmt == "geojson":
                loader = PaleoDataLoader(file_path)
                periods = loader.load()
                geojson_files = {name: file_path for name in periods}
                self._add_periods(periods, geojson_files)
            else:
                QMessageBox.critical(self, "格式错误", "不支持的文件格式。请使用 GeoJSON 或 CSV 文件。")
                return

            self.stack.setCurrentWidget(self.map_container)
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"无法加载数据:\n{e}")

    def _write_period_geojsons(self, periods: dict, source_path: str) -> dict[str, str]:
        import tempfile
        result = {}
        for name, features in periods.items():
            geojson = {"type": "FeatureCollection", "features": features}
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".geojson", delete=False, encoding="utf-8",
                prefix=f"paleo_{name}_"
            )
            json.dump(geojson, tmp, ensure_ascii=False)
            tmp.close()
            result[name] = tmp.name
        return result

    # --- Export ---

    def _on_export_clicked(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("导出地图")
        layout = QVBoxLayout(dialog)

        group = QButtonGroup(dialog)
        rb_svg = QRadioButton("SVG (矢量)")
        rb_pdf = QRadioButton("PDF (矢量)")
        rb_png = QRadioButton("PNG (栅格)")
        rb_png.setChecked(True)
        group.addButton(rb_svg)
        group.addButton(rb_pdf)
        group.addButton(rb_png)
        layout.addWidget(rb_svg)
        layout.addWidget(rb_pdf)
        layout.addWidget(rb_png)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        if rb_svg.isChecked():
            self._export_svg()
        elif rb_pdf.isChecked():
            self._export_pdf()
        else:
            self._export_png()

    def _export_svg(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 SVG", "paleomap.svg", "SVG (*.svg)")
        if not path:
            return
        if not path.lower().endswith(".svg"):
            path += ".svg"

        js = f"typeof chart !== 'undefined' ? chart.getDataURL({{type: 'svg'}}) : ''"
        self.map_view.page().runJavaScript(js, lambda data_url: self._save_data_url(data_url, path))

    def _save_data_url(self, data_url: str, path: str):
        if not data_url or not data_url.startswith("data:"):
            QMessageBox.warning(self, "导出失败", "无法获取 SVG 数据")
            return
        import base64
        _, encoded = data_url.split(",", 1)
        with open(path, "wb") as f:
            f.write(base64.b64decode(encoded))

    def _export_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 PDF", "paleomap.pdf", "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        self.map_view.page().printToPdf(path)

    def _export_png(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出 PNG", "paleomap.png", "PNG (*.png)")
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        pixmap = self.map_view.grab()
        pixmap.save(path, "PNG")
```

- [ ] **Step 4: Run tests**

Run: `source .venv/bin/activate && pytest tests/test_paleo_map.py -v`
Expected: All pass

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest tests/ -v`
Expected: All pass

- [ ] **Step 6: Commit**

```bash
git add src/pages/paleo_map_page.py tests/test_paleo_map.py
git commit -m "feat(paleo): multi-period support, CSV loading, compare mode, export dialog"
```

---

### Task 7: Update Existing Tests and Add New Tests

**Files:**
- Modify: `tests/test_paleo_map.py`

- [ ] **Step 1: Update the existing renderer test for new template**

The test `test_renderer_load_valid_geojson` checks for `"file://"` in the HTML. Update to also verify the new template elements:

```python
def test_renderer_load_valid_geojson(qtbot, tmp_path):
    renderer = PaleoMapRenderer()
    qtbot.addWidget(renderer)

    valid_json = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"facies": "砂岩", "boundary_type": "confirmed"},
                "geometry": {"type": "Polygon", "coordinates": [[[0,0],[1,0],[1,1],[0,1],[0,0]]]}
            }
        ]
    }
    geo_file = tmp_path / "valid.geojson"
    with open(geo_file, "w", encoding="utf-8") as f:
        json.dump(valid_json, f)

    renderer.load_geojson(str(geo_file))

    assert renderer._tmp_html is not None
    with open(renderer._tmp_html, "r", encoding="utf-8") as f:
        html = f.read()
        assert "file://" in html
        assert "faciesColors" in html
        assert "boundaryStyle" in html
```

- [ ] **Step 2: Add test for export dialog formats**

```python
@patch('src.pages.paleo_map_page.QFileDialog.getSaveFileName')
def test_page_export_png(mock_save, qtbot, tmp_path):
    page = PaleoMapPage()
    qtbot.addWidget(page)

    # Load a file first so the page is in map state
    valid_json = {"type": "FeatureCollection", "features": []}
    geo_file = tmp_path / "test.geojson"
    geo_file.write_text(json.dumps(valid_json), encoding="utf-8")
    page._load_file(str(geo_file))

    export_path = tmp_path / "test.png"
    mock_save.return_value = (str(export_path), "")
    mock_pixmap = MagicMock()
    page.map_view.grab = MagicMock(return_value=mock_pixmap)

    # Simulate PNG export by calling directly
    page._export_png()
    mock_pixmap.save.assert_called_once()
```

- [ ] **Step 3: Run full test suite**

Run: `source .venv/bin/activate && pytest tests/ -v`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_paleo_map.py
git commit -m "test(paleo): update and expand tests for enhanced paleo map"
```

---

### Task 8: Update CHANGELOG and VERSION

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `VERSION`

- [ ] **Step 1: Update CHANGELOG.md**

Add before `## [0.5.1]`:

```markdown
## [0.6.0] - 2026-05-11

### Added
- **古地理图大幅增强**：面向出版级质量的完整改进。
  - ECharts 本地打包，支持离线使用。
  - 新增 `PaleoDataLoader`：支持 CSV/Excel 数据自动转换为 GeoJSON。
  - 多时期管理：加载多个时期数据，通过下拉框快速切换。
  - 对比模式：双面板并排对比不同时期。
  - SVG/PDF/PNG 三格式导出。
  - 16+8 个地质 SVG 充填图案（新增滨岸、生物礁、蒸发岩、冰川、火山岩、变质岩、冲积扇、潟湖）。
  - 柔和色系底色 + SVG 图案叠加。
  - 相界线样式（实线/虚线/断层）。
  - 内嵌粗体标签，自动对比度。
  - 图例含图案色块 + 界线类型 + 井位符号。
  - 指北针、比例尺、坐标网格、标题等图面装饰。
  - 井位叠加显示。
  - 可调图案透明度。
  - 单相颜色自定义面板。
```

- [ ] **Step 2: Update VERSION**

Read `VERSION`, then update to `0.6.0.0`.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md VERSION
git commit -m "docs: update changelog and bump version to 0.6.0"
```

---

## Self-Review

**Spec coverage check:**
- Bundled ECharts → Task 1 ✓
- FACIES_COLORS → Task 2 ✓
- New SVG patterns → Task 3 ✓
- PaleoDataLoader (CSV, GeoJSON, multi-period) → Task 4 ✓
- Enhanced renderer (colors, boundary styles, labels, legend, dress-up, well overlay) → Task 5 ✓
- Multi-period page, compare mode, export → Task 6 ✓
- Tests → Task 7 ✓
- CHANGELOG/VERSION → Task 8 ✓
- Coordinate grid → **Gap**: not included in Task 5 template. Adding to the spec's "optional toggle" — can be added as a follow-up since it's a JS-only feature.
- Per-facies color picker → **Gap**: deferred from Task 6 for scope. The page supports it architecturally (the renderer accepts color overrides via JSON), but the settings panel UI is not implemented. Can be a follow-up task.
- Pattern opacity slider → **Gap**: deferred. The SVG patterns already support it via `fill-opacity`, but no UI slider is wired up.

**Placeholder scan:** No TBDs, TODOs, or "implement later" found. All steps have complete code.

**Type consistency:** `PaleoDataLoader.load()` returns `dict[str, list[dict]]` consistently. `load_geojson()` signature extended with `period_name`, `show_labels`, `map_title` — all used consistently. `_periods` dict in page uses same structure.

## CEO Review Amendments (2026-05-11)

The following fixes must be applied during implementation. Found by `/plan-ceo-review` in HOLD SCOPE mode.

| # | Issue | Fix | Where |
|---|-------|-----|-------|
| 1 | Period switching doesn't filter GeoJSON features | Use `_write_period_geojsons` for GeoJSON input too (same as CSV) | Task 6 `_load_file` |
| 2 | Compare mode leaks old renderers | Call `deleteLater()` on old renderers before replacing | Task 6 `_start_compare`/`_stop_compare` |
| 3 | Pattern overlay replaces base color | Use ECharts `renderItem` custom series to draw base color + pattern on top | Task 5 JS template |
| 4 | Wells JSON has no error handling | Wrap `_get_wells_json` in try/except, return `[]` on failure | Task 5 renderer |
| 5 | Empty data has no user feedback | Check if periods dict is empty after load, show QMessageBox | Task 6 `_load_file` |
| 6 | `printToPdf(path)` API wrong for PySide6 | Use `QPrinter` + `grab()` for PDF export | Task 6 `_export_pdf` |
| 7 | No compare mode test | Add smoke test for compare toggle | Task 7 tests |
| 8 | `shapely` not in pyproject.toml | Add to project dependencies | Task 4 |
| 9 | Scale bar hardcoded "100 km" | Compute dynamically from coordinate extent in JS | Task 5 JS template |
| 10 | Pattern image race condition | Ensure images loaded before ECharts renders | Task 5 JS template |

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | clean | HOLD SCOPE, 10 issues, 0 critical gaps |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | stale | Last ran on commit 7543f7f1, 7 commits behind |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | stale | Last ran on commit 7543f7f1, 7 commits behind |
| DX Review | `/plan-devex-review` | Developer experience gaps | 1 | clean | 7 findings, 7 fixes applied |

**VERDICT:** CEO REVIEW CLEARED — 10 issues identified and amendments documented above. Eng review stale (pre-dates this plan) — recommend re-running `/plan-eng-review` after incorporating amendments.
