# QPainter Data Pipeline — Plan 3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]` that converts WellLogData directly into QPainter track objects for WellLogCanvas.

**Architecture:** New function `build_qpainter_tracks()` in `qpainter_builder.py` reads WellLogData fields and produces a list of typed BaseTrack subclasses. It inspects `data.curves`, `data.lithology`, `data.intervals` and creates the appropriate track objects. The function is pure — no Qt dependency, no widget creation.

**Tech Stack:** PySide6, Pydantic, numpy

---

## File Structure

```
packages/geoviz_well_log/geoviz_well_log/
├── qpainter_builder.py    # NEW: build_qpainter_tracks()
├── __init__.py            # MODIFY: export build_qpainter_tracks
├── renderer/
│   ├── depth_track.py     # (existing)
│   ├── curve_track.py     # (existing)
│   ├── interval_track.py  # (existing)
│   ├── lithology_track.py # (existing)
│   ├── facies_track.py    # (existing)
│   └── systems_tract.py   # (existing)
└── models.py              # (existing — WellLogData, CurveData, etc.)

tests/
└── test_qpainter_builder.py  # NEW
```

---

### Task 1: build_qpainter_tracks — test + implement + export

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/qpainter_builder.py`
- Create: `tests/test_qpainter_builder.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/__init__.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_qpainter_builder.py
import pytest
import numpy as np

from geoviz_well_log.models import (
    WellLogData, CurveData, LithologyInterval, FaciesInterval,
    IntervalItem, WellIntervals, FaciesData, LineStyle,
)
from geoviz_well_log.qpainter_builder import build_qpainter_tracks
from geoviz_well_log.renderer import (
    DepthTrack, CurveTrack, IntervalTrack,
    LithologyTrack, FaciesTrack, SystemsTractTrack,
)


def _make_full_data():
    """Create a WellLogData with all track types populated."""
    depths = np.linspace(2500, 2600, 100).tolist()
    return WellLogData(
        well_name="Test-1",
        top_depth=2500.0,
        bottom_depth=2600.0,
        curves=[
            CurveData(name="GR", unit="API", depth=depths,
                      values=np.random.uniform(10, 120, 100).tolist(),
                      display_range=(0, 150), color="#22c55e"),
            CurveData(name="AC", unit="us/ft", depth=depths,
                      values=np.random.uniform(40, 80, 100).tolist(),
                      display_range=(40, 240), color="#3b82f6",
                      line_style=LineStyle.DASHED),
            CurveData(name="RT", unit="ohm.m", depth=depths,
                      values=np.random.uniform(0.5, 200, 100).tolist(),
                      display_range=(0.2, 2000), color="#ef4444"),
        ],
        lithology=[
            LithologyInterval(top=2500, bottom=2530, lithology="砂岩", description="中砂岩"),
            LithologyInterval(top=2530, bottom=2560, lithology="泥岩", description="深灰色泥岩"),
            LithologyInterval(top=2560, bottom=2600, lithology="灰岩", description="生物灰岩"),
        ],
        facies=[
            FaciesInterval(top=2500, bottom=2530, facies="三角洲前缘"),
            FaciesInterval(top=2530, bottom=2600, facies="碳酸盐台地"),
        ],
        intervals=WellIntervals(
            system=[IntervalItem(top=2500, bottom=2600, name="中生界")],
            series=[IntervalItem(top=2500, bottom=2550, name="白垩系"),
                    IntervalItem(top=2550, bottom=2600, name="侏罗系")],
            formation=[IntervalItem(top=2500, bottom=2600, name="Test组")],
            systems_tract=[
                IntervalItem(top=2500, bottom=2550, name="TST"),
                IntervalItem(top=2550, bottom=2600, name="HST"),
            ],
            sequence=[IntervalItem(top=2500, bottom=2600, name="SQ1")],
            facies=FaciesData(
                phase=[IntervalItem(top=2500, bottom=2600, name="三角洲")],
                sub_phase=[IntervalItem(top=2500, bottom=2550, name="前三角洲"),
                           IntervalItem(top=2550, bottom=2600, name="三角洲前缘")],
                micro_phase=[IntervalItem(top=2500, bottom=2530, name="河口坝"),
                             IntervalItem(top=2530, bottom=2600, name="远砂坝")],
            ),
        ),
    )


def test_build_tracks_full_data():
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    # Should have: Depth + 3 curves + system + series + formation +
    # lithology + facies(list) + systems_tract + sequence + facies(FaciesData)
    assert len(tracks) >= 8
    types = [type(t).__name__ for t in tracks]
    assert "DepthTrack" in types
    assert "CurveTrack" in types
    assert "LithologyTrack" in types
    assert "FaciesTrack" in types
    assert "SystemsTractTrack" in types


def test_build_tracks_has_depth():
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    depth_tracks = [t for t in tracks if isinstance(t, DepthTrack)]
    assert len(depth_tracks) == 1


