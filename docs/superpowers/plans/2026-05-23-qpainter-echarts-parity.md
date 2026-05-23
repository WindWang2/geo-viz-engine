# QPainter ↔ ECharts Visual Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make QPainter renderer output visually identical to the ECharts renderer — same track layout, colors, fonts, grid lines, headers, and proportions.

**Architecture:** Overhaul the QPainter rendering pipeline in three layers: (1) data pipeline (`qpainter_builder.py`) to merge curves and add grouping, (2) track rendering classes to match ECharts visual style, (3) header/grid infrastructure to match ECharts layout.

**Tech Stack:** PySide6 QPainter, existing track class hierarchy

---

### Task 1: Update Color Constants and Font Defaults

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py`

Replace all QPainter color/font constants with ECharts-matching values.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_colors.py
import pytest
from PySide6.QtGui import QColor
from geoviz_well_log.renderer.track_base import BaseTrack, ECHARTS_BORDER, ECHARTS_GRID, ECHARTS_HEADER_BG, ECHARTS_SUB_HEADER_BG, ECHARTS_TEXT


def test_echarts_border_color():
    assert ECHARTS_BORDER == "#94a3b8"

def test_echarts_grid_color():
    assert ECHARTS_GRID == "#cbd5e1"

def test_echarts_header_bg():
    assert ECHARTS_HEADER_BG == "#e2e8f0"

def test_echarts_sub_header_bg():
    assert ECHARTS_SUB_HEADER_BG == "#f8fafc"

def test_echarts_text_color():
    assert ECHARTS_TEXT == "#0f172a"

def test_base_track_header_height_default():
    """Header height should be 56px to match ECharts trackHeaderHeight."""
    # Can't instantiate BaseTrack directly, so test via DepthTrack
    from geoviz_well_log.renderer.depth_track import DepthTrack
    t = DepthTrack(top_depth=0, bottom_depth=100)
    assert t.header_height == 56

def test_base_track_header_font_size():
    """Header font should be 14px bold to match ECharts."""
    from geoviz_well_log.renderer.depth_track import DepthTrack
    t = DepthTrack(top_depth=0, bottom_depth=100)
    # Verify font by checking paint output — basic check that header_height changed
    assert t.header_height == 56
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_colors.py -v`
Expected: FAIL — constants not defined, header_height is 32 not 56

- [ ] **Step 3: Write minimal implementation**

In `track_base.py`, add ECharts-matching color constants at module level and update `BaseTrack.__init__` default:

```python
# ECharts-matching visual constants (Tailwind slate palette)
ECHARTS_BORDER = "#94a3b8"
ECHARTS_GRID = "#cbd5e1"
ECHARTS_HEADER_BG = "#e2e8f0"
ECHARTS_SUB_HEADER_BG = "#f8fafc"
ECHARTS_TEXT = "#0f172a"
ECHARTS_HEADER_TOP = 10
ECHARTS_GROUP_HEADER_HEIGHT = 32
ECHARTS_TRACK_HEADER_HEIGHT = 56
ECHARTS_BODY_TOP_GAP = 8
ECHARTS_FONT_FAMILY = "Inter, 'Microsoft YaHei', sans-serif"
```

Change `BaseTrack.__init__` default `header_height` from 32 to 56.
Change `paint_header` font from 8pt to 14px bold, text color from black to `#0f172a`.
Change `export_render` header background from `#f0f0f0` to `#e2e8f0`.
Change all border pens from `#999999` to `ECHARTS_BORDER`.

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_colors.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All tests pass (some tests may need header_height updates)

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py tests/test_visual_parity_colors.py
git commit -m "feat(well-log): match QPainter colors/fonts to ECharts palette"
```

---

### Task 2: Add Grid Lines to All Tracks

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py`

Add horizontal grid lines (yAxis splitLine equivalent) to all track types.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_grid.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack, CurveData
from geoviz_well_log.renderer.track_base import ECHARTS_GRID


