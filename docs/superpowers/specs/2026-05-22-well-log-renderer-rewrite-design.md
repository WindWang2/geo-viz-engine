# Well Log Renderer Rewrite — Design Spec

## Problem

Current well log rendering uses ECharts (Canvas renderer) inside QWebEngineView. This causes:

1. **Display ≠ export inconsistency** — Canvas display vs SVG export are two different rendering paths. Custom `renderItem` (lithology patterns, interval columns) may produce subtle differences between screen and SVG/PDF output.
2. **Performance bottleneck** — ECharts renders ALL data points at once. Wells with >5000 samples take seconds to load; >10000 samples can freeze.
3. **Windows black screen** — QWebEngineView conflicts with pyqtgraph OpenGL contexts on Windows (addressed separately in black screen fix).

## Goal

Rewrite the well log rendering engine using pure QPainter. Every visual element uses the same `paint(painter, rect, depth_range)` method for both display and export. The painter's device changes (screen / QSvgGenerator / QPrinter), but the rendering code is identical — guaranteeing display = export consistency.

**Package requirement:** `pip install geoviz-well-log` works in any PySide6 project. Object-oriented, independently packaged.

## Architecture

```
geoviz_well_log/
├── renderer/                    # New QPainter rendering engine
│   ├── canvas.py                # WellLogCanvas (main widget)
│   ├── track_base.py            # BaseTrack abstract base
│   ├── depth_track.py           # Depth ruler
│   ├── curve_track.py           # Log curves (QPainterPath)
│   ├── interval_track.py        # Generic interval column
│   ├── lithology_track.py       # Lithology with SVG patterns
│   ├── systems_tract.py         # TST/HST triangles
│   ├── text_track.py            # Text description
│   ├── core_track.py            # Core recovery intervals
│   ├── oil_show_track.py        # Hydrocarbon show levels
│   ├── gas_curve_track.py       # Gas chromatograph curves
│   ├── rop_track.py             # Rate of penetration curve
│   ├── core_point_track.py      # Sidewall core markers
│   ├── sample_track.py          # Cuttings description column
│   ├── porosity_track.py        # Core porosity bars
│   ├── permeability_track.py    # Core permeability bars (log scale)
│   ├── temperature_track.py     # Borehole temperature curve
│   ├── overlay.py               # Crosshair + tooltip overlay
│   └── coordinator.py           # LayoutCoordinator (depth sync)
├── models.py                    # Extended Pydantic models
├── payload_builder.py           # build_tracks_from_data() (extended)
├── export.py                    # Unified QPainter export
├── pattern_map.py               # PATTERN_MAP (unchanged)
├── chart_engine.py              # Old ECharts backend (preserved, not deleted)
└── ...
```

## Core Abstraction: `paint(painter, rect, depth_range)`

Every track implements a `paint_content` method that receives a QPainter. For display, the painter points to the widget. For SVG export, it points to a QSvgGenerator. For PDF export, it points to a QPrinter. The same drawing commands produce native vector elements in each format.

```python
class BaseTrack(QWidget):
    header_height: int = 32
    width: int

    def set_depth_range(self, top: float, bottom: float):
        """Set visible depth range, triggers viewport culling + repaint."""

    def paint_content(self, painter: QPainter, rect: QRectF):
        """Render track content area (no header)."""

    def paint_header(self, painter: QPainter, rect: QRectF):
        """Render track header (label, scale range)."""

    def export_render(self, painter: QPainter, full_rect: QRectF):
        """Export: header + content rendered together to painter."""
```

## Export Consistency

```python
# export.py

def export_svg(canvas: WellLogCanvas, path: str):
    generator = QSvgGenerator()
    generator.setFileName(path)
    generator.setSize(canvas.size())
    painter = QPainter(generator)
    canvas.paint_all(painter)    # same paint code as display
    painter.end()

def export_pdf(canvas: WellLogCanvas, path: str):
    printer = QPrinter()
    printer.setOutputFileName(path)
    printer.setPageSize(QPageSize(QSizeF(canvas.width(), canvas.height()), QPageSize.Unit.Point))
    painter = QPainter(printer)
    canvas.paint_all(painter)    # same paint code as display
    painter.end()

def export_png(canvas: WellLogCanvas, path: str):
    pixmap = canvas.grab()
    pixmap.save(path)
```

