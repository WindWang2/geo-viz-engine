# Well Log Renderer Plan 2 — Track Types + Interaction Design

**Parent spec:** `2026-05-22-well-log-renderer-rewrite-design.md`
**Depends on:** Plan 1 (core infrastructure — BaseTrack, DepthTrack, CurveTrack, WellLogCanvas, LayoutCoordinator, export)

## Goal

Add 4 interval/track types and mouse interaction to the QPainter renderer so it can render the full set of geological columns that the ECharts path currently supports.

## New Files

```
renderer/
├── pattern_engine.py     # SVG pattern → QBrush cache (shared by LithologyTrack)
├── interval_track.py     # Generic stratigraphy interval column
├── lithology_track.py    # Lithology column with SVG pattern fills
├── facies_track.py       # Facies column with color fills
├── systems_tract.py      # TST/HST triangle track
├── interaction.py        # ZoomPanHandler (wheel zoom + drag pan)
└── overlay.py            # CrosshairOverlay (depth cursor + tooltip)
```

Tests:
```
tests/
├── test_pattern_engine.py
├── test_interval_track.py
├── test_lithology_track.py
├── test_facies_track.py
├── test_systems_tract.py
├── test_interaction.py
└── test_overlay.py
```

## Track Details

### PatternEngine

Shared singleton that loads the 17 SVG pattern files from `assets/patterns/` and converts them to `QBrush` objects. Caches by pattern ID so each SVG is parsed once.

- `get_brush(pattern_id: str, size: int = 20) -> QBrush` — returns tiled pattern brush
- `get_color(lithology_name: str) -> QColor | None` — maps Chinese lithology name to fallback color
- Loads from `PATTERN_MAP` (38 entries) for name → pattern_id lookup

### IntervalTrack

Generic interval column for stratigraphy (system/series/formation/member), lithology descriptions, and any other text-labeled depth intervals.

- Input: `list[IntervalItem]` (top, bottom, name) + optional color dict
- Rendering: alternating color rectangles from a 6-color pastel palette, centered text label
- Border lines between intervals
- Text rotation: horizontal for wide tracks, vertical for narrow (< 50px)

### LithologyTrack

Lithology column with SVG pattern fills — the primary geological column.

- Input: `list[LithologyInterval]` (top, bottom, lithology, description)
- Rendering: each interval filled with tiled SVG pattern via `PatternEngine.get_brush()`
- Falls back to solid pastel color if pattern not found
- Description text drawn vertically along right edge
- Border lines between intervals

### FaciesTrack

Facies column with `FACIES_COLORS` fills. Supports three display modes.

- Input: `FaciesData` (phase/sub_phase/micro_phase each `list[IntervalItem]`)
- Rendering mode 1 (default): single column showing the most specific level available
- Rendering mode 2: three-column nested view (phase | sub_phase | micro_phase side by side)
- Color from `FACIES_COLORS` dict, fallback to pastel palette
- Label text centered in each interval

### SystemsTractTrack

Systems tract column with geometric shape fills.

- Input: `list[IntervalItem]` (top, bottom, name) where name is TST/HST/etc.
- Rendering:
  - TST (海侵体系域): upward-pointing triangle, blue fill (#4472C4)
  - HST (高位体系域): downward-pointing triangle, orange fill (#ED7D31)
  - LST (低位体系域): rectangle, green fill (#70AD47)
  - Unknown: rectangle, gray fill
- Label text centered

## Interaction

### ZoomPanHandler

Event filter installed on `WellLogCanvas` via `installEventFilter()`.

- **Mouse wheel**: zoom depth range by 20%, centered on cursor y-position. Clamped to data bounds.
- **Middle-button drag** or **Ctrl+left drag**: pan depth range. Clamped to data bounds.
- **Double-click**: reset to full depth range.
- Calls `canvas.set_depth_range()` which propagates via LayoutCoordinator to all tracks.

### CrosshairOverlay

Transparent overlay widget rendered on top of the canvas.

- Horizontal dashed line at cursor y-position
- Depth label tooltip at cursor (e.g., "2543.5 m")
- Only visible while mouse is inside canvas
- Uses `WA_TransparentForMouseEvents` so clicks pass through to canvas
- Repaints on `cursor_moved` signal from canvas

## Task Order (TDD)

1. PatternEngine — test + implement + commit
2. IntervalTrack — test + implement + commit
3. LithologyTrack — test + implement + commit
4. FaciesTrack — test + implement + commit
5. SystemsTractTrack — test + implement + commit
6. ZoomPanHandler — test + implement + commit
7. CrosshairOverlay — test + implement + commit
8. Update `__init__.py` exports + run full suite

## Out of Scope (deferred to Plan 3+)

- Integration with WellLogPage (switch from ECharts)
- build_tracks_from_data() extension for new track types
- Mudlog tracks (CoreTrack, OilShowTrack, GasCurveTrack, ROPTrack, etc.)
- Track width resize by dragging borders
- Curve value hover annotation