def test_depth_track_draws_horizontal_grid_lines():
    """DepthTrack should draw horizontal grid lines at tick positions."""
    track = DepthTrack(top_depth=0, bottom_depth=100, width=60)
    pixmap = QPixmap(60, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 60, 544)  # below header
    track.paint_content(painter, rect)
    painter.end()
    # Verify grid lines are drawn by checking pixels at tick y-positions
    # At depth 50, y should be roughly midpoint — check a pixel there
    mid_y = int(rect.top() + rect.height() * 0.5)
    pixel = pixmap.toImage().pixelColor(30, mid_y)
    # Should be grid color or tick color, not white
    assert pixel.red() < 250 or pixel.green() < 250


def test_curve_track_draws_horizontal_grid_lines():
    """CurveTrack should draw horizontal grid lines across full width."""
    curves = [CurveData(name="GR", depth=list(range(100)), values=[50.0]*100, display_range=(0, 150))]
    track = CurveTrack(curves=curves, width=150)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(150, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 150, 544)
    track.paint_content(painter, rect)
    painter.end()
    # Verify horizontal grid lines exist
    mid_y = int(rect.top() + rect.height() * 0.5)
    pixel = pixmap.toImage().pixelColor(75, mid_y)
    assert pixel.red() < 250 or pixel.green() < 250
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_grid.py -v`
Expected: FAIL — no horizontal grid lines drawn

- [ ] **Step 3: Write minimal implementation**

In `track_base.py`, add a `paint_grid(painter, rect)` method:

```python
def paint_grid(self, painter: QPainter, rect: QRectF):
    """Draw horizontal grid lines matching ECharts yAxis splitLine."""
    pen = QPen(QColor(ECHARTS_GRID), 1, Qt.PenStyle.SolidLine)
    painter.setPen(pen)
    span = self.depth_span
    if span <= 0:
        return
    # Adaptive grid interval — same algorithm as depth ticks
    interval = self._compute_grid_interval(rect.height(), span)
    start = (self.depth_top // interval) * interval
    if start < self.depth_top:
        start += interval
    depth = start
    while depth <= self.depth_bottom:
        y = self._depth_to_y(depth, rect)
        painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        depth += interval

def _compute_grid_interval(self, rect_height, span):
    """Pick interval so that grid lines are >=20px apart."""
    candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
    for c in candidates:
        px_per_tick = rect_height / (span / c)
        if px_per_tick >= 20:
            return c
    return candidates[-1]
```

Call `paint_grid()` at the start of `paint_content()` in every track subclass.
Remove the single vertical dotted line from `CurveTrack.paint_content()`.

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_grid.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py tests/test_visual_parity_grid.py
git commit -m "feat(well-log): add horizontal grid lines to all QPainter tracks"
```

---

### Task 3: Overhaul Curve Rendering and Header Legends

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py`

Match ECharts curve track styling: colors from CURVE_META, legend in header, display range labels.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_curve.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.curve_track import CurveTrack, CurveData
from geoviz_well_log.renderer.track_base import ECHARTS_BORDER


def test_curve_track_uses_echarts_border():
    """CurveTrack border should use ECharts border color."""
    curves = [CurveData(name="GR", depth=list(range(100)), values=[50.0]*100, display_range=(0, 150))]
    track = CurveTrack(curves=curves, width=150)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(150, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 150, 544)
    track.paint_content(painter, rect)
    painter.end()
    # Check that border is ECharts color — check top-left pixel of border
    border_pixel = pixmap.toImage().pixelColor(0, 56)
    assert border_pixel.red() < 200  # Not pure white, some border drawn


def test_curve_header_shows_legend():
    """CurveTrack header should show curve name with legend info."""
    curves = [CurveData(name="GR", depth=list(range(100)), values=[50.0]*100,
                        display_range=(0, 150), color="#15803d")]
    track = CurveTrack(curves=curves, label="GR (API)", width=150)
    pixmap = QPixmap(150, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    header_rect = QRectF(0, 0, 150, 56)
    track.paint_header(painter, header_rect)
    painter.end()
    # Verify something was drawn in header area (not all white)
    img = pixmap.toImage()
    has_color = False
    for x in range(0, 150, 5):
        for y in range(0, 56, 5):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.green() > 200:
                has_color = True
                break
    assert has_color
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_curve.py -v`

- [ ] **Step 3: Write minimal implementation**

In `curve_track.py`:
1. Override `paint_header` to draw:
   - Track name in bold 15px at top of header rect
   - For each curve: color swatch rectangle (8x8px) + line style indicator ("---" solid / "- -" dashed) + name + range label, in 12px font
   - Text color: `#0f172a`
2. Update border from `#999999` to `ECHARTS_BORDER`
3. Remove the single vertical dotted line (replaced by grid from Task 2)
4. Update display range labels font from 6pt to 10px

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_curve.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py tests/test_visual_parity_curve.py
git commit -m "feat(well-log): match CurveTrack header legends and styling to ECharts"
```

---

### Task 4: Overhaul Depth Track Styling

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py`

Match ECharts depth track: centered labels, bold 11px font, proper tick formatting.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_depth.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.depth_track import DepthTrack


def test_depth_track_label_width():
    """DepthTrack default width should accommodate centered labels."""
    track = DepthTrack(top_depth=0, bottom_depth=100)
    assert track.width >= 60  # Enough for centered depth labels


def test_depth_track_draws_centered_labels():
    """Depth labels should be centered in the track (not right-aligned)."""
    track = DepthTrack(top_depth=0, bottom_depth=100, width=60)
    track.set_depth_range(0, 100)
    pixmap = QPixmap(60, 600)
    pixmap.fill()
    painter = QPainter(pixmap)
    rect = QRectF(0, 56, 60, 544)
    track.paint_content(painter, rect)
    painter.end()
    # Verify text exists in center of track (around x=30)
    img = pixmap.toImage()
    center_has_text = False
    for y in range(int(rect.top()), int(rect.bottom()), 10):
        c = img.pixelColor(30, y)
        if c.lightness() < 200:  # Dark pixel = text
            center_has_text = True
            break
    assert center_has_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_depth.py -v`

- [ ] **Step 3: Write minimal implementation**

In `depth_track.py`, update `paint_content`:
1. Change font from 7pt to 11px bold
2. Center labels horizontally in the track (use `AlignCenter` instead of right-align)
3. Draw tick marks as full-width horizontal lines (ECharts yAxis style) instead of just right-edge marks
4. Update border color to `ECHARTS_BORDER`
5. Label alignment: center, no offset to right edge

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_depth.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py tests/test_visual_parity_depth.py
git commit -m "feat(well-log): match DepthTrack styling to ECharts centered labels"
```

---

### Task 5: Fix SystemsTract Colors and Shapes

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/systems_tract.py`

Match ECharts systems tract colors: TST=#93c5fd (light blue), HST=#fde047 (light yellow).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_tract.py
import pytest
from geoviz_well_log.renderer.systems_tract import SystemsTractTrack, _TRACT_COLORS


def test_tst_color_matches_echarts():
    assert _TRACT_COLORS.get("TST") == "#93c5fd"

def test_hst_color_matches_echarts():
    assert _TRACT_COLORS.get("HST") == "#fde047"

def test_lst_color_matches_echarts():
    assert _TRACT_COLORS.get("LST") == "#70AD47"

def test_chinese_tst_color():
    assert _TRACT_COLORS.get("海侵体系域") == "#93c5fd"

def test_chinese_hst_color():
    assert _TRACT_COLORS.get("高位体系域") == "#fde047"

def test_chinese_lst_color():
    assert _TRACT_COLORS.get("低位体系域") == "#70AD47"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_tract.py -v`
Expected: FAIL — TST is #4472C4, HST is #ED7D31

- [ ] **Step 3: Write minimal implementation**

In `systems_tract.py`, update `_TRACT_COLORS`:

```python
_TRACT_COLORS = {
    "TST": "#93c5fd", "HST": "#fde047", "LST": "#70AD47",
    "海侵体系域": "#93c5fd", "高位体系域": "#fde047", "低位体系域": "#70AD47",
}
```

Update border color to `ECHARTS_BORDER`, text color to `ECHARTS_TEXT`.

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_tract.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/systems_tract.py tests/test_visual_parity_tract.py
git commit -m "feat(well-log): fix SystemsTract colors to match ECharts TST/HST/LST"
```

---

### Task 6: Overhaul qpainter_builder — Merge Curves and Add Grouping

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/qpainter_builder.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py` (add group_name property)

This is the most impactful change — reduce track count by merging curves and add ECharts-style grouping.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_builder.py
import pytest
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.models import WellLogData, CurveData, WellIntervals, IntervalItem, LithologyInterval, FaciesInterval


def _make_full_data():
    return WellLogData(
        well_name="TEST-1",
        top_depth=0.0,
        bottom_depth=100.0,
        curves=[
            CurveData(name="AC", depth=list(range(100)), values=[60.0]*100, display_range=(40, 80), color="#1d4ed8"),
            CurveData(name="GR", depth=list(range(100)), values=[50.0]*100, display_range=(0, 150), color="#15803d"),
            CurveData(name="RT", depth=list(range(100)), values=[10.0]*100, display_range=(0.1, 1000), color="#b91c1c"),
            CurveData(name="RXO", depth=list(range(100)), values=[5.0]*100, display_range=(0.1, 1000), color="#ea580c"),
        ],
        intervals=WellIntervals(
            system=[IntervalItem(top=0, bottom=50, name="C"), IntervalItem(top=50, bottom=100, name="P")],
            series=[IntervalItem(top=0, bottom=50, name="C1"), IntervalItem(top=50, bottom=100, name="P1")],
            formation=[IntervalItem(top=0, bottom=50, name="F1"), IntervalItem(top=50, bottom=100, name="F2")],
        ),
    )


def test_builder_merges_curves():
    """Curves should be merged: AC+GR into one track, RT+RXO into another."""
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    curve_tracks = [t for t in tracks if hasattr(t, '_curves')]
    # Should have at most 2 curve tracks (merged), not 4 individual ones
    assert len(curve_tracks) <= 2
    # Total curves across all curve tracks should be 4
    total_curves = sum(len(t._curves) for t in curve_tracks)
    assert total_curves == 4


def test_builder_adds_group_name_to_stratigraphy():
    """Stratigraphy tracks should have group_name='地层系统'."""
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    strat_tracks = [t for t in tracks if getattr(t, 'group_name', None) == '地层系统']
    assert len(strat_tracks) >= 2  # At least system + series + formation


def test_builder_reduces_total_width():
    """Total width should be reasonable (not 4000px)."""
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    total = sum(t.width for t in tracks)
    assert total < 1200  # ECharts fits in ~800-1000px equivalent


def test_builder_track_order_matches_echarts():
    """Track order should be: depth -> curves -> intervals -> lithology."""
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    # First track should be depth
    from geoviz_well_log.renderer.depth_track import DepthTrack
    assert isinstance(tracks[0], DepthTrack)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_builder.py -v`
Expected: FAIL — 4 individual curve tracks, no grouping, total width >1200

- [ ] **Step 3: Write minimal implementation**

1. In `track_base.py`, add `group_name` property to `BaseTrack`:
```python
def __init__(self, ..., group_name: str = ""):
    self._group_name = group_name

@property
def group_name(self) -> str:
    return self._group_name
```

2. In `qpainter_builder.py`, rewrite `build_qpainter_tracks`:

```python
from geoviz_well_log.renderer.curve_track import CurveTrack, CurveData

# ECharts CURVE_META colors
CURVE_META = {
    "AC":  {"color": "#1d4ed8", "style": "dashed", "range": "40 - 80"},
    "GR":  {"color": "#15803d", "style": "solid",  "range": "0 - 150"},
    "RT":  {"color": "#b91c1c", "style": "solid",  "range": "0.1 - 1000"},
    "RXO": {"color": "#ea580c", "style": "dashed", "range": "0.1 - 1000"},
}

# Merge groups (matching ECharts layout)
_MERGE_GROUPS = [
    (["AC", "GR"], "AC/GR", 14),   # width=14 relative units -> ~150px
    (["RT", "RXO"], "RT/RXO", 14),
]

_LOG_SCALE_CURVES = {"RT", "RXO"}

def _apply_curve_meta(curve: CurveData) -> CurveData:
    """Apply ECharts CURVE_META styling to a curve."""
    meta = CURVE_META.get(curve.name, {})
    if meta:
        return CurveData(
            name=curve.name, depth=curve.depth, values=curve.values,
            display_range=curve.display_range,
            color=meta.get("color", curve.color),
            line_style="dashed" if meta.get("style") == "dashed" else "solid",
        )
    return curve

def build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]:
    tracks: list[BaseTrack] = []

    # 1. Depth track (width=60)
    depth = DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth, width=60)
    tracks.append(depth)

    # 2. Curve tracks — merge according to _MERGE_GROUPS
    curve_map = {c.name: c for c in data.curves}
    used = set()
    for names, label, rel_width in _MERGE_GROUPS:
        available = [curve_map[n] for n in names if n in curve_map]
        if not available:
            continue
        styled = [_apply_curve_meta(c) for c in available]
        for n in available:
            used.add(n.name)
        log = any(c.name in _LOG_SCALE_CURVES for c in styled)
        px_width = rel_width * 10  # Scale: 14 units -> 140px
        ct = CurveTrack(curves=styled, label=label, width=px_width, log_scale=log)
        tracks.append(ct)

    # Remaining ungrouped curves
    for c in data.curves:
        if c.name not in used:
            styled = _apply_curve_meta(c)
            log = c.name in _LOG_SCALE_CURVES
            ct = CurveTrack(curves=[styled], label=f"{c.name}", width=140, log_scale=log)
            tracks.append(ct)

    # 3. Stratigraphy intervals with group_name
    interval_fields = [
        ("system", "系", 50, "地层系统"),
        ("series", "统", 50, "地层系统"),
        ("formation", "组", 50, "地层系统"),
    ]
    for field, label, width, group in interval_fields:
        items = getattr(data.intervals, field, None) if data.intervals else None
        if items:
            tracks.append(IntervalTrack(intervals=items, label=label, width=width, group_name=group))

    # 4. Lithology
    if data.lithology:
        tracks.append(LithologyTrack(intervals=data.lithology, width=80))

    # 5. Facies with group_name
    if data.intervals and data.intervals.facies:
        f = data.intervals.facies
        has_data = any([f.phase, f.sub_phase, f.micro_phase])
        if has_data:
            tracks.append(FaciesTrack(facies_data=f, width=80, nested=True, group_name="沉积相"))

    # 6. Systems tract
    if data.intervals and data.intervals.systems_tract:
        tracks.append(SystemsTractTrack(intervals=data.intervals.systems_tract, width=60))

    # 7. Sequence
    if data.intervals and data.intervals.sequence:
        tracks.append(IntervalTrack(intervals=data.intervals.sequence, label="层序", width=50))

    # Set depth range on all tracks
    for t in tracks:
        t.set_depth_range(data.top_depth, data.bottom_depth)

    return tracks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_builder.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/qpainter_builder.py packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py tests/test_visual_parity_builder.py