def test_build_tracks_curves_count():
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    curve_tracks = [t for t in tracks if isinstance(t, CurveTrack)]
    assert len(curve_tracks) == 3


def test_build_tracks_rt_is_log_scale():
    data = _make_full_data()
    tracks = build_qpainter_tracks(data)
    rt_track = [t for t in tracks if isinstance(t, CurveTrack) and "RT" in t.label]
    assert len(rt_track) == 1
    assert rt_track[0]._log_scale is True


def test_build_tracks_empty_data():
    """Minimal data — only DepthTrack created."""
    data = WellLogData(well_name="Empty", top_depth=0, bottom_depth=100)
    tracks = build_qpainter_tracks(data)
    assert len(tracks) == 1
    assert isinstance(tracks[0], DepthTrack)


def test_build_tracks_no_intervals():
    """Curves + lithology but no intervals."""
    data = WellLogData(
        well_name="Partial",
        top_depth=0,
        bottom_depth=100,
        curves=[CurveData(name="GR", depth=list(range(100)),
                          values=[50.0] * 100, display_range=(0, 150))],
        lithology=[LithologyInterval(top=0, bottom=50, lithology="砂岩"),
                   LithologyInterval(top=50, bottom=100, lithology="泥岩")],
    )
    tracks = build_qpainter_tracks(data)
    types = [type(t).__name__ for t in tracks]
    assert "DepthTrack" in types
    assert "CurveTrack" in types
    assert "LithologyTrack" in types
    # No IntervalTrack since intervals=None
    interval_tracks = [t for t in tracks if isinstance(t, IntervalTrack)]
    assert len(interval_tracks) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_qpainter_builder.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement build_qpainter_tracks**

```python
# packages/geoviz_well_log/geoviz_well_log/qpainter_builder.py
from __future__ import annotations

from .models import WellLogData, CurveData
from .renderer import (
    DepthTrack, CurveTrack, IntervalTrack,
    LithologyTrack, FaciesTrack, SystemsTractTrack,
    BaseTrack,
)

_LOG_SCALE_CURVES = {"RT", "RXO"}


def build_qpainter_tracks(data: WellLogData) -> list[BaseTrack]:
    """Convert WellLogData into QPainter track objects for WellLogCanvas.

    Creates tracks only for non-empty data sections.
    Order: depth → curves → interval columns → lithology → facies → systems tract.
    """
    tracks: list[BaseTrack] = []

    # 1. Depth track (always)
    tracks.append(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))

    # 2. Curve tracks
    for curve in data.curves:
        is_log = curve.name.upper() in _LOG_SCALE_CURVES
        tracks.append(CurveTrack(
            curves=[curve],
            label=f"{curve.name} ({curve.unit})" if curve.unit else curve.name,
            width=150,
            log_scale=is_log,
        ))

    # 3. Interval tracks from WellIntervals
    if data.intervals is not None:
        iv = data.intervals
        for field_name, label in [
            ("system", "System"),
            ("series", "Series"),
            ("formation", "Formation"),
            ("member", "Member"),
            ("lithology_desc", "Description"),
            ("sequence", "Sequence"),
        ]:
            items = getattr(iv, field_name, None)
            if items:
                tracks.append(IntervalTrack(intervals=items, label=label, width=80))

    # 4. Lithology track
    if data.lithology:
        tracks.append(LithologyTrack(intervals=data.lithology, width=80))

    # 5. Facies track (from intervals.facies if present, else from data.facies)
    facies_data = None
    if data.intervals is not None and data.intervals.facies:
        fd = data.intervals.facies
        if fd.phase or fd.sub_phase or fd.micro_phase:
            facies_data = fd
    if facies_data is None and data.facies:
        from .models import FaciesData, IntervalItem
        phase = [IntervalItem(top=f.top, bottom=f.bottom, name=f.facies) for f in data.facies]
        facies_data = FaciesData(phase=phase)

    if facies_data is not None:
        tracks.append(FaciesTrack(facies_data=facies_data, label="Facies", width=80))

    # 6. Systems tract track
    if data.intervals is not None and data.intervals.systems_tract:
        tracks.append(SystemsTractTrack(intervals=data.intervals.systems_tract, width=60))

    return tracks
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_qpainter_builder.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Update package __init__.py**

Add to `packages/geoviz_well_log/geoviz_well_log/__init__.py`:

After the existing `from .payload_builder import (` block, add:
```python
from .qpainter_builder import build_qpainter_tracks
```

Add to `__all__`:
```python
    "build_qpainter_tracks",
```

- [ ] **Step 6: Run full test suite**

Run: `source .venv/bin/activate && pytest --tb=short`
Expected: All existing + new tests pass.

- [ ] **Step 7: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/qpainter_builder.py packages/geoviz_well_log/geoviz_well_log/__init__.py tests/test_qpainter_builder.py
git commit -m "feat(well-log): add build_qpainter_tracks data pipeline

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