No rasterization in SVG/PDF output. All drawing primitives (lines, polygons, text, patterns) are native vector elements.

## Track Types (15 total)

### Base Tracks (feature parity with current ECharts)

1. **DepthTrack** — Depth ruler with adaptive tick spacing (1m/5m/10m/50m/100m). Zoom adjusts density automatically.
2. **CurveTrack** — Log curves via QPainterPath. Supports: multi-curve overlay, linear/logarithmic scale, line styles (solid/dashed/dotted), display range, background interval coloring.
3. **IntervalTrack** — Generic interval column (stratigraphy, facies, sequence). Color fill + text label (horizontal/vertical rotation). Parent-child grouping for expandable headers.
4. **LithologyTrack** — Lithology column with SVG pattern fills via QBrush. Reuses existing PATTERN_MAP (35 entries). Patterns cached as QPixmap at startup.
5. **SystemsTractTrack** — TST (blue upward triangle) / HST (yellow downward triangle) via QPolygonF.
6. **TextTrack** — Word-wrapped text with CJK font fallback. Auto-sizing font.

### Mudlog Tracks (new — from SY/T 5599 standard)

7. **CoreTrack** — Core recovery intervals. Shows run number, footage, core length, recovery percentage. Rendered as segmented rectangles with percentage labels.
8. **OilShowTrack** — Hydrocarbon show levels: 饱含油/富含油/油浸/油斑/油迹/荧光. Six-level color gradient interval column.
9. **GasCurveTrack** — Gas chromatograph curves (total gas, C1–C5). Multi-curve overlay similar to CurveTrack.
10. **ROPTrack** — Rate of penetration curve (min/m vs depth). Reverse scale (high on left, low on right).
11. **CorePointTrack** — Sidewall core point markers. Scatter symbols with sequential numbering.
12. **SampleTrack** — Cuttings/sample description column. Color bands + text annotations.

### Analysis Tracks (new — for crossplot/histogram sub-project)

13. **PorosityTrack** — Core porosity horizontal bar chart.
14. **PermeabilityTrack** — Core permeability horizontal bar chart with logarithmic scale.
15. **TemperatureTrack** — Borehole temperature curve via QPainterPath.

## WellLogCanvas

```python
class WellLogCanvas(QWidget):
    def add_track(self, track: BaseTrack, position: int = -1)
    def remove_track(self, index: int)
    def set_depth_range(self, top: float, bottom: float)
    def set_tracks(self, tracks: list[BaseTrack])
    def paint_all(self, painter: QPainter)
    def export_svg(self, path: str)
    def export_pdf(self, path: str)
    def export_png(self, path: str)

    depth_range_changed = Signal(float, float)
    interval_clicked = Signal(str, float, float)
    cursor_moved = Signal(float)
```

Layout: tracks arranged horizontally. Each track has fixed width (user-adjustable). Header region at top (32px). Content region shares synchronized depth range via LayoutCoordinator.

## Performance Optimization

### 1. Viewport Culling

Only data within visible depth range is rendered. Binary search (`bisect`) to find visible slice in O(log n).

```python
def _visible_data(self, depth_range):
    top, bottom = depth_range
    start = bisect.bisect_left(self._depths, top)
    end = bisect.bisect_right(self._depths, bottom)
    return self._depths[start:end], self._values[start:end]
```

### 2. Adaptive Downsampling (Min-Max)

When visible data points exceed pixel height × 2, downsample preserving extremes:

```python
def _adaptive_downsample(depths, values, pixel_height):
    if len(depths) <= pixel_height * 2:
        return depths, values
    step = len(depths) // pixel_height
    result_d, result_v = [], []
    for i in range(0, len(depths), step):
        chunk = values[i:i+step]
        max_idx = i + np.argmax(chunk)
        min_idx = i + np.argmin(chunk)
        result_d.extend([depths[max_idx], depths[min_idx]])
        result_v.extend([values[max_idx], values[min_idx]])
    return result_d, result_v
```

Preserves peaks and valleys — curve shape is maintained.

### 3. QPainterPath Caching