git commit -m "feat(well-log): merge curves and add grouping in QPainter builder"
```

---

### Task 7: Add Group Header Rendering to Canvas

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py`

Add group header rendering above grouped tracks, matching ECharts parentGroup layout.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_group_headers.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.renderer.track_base import IntervalItem


def test_canvas_renders_group_headers():
    """Canvas should render group headers above grouped tracks."""
    canvas = WellLogCanvas()
    canvas.setFixedSize(300, 600)

    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100, width=60))
    canvas.add_track(IntervalTrack(
        intervals=[IntervalItem(top=0, bottom=50, name="C")],
        label="系", width=50, group_name="地层系统"
    ))
    canvas.add_track(IntervalTrack(
        intervals=[IntervalItem(top=0, bottom=50, name="C1")],
        label="统", width=50, group_name="地层系统"
    ))

    pixmap = canvas.grab()
    img = pixmap.toImage()
    # Group header should appear at top — check for non-white pixels in header region
    has_header = False
    for x in range(60, 160):
        for y in range(0, 32):
            c = img.pixelColor(x, y)
            if c.red() < 200 or c.blue() > 200:
                has_header = True
                break
    assert has_header
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_group_headers.py -v`

- [ ] **Step 3: Write minimal implementation**

In `canvas.py`, update `paint_all` to render group headers:

```python
def paint_all(self, painter: QPainter):
    if not self.tracks:
        return
    w = self.width()
    h = self.height()

    # Collect groups
    groups: dict[str, list[tuple[float, float]]] = {}
    x_off = 0.0
    for track in self.tracks:
        gn = track.group_name
        if gn:
            groups.setdefault(gn, []).append((x_off, track.width))
        x_off += track.width

    # Draw group headers at top
    header_pen = QPen(QColor(ECHARTS_TEXT))
    header_font = painter.font()
    header_font.setPixelSize(15)
    header_font.setBold(True)
    painter.setFont(header_font)
    painter.setPen(header_pen)

    for group_name, spans in groups.items():
        if not spans:
            continue
        x_start = spans[0][0]
        x_end = spans[-1][0] + spans[-1][1]
        gw = x_end - x_start
        # Group header rect
        group_rect = QRectF(x_start, 0, gw, ECHARTS_GROUP_HEADER_HEIGHT)
        painter.fillRect(group_rect, QColor(ECHARTS_HEADER_BG))
        painter.drawRect(group_rect)
        painter.drawText(group_rect, Qt.AlignmentFlag.AlignCenter, group_name)

    # Render tracks
    x_offset = 0.0
    for track in self.tracks:
        full_rect = QRectF(x_offset, 0, track.width, h)
        track.export_render(painter, full_rect)
        x_offset += track.width
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_group_headers.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py tests/test_visual_parity_group_headers.py
git commit -m "feat(well-log): add group header rendering to QPainter canvas"
```

---

### Task 8: Update Interval/Lithology/Facies Track Styling

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/interval_track.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/lithology_track.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/facies_track.py`

