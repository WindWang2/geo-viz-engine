# geoviz-well-log API Reference

> Version 1.0.0 | PySide6 QPainter-based well log visualization

## Installation

```bash
pip install geoviz-well-log
```

**Dependencies:** PySide6 >= 6.5, pydantic >= 2.0

**Optional:** numpy (for curve downsampling performance)

## Quick Start

```python
from PySide6.QtWidgets import QApplication
from geoviz_well_log import (
    WellLogData, CurveData, IntervalItem, WellIntervals,
    build_qpainter_tracks, WellLogCanvas,
)

app = QApplication([])

# 1. Prepare data
data = WellLogData(
    well_name="Well-1",
    top_depth=1000.0,
    bottom_depth=2000.0,
    curves=[
        CurveData(name="GR", depth=[1000, 1010, 1020], values=[40, 55, 30],
                  display_range=(0, 150), color="#15803d"),
    ],
    intervals=WellIntervals(
        system=[IntervalItem(top=1000, bottom=1500, name="志留系")],
        lithology=[IntervalItem(top=1000, bottom=1200, name="砂岩")],
    ),
)

# 2. Build tracks
tracks = build_qpainter_tracks(data)

# 3. Display
canvas = WellLogCanvas()
canvas.set_tracks(tracks)
canvas.resize(800, 600)
canvas.show()

app.exec()
```

---

## Data Models

### `WellLogData`

Top-level data container for a single well.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `well_name` | `str` | required | Well identifier |
| `top_depth` | `float` | required | Top depth (meters) |
| `bottom_depth` | `float` | required | Bottom depth (meters) |
| `datum_elevation` | `float` | `0.0` | Datum elevation |
| `curves` | `list[CurveData]` | `[]` | Log curve data |
| `lithology` | `list[LithologyInterval]` | `[]` | Lithology intervals |
| `facies` | `list[FaciesInterval]` | `[]` | Facies intervals |
| `intervals` | `WellIntervals \| None` | `None` | Stratigraphy intervals |
| `custom_tracks` | `list[dict]` | `[]` | Custom track data |

### `CurveData`

Single log curve with depth-value pairs.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | `str` | required | Curve name (e.g. "GR", "RT") |
| `depth` | `list[float]` | required | Depth samples |
| `values` | `list[float]` | required | Log values |
| `display_range` | `tuple[float, float]` | `(0, 100)` | Display min/max |
| `color` | `str` | `"#63b3ed"` | Curve color (hex) |
| `line_style` | `LineStyle` | `SOLID` | `SOLID`, `DASHED`, or `DOTTED` |

### `IntervalItem`

Generic depth interval (used for stratigraphy, lithology, etc.).

| Field | Type | Description |
|-------|------|-------------|
| `top` | `float` | Top depth |
| `bottom` | `float` | Bottom depth |
| `name` | `str` | Interval name/label |

### `WellIntervals`

Container for all stratigraphic interval types.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `system` | `list[IntervalItem]` | `[]` | 系 (System) |
| `series` | `list[IntervalItem]` | `[]` | 统 (Series) |
| `formation` | `list[IntervalItem]` | `[]` | 组 (Formation) |
| `member` | `list[IntervalItem]` | `[]` | 段 (Member) |
| `lithology` | `list[IntervalItem]` | `[]` | 岩性 (Lithology) |
| `lithology_desc` | `list[IntervalItem]` | `[]` | 岩性描述 |
| `systems_tract` | `list[IntervalItem]` | `[]` | 体系域 |
| `sequence` | `list[IntervalItem]` | `[]` | 层序 |
| `facies` | `FaciesData` | `FaciesData()` | 沉积相 |

### `LithologyInterval`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `top` | `float` | required | Top depth |
| `bottom` | `float` | required | Bottom depth |
| `lithology` | `str` | required | Lithology name |
| `description` | `str` | `""` | Description text |

### `FaciesData`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `phase` | `list[IntervalItem]` | `[]` | 相 (Phase) |
| `sub_phase` | `list[IntervalItem]` | `[]` | 亚相 |
| `micro_phase` | `list[IntervalItem]` | `[]` | 微相 |

### `LineStyle`

```python
class LineStyle(str, Enum):
    SOLID = "solid"
    DASHED = "dashed"
    DOTTED = "dotted"
```

---

## Track Builder

### `build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]`