Cache the QPainterPath for the current visible region. On depth pan: compute delta, shift existing path, only append new segments. On depth zoom: rebuild path.

### Performance Targets

| Data Size | Current ECharts | Target QPainter |
|-----------|----------------|-----------------|
| 1,000 pts | ~500ms | < 16ms (60fps) |
| 5,000 pts | ~2s | < 16ms |
| 10,000 pts | ~5s | < 32ms |
| 50,000 pts | freeze | < 50ms |

## Data Models (Extended)

New Pydantic models for mudlog data:

```python
class CoreInterval(BaseModel):
    top: float; bottom: float
    run_number: int
    recovered: float          # core length (m)
    percentage: float         # recovery rate (%)

class OilShowInterval(BaseModel):
    top: float; bottom: float
    level: str                # 饱含油/富含油/油浸/油斑/油迹/荧光

class GasReading(BaseModel):
    depth: float
    total_gas: float          # (%)
    c1: float; c2: float; c3: float; c4: float; c5: float

class SidewallCore(BaseModel):
    depth: float
    number: int
    lithology: str
    oil_show: str

class ROPData(BaseModel):
    depths: list[float]
    rop_values: list[float]   # min/m
```

Extended WellLogData (all new fields Optional):

```python
class WellLogData(BaseModel):
    # Existing fields unchanged
    well_name: str
    curves: list[CurveData]
    lithology: list[LithologyInterval]
    facies: list[FaciesInterval]
    ...
    # New mudlog fields (all optional)
    core_intervals: list[CoreInterval] = []
    oil_shows: list[OilShowInterval] = []
    gas_readings: list[GasReading] = []
    sidewall_cores: list[SidewallCore] = []
    rop_data: ROPData | None = None
    temperatures: list[tuple[float, float]] = []
```

## Interaction Enhancement

| Feature | Implementation |
|---------|---------------|
| Crosshair cursor | Overlay widget, QPainter drawLine |
| Tooltip | Depth + all curve values + lithology + facies |
| Depth zoom/pan | Mouse wheel zoom, drag pan, adjust depth_range |
| Interval click | Click on interval emits signal (for cross-well correlation) |
| Curve value annotation | Hover shows value label on curve |
| Track width resize | Drag track border to adjust width |

## build_tracks_from_data() Logic

Auto-builds all tracks from WellLogData. Creates a track only if corresponding data exists:

1. DepthTrack (always)
2. CurveTrack for each curve in `curves[]`
3. IntervalTrack for stratigraphy (system/series/formation/member)
4. LithologyTrack if `lithology[]` is non-empty
5. IntervalTrack for facies (micro/sub/phase)
6. SystemsTractTrack if `systems_tract` data exists
7. IntervalTrack for sequence if `sequence` data exists
8. CoreTrack if `core_intervals[]` is non-empty
9. OilShowTrack if `oil_shows[]` is non-empty
10. GasCurveTrack if `gas_readings[]` is non-empty
11. ROPTrack if `rop_data` exists
12. CorePointTrack if `sidewall_cores[]` is non-empty
13. TextTrack for lithology descriptions if available

## Files Modified

- `packages/geoviz_well_log/geoviz_well_log/renderer/` — 19 new files
- `packages/geoviz_well_log/geoviz_well_log/models.py` — Add new Pydantic models
- `packages/geoviz_well_log/geoviz_well_log/payload_builder.py` — Extend build_tracks_from_data
- `packages/geoviz_well_log/geoviz_well_log/export.py` — Rewrite for QPainter export
- `packages/geoviz_well_log/geoviz_well_log/__init__.py` — Export new API
- `src/pages/well_log/` — Switch from ChartEngine to WellLogCanvas

## Out of Scope

- Crossplot and histogram views (separate sub-project)
- Multi-well statistical view (separate sub-project)
- pyqtgraph dependency (pure QPainter, no pyqtgraph needed)
- Deleting old ECharts backend (preserved for backward compatibility)
- Cross-well page rewrite (uses ChartEngine, will migrate later)

## References

- SY/T 5599-2006 油气探井完井地质图件编制规范
- SLB Defining Series: Basic Well Log Interpretation
- Energistics Standard Legend 1995
- GB/T 勘探管理图件图册编制规范 附录M/O (existing pattern standard)