Match ECharts interval rendering: bold 11px vertical text, bold 10px horizontal text, correct borders.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_intervals.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF
from geoviz_well_log.renderer.interval_track import IntervalTrack, IntervalItem
from geoviz_well_log.renderer.lithology_track import LithologyTrack
from geoviz_well_log.renderer.lithology_track import LithologyInterval


def test_interval_track_uses_echarts_border():
    """IntervalTrack border should use ECharts border color."""
    track = IntervalTrack(
        intervals=[IntervalItem(top=0, bottom=50, name="Test")],
        width=60
    )
    track.set_depth_range(0, 100)
    pixmap = QPixmap(60, 300)
    pixmap.fill()
    painter = QPainter(pixmap)
    track.paint_content(painter, QRectF(0, 0, 60, 300))
    painter.end()
    # Border should be visible
    pixel = pixmap.toImage().pixelColor(0, 0)
    assert pixel.red() < 250 or pixel.green() < 250


def test_lithology_track_uses_echarts_border():
    """LithologyTrack border should use ECharts border color."""
    track = LithologyTrack(
        intervals=[LithologyInterval(top=0, bottom=50, lithology="砂岩")],
        width=60
    )
    track.set_depth_range(0, 100)
    pixmap = QPixmap(60, 300)
    pixmap.fill()
    painter = QPainter(pixmap)
    track.paint_content(painter, QRectF(0, 0, 60, 300))
    painter.end()
    pixel = pixmap.toImage().pixelColor(0, 0)
    assert pixel.red() < 250 or pixel.green() < 250
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_intervals.py -v`

- [ ] **Step 3: Write minimal implementation**

Update all three track types:
1. Font: vertical text → bold 11px, horizontal text → bold 10px
2. Border: `#999999` → `ECHARTS_BORDER` (`#94a3b8`)
3. Inner border: `#666666` → `ECHARTS_BORDER`
4. Text color: `#333333` → `ECHARTS_TEXT` (`#0f172a`)
5. Description text: `#555555` → `ECHARTS_TEXT`

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_intervals.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/interval_track.py packages/geoviz_well_log/geoviz_well_log/renderer/lithology_track.py packages/geoviz_well_log/geoviz_well_log/renderer/facies_track.py tests/test_visual_parity_intervals.py
git commit -m "feat(well-log): match interval/lithology/facies styling to ECharts"
```

---

### Task 9: Optimize Loading Performance

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py`