Convert `WellLogData` into a list of track objects ready for `WellLogCanvas`. Creates tracks for:
- Depth ruler
- Log curves (auto-merged: AC/GR and RT/RXO)
- Stratigraphy columns (系, 统, 组) grouped under "地层系统"
- Lithology with SVG pattern fills
- Facies (nested 3-column: phase/sub-phase/micro-phase)
- Systems tract (TST/HST/LST shapes)
- Sequence column
- Lithology description

Curve colors and merge groups follow the built-in `CURVE_META` configuration:

| Curve | Color | Style |
|-------|-------|-------|
| AC | `#1d4ed8` | dashed |
| GR | `#15803d` | solid |
| RT | `#b91c1c` | solid |
| RXO | `#ea580c` | dashed |

---

## Canvas & Display

### `WellLogCanvas`

Main widget that manages track layout and rendering.

```python
canvas = WellLogCanvas()
canvas.set_tracks(tracks)            # Set all tracks at once
canvas.add_track(track)              # Add single track
canvas.remove_track(track)           # Remove a track
canvas.set_depth_range(top, bottom)  # Set visible depth range
canvas.paint_all(painter)            # Render to any QPainter
```

**Signals:**
- `depth_range_changed(float, float)` — emitted when depth range changes

**Properties:**
- `tracks` — list of `BaseTrack`
- `total_width` — sum of all track widths

### `LayoutCoordinator`

Synchronizes depth range across tracks.

---

## Track Types

All tracks inherit from `BaseTrack`.

### `BaseTrack` (abstract)

```python
track.label            # str: display name
track.width            # int: pixel width
track.header_height    # int: header band height
track.group_name       # str: group header (e.g. "地层系统")
track.depth_top        # float
track.depth_bottom     # float
track.depth_span       # float (read-only)
track.set_depth_range(top, bottom)
track.paint_content(painter, rect)
track.paint_header(painter, rect)
track.export_render(painter, full_rect, canvas_header_height=None)
```

### `DepthTrack`

Depth ruler with adaptive tick spacing.

```python
DepthTrack(top_depth=0, bottom_depth=100, width=60, label="Depth")
```

### `CurveTrack`

Log curve renderer with viewport culling and adaptive downsampling.

```python
CurveTrack(curves=[curve1, curve2], label="AC/GR", width=140, log_scale=False)
```

Supports 1-3 curves per track. Handles linear and logarithmic scales.

### `IntervalTrack`

Generic interval column for stratigraphy, descriptions, etc.

```python
IntervalTrack(intervals=[...], label="组", width=50, colors={}, group_name="地层系统")
```

### `LithologyTrack`

Lithology column with SVG pattern fills and fuzzy name matching.

```python
LithologyTrack(intervals=[...], label="岩性", width=80, show_description=True)
```

Uses `PatternEngine` for SVG texture fills. Lithology names like "浅灰色粉砂岩" are fuzzy-matched to "粉砂岩" → `siltstone` pattern.

### `FaciesTrack`

Facies column with SVG pattern fills, supports nested 3-column display.

```python
FaciesTrack(facies_data=facies_data, width=80, nested=True, group_name="沉积相", label="沉积相")
```

When `nested=True`, displays phase / sub_phase / micro_phase in 3 equal-width columns.

### `SystemsTractTrack`

Systems tract column with TST/HST/LST geometric shapes.

```python
SystemsTractTrack(intervals=[...], width=60)
```

| Name contains | Shape | Color |
|--------------|-------|-------|
| TST / 海侵体系域 | Triangle up | `#93c5fd` |
| HST / 高位体系域 | Triangle down | `#fde047` |
| LST / 低位体系域 | Rectangle | `#70ad47` |

---

## SVG Pattern Engine

### `PatternEngine`

Caches SVG pattern files as tiled `QBrush` objects.

```python
engine = PatternEngine(tile_size=20)

brush = engine.get_brush("砂岩")        # Returns QBrush or None
color = engine.get_color("砂岩")         # Returns QColor or None
```

Supports fuzzy substring matching: "浅灰色粉砂岩" → matches "粉砂岩" → loads `siltstone.svg`.

**Built-in patterns (17 SVG files):**