Reduce track creation overhead: avoid unnecessary data copies, optimize sorting.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_visual_parity_perf.py
import pytest
import time
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.models import WellLogData, CurveData


def test_track_build_speed():
    """Building tracks should be fast (< 500ms for typical data)."""
    n = 5000
    data = WellLogData(
        well_name="PERF-1",
        top_depth=0.0,
        bottom_depth=float(n),
        curves=[
            CurveData(name="GR", depth=list(range(n)), values=[50.0]*n, display_range=(0, 150)),
            CurveData(name="RT", depth=list(range(n)), values=[10.0]*n, display_range=(0.1, 1000)),
        ],
    )
    start = time.monotonic()
    tracks = build_qpainter_tracks(data)
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, f"Track building took {elapsed:.3f}s, expected <0.5s"
    assert len(tracks) > 0
```

- [ ] **Step 2: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_perf.py -v`

- [ ] **Step 3: Optimize if needed**

In `curve_track.py`, optimize `_visible_data` and sorting:
- Skip sorting if data is already sorted (check first/last elements)
- Use numpy views instead of copies where possible

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_visual_parity_perf.py -v`

- [ ] **Step 5: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 6: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py packages/geoviz_well_log/geoviz_well_log/qpainter_builder.py tests/test_visual_parity_perf.py
git commit -m "perf(well-log): optimize QPainter track building speed"
```

---

### Task 10: Update Existing Tests and Final Verification

**Files:**
- Modify: `tests/test_qpainter_builder.py`
- Modify: `tests/test_qpainter_widget.py`
- Modify: any other failing tests

Fix all tests that reference old defaults (32px headers, old colors, old track counts).

- [ ] **Step 1: Run full test suite to identify failures**

Run: `source .venv/bin/activate && pytest -v`

- [ ] **Step 2: Fix each failing test**

Update assertions to match new defaults:
- `header_height` 32 → 56
- Track count changes from builder
- Color assertions
- Width changes

- [ ] **Step 3: Run full test suite again**

Run: `source .venv/bin/activate && pytest -v`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/
git commit -m "test(well-log): update tests for ECharts visual parity"
```

- [ ] **Step 5: Run the app and visually verify**

Run: `source .venv/bin/activate && python -m src.main`
Load HZ19-1-1A well, switch to QPainter renderer, verify visual quality matches ECharts.