| Pattern ID | Lithology/Facies Keys |
|-----------|----------------------|
| `sandstone` | 砂岩, 砂坪, 砂质陆棚, 滨岸, 前滨, 临滨 |
| `mudstone` | 泥岩, 泥坪, 泥质陆棚, 碎屑岩潮坪 |
| `limestone` | 灰岩, 碳酸盐台地, 生物礁 |
| `dolomite` | 白云岩 |
| `shale` | 页岩 |
| `siltstone` | 粉砂岩 |
| `sand-flat` | 砂坪 |
| `mud-flat` | 泥坪 |
| `dolomitic-flat` | 云质坪, 混积潮坪 |
| `tidal-flat` | 潮坪, 碎屑岩潮坪 |
| `muddy-shelf` | 泥质陆棚 |
| `sandy-shelf` | 砂质陆棚 |
| `sand-mud-shelf` | 砂泥质陆棚 |
| `clastic-shelf` | 碎屑岩浅水陆棚 |
| `mixed` | 混积浅水陆棚, 混积 |
| `shelf` | 陆棚 |
| `delta` | 三角洲 |
| `reef` | 生物礁, 礁 |
| `evaporite` | 蒸发岩, 膏盐 |
| `glacial` | 冰川, 冰碛 |
| `volcanic` | 火山岩, 熔岩 |
| `metamorphic` | 变质岩 |
| `alluvial` | 冲积扇, 洪积扇 |
| `lagoon` | 潟湖, 局限台地 |

---

## Interaction

### `ZoomPanHandler`

Mouse wheel zoom and drag-pan for a canvas inside a scroll area.

```python
handler = ZoomPanHandler(canvas, scroll_area)
handler.set_full_range(top, bottom)
```

- **Mouse wheel** — zoom in/out centered on cursor
- **Double click** — reset to full depth range
- **Drag** — pan up/down

### `CrosshairOverlay`

Semi-transparent hover panel showing depth and track values at cursor position.

```python
overlay = CrosshairOverlay(canvas)
overlay.set_cursor_y(y_pixels)
overlay.paint_overlay(painter, rect)
```

---

## Vector Export

### `export_svg(canvas, path)`

Export to SVG — fully vector, identical to display rendering.

### `export_pdf(canvas, path)`

Export to PDF — fully vector, page size matches canvas aspect ratio.

### `export_png(canvas, path)`

Export to PNG — raster screenshot of current display.

```python
from geoviz_well_log import export_svg, export_pdf, export_png

export_svg(canvas, "well_log.svg")
export_pdf(canvas, "well_log.pdf")
export_png(canvas, "well_log.png")
```

---

## Pattern Maps

### `PATTERN_MAP`

`dict[str, str]` — Maps Chinese lithology/facies names to SVG pattern IDs.

### `FACIES_COLORS`

`dict[str, str]` — Maps lithology/facies names to hex colors (fallback when no SVG pattern available).

---

## Complete Example

```python
from PySide6.QtWidgets import QApplication, QScrollArea
from geoviz_well_log import (
    WellLogData, CurveData, IntervalItem, WellIntervals, FaciesData,
    build_qpainter_tracks, WellLogCanvas, ZoomPanHandler,
    export_svg, export_pdf,
)

app = QApplication([])

# Build data
data = WellLogData(
    well_name="LA1",
    top_depth=500.0,
    bottom_depth=1500.0,
    curves=[
        CurveData(name="GR", depth=[500, 510, 520, 530], values=[45, 60, 35, 50],
                  display_range=(0, 150), color="#15803d"),
        CurveData(name="RT", depth=[500, 510, 520, 530], values=[2.5, 8.0, 1.2, 5.0],
                  display_range=(0.2, 2000), color="#b91c1c"),
    ],
    intervals=WellIntervals(
        system=[IntervalItem(top=500, bottom=1500, name="侏罗系")],
        formation=[IntervalItem(top=500, bottom=1000, name="自流井组")],
        lithology=[IntervalItem(top=500, bottom=800, name="砂岩"),
                   IntervalItem(top=800, bottom=1500, name="泥岩")],
        facies=FaciesData(
            phase=[IntervalItem(top=500, bottom=1000, name="三角洲"),
                   IntervalItem(top=1000, bottom=1500, name="滨岸")],
        ),
        systems_tract=[
            IntervalItem(top=500, bottom=1000, name="TST"),
            IntervalItem(top=1000, bottom=1500, name="HST"),
        ],
    ),
)

# Build and display
tracks = build_qpainter_tracks(data)

scroll = QScrollArea()
canvas = WellLogCanvas()
canvas.set_tracks(tracks)
handler = ZoomPanHandler(canvas, scroll)

scroll.setWidget(canvas)
scroll.setWidgetResizable(True)
scroll.resize(900, 700)
scroll.show()

# Export
export_svg(canvas, "la1_well_log.svg")
export_pdf(canvas, "la1_well_log.pdf")

app.exec()
```
