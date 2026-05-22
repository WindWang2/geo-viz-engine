# Well Log Renderer Plan 2 — Track Types + Interaction

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 geological track types (IntervalTrack, LithologyTrack, FaciesTrack, SystemsTractTrack) and mouse interaction (zoom/pan + crosshair) to the QPainter well log renderer.

**Architecture:** All new tracks extend `BaseTrack` and implement `paint_content(painter, rect)`. `PatternEngine` caches SVG pattern → QBrush conversions for LithologyTrack. `ZoomPanHandler` is an event filter on `WellLogCanvas`. `CrosshairOverlay` is a transparent overlay widget. Same `paint_content` code renders to screen, SVG, and PDF.

**Tech Stack:** PySide6 QPainter, QSvgRenderer, QBrush, QPolygonF, numpy, Pydantic

---

## File Structure

```
packages/geoviz_well_log/geoviz_well_log/renderer/
├── __init__.py           # MODIFY: add new exports
├── track_base.py         # (existing, unchanged)
├── depth_track.py        # (existing, unchanged)
├── curve_track.py        # (existing, unchanged)
├── canvas.py             # (existing, unchanged)
├── coordinator.py        # (existing, unchanged)
├── pattern_engine.py     # NEW: SVG → QBrush cache
├── interval_track.py     # NEW: Generic stratigraphy column
├── lithology_track.py    # NEW: Lithology with SVG pattern fills
├── facies_track.py       # NEW: Facies with color fills
├── systems_tract.py      # NEW: TST/HST triangles
├── interaction.py        # NEW: ZoomPanHandler
└── overlay.py            # NEW: CrosshairOverlay

tests/
├── test_pattern_engine.py
├── test_interval_track.py
├── test_lithology_track.py
├── test_facies_track.py
├── test_systems_tract.py
├── test_interaction.py
└── test_overlay.py
```

---

### Task 1: PatternEngine — SVG pattern → QBrush cache

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py`
- Test: `tests/test_pattern_engine.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_pattern_engine.py
import os
import pytest
from PySide6.QtGui import QBrush, QColor

from geoviz_well_log.renderer.pattern_engine import PatternEngine


def test_pattern_engine_resolves_known_lithology():
    """砂岩 should resolve to 'sandstone' pattern."""
    engine = PatternEngine()
    brush = engine.get_brush("砂岩")
    assert brush is not None
    assert isinstance(brush, QBrush)


def test_pattern_engine_unknown_returns_none():
    """Unknown lithology returns None brush."""
    engine = PatternEngine()
    brush = engine.get_brush("不存在的岩石")
    assert brush is None


def test_pattern_engine_fallback_color():
    """Fallback color for known FACIES_COLORS entry."""
    engine = PatternEngine()
    color = engine.get_color("砂岩")
    assert color is not None
    assert isinstance(color, QColor)
    assert color.name() == "#f0d9b5"


def test_pattern_engine_fallback_color_unknown():
    """Unknown name returns None color."""
    engine = PatternEngine()
    color = engine.get_color("不存在的岩石")
    assert color is None


def test_pattern_engine_caches_brushes():
    """Same lithology returns same brush object (cached)."""
    engine = PatternEngine()
    b1 = engine.get_brush("砂岩")
    b2 = engine.get_brush("砂岩")
    assert b1 is b2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_pattern_engine.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement PatternEngine**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QBrush, QColor, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QSize, Qt

from ..pattern_map import PATTERN_MAP, FACIES_COLORS


class PatternEngine:
    """Cache that converts SVG pattern files to tiled QBrush objects."""

    _ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "patterns"

    def __init__(self, tile_size: int = 20):
        self._tile_size = tile_size
        self._brush_cache: dict[str, QBrush] = {}

    def _load_svg(self, pattern_id: str) -> QBrush | None:
        """Load an SVG file and return a tiled QBrush."""
        filename = pattern_id.replace("-", "_")
        svg_path = self._ASSETS_DIR / f"{filename}.svg"
        if not svg_path.exists():
            return None

        renderer = QSvgRenderer(str(svg_path))
        if not renderer.isValid():
            return None

        size = QSize(self._tile_size, self._tile_size)
        pm = QPixmap(size)
        pm.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pm)
        renderer.render(painter)
        painter.end()
        return QBrush(pm)

    def get_brush(self, lithology_name: str) -> QBrush | None:
        """Return a tiled QBrush for the given lithology name.

        Returns None if the name has no PATTERN_MAP entry or the SVG file is missing.
        """
        if lithology_name in self._brush_cache:
            return self._brush_cache[lithology_name]

        pattern_id = PATTERN_MAP.get(lithology_name)
        if pattern_id is None:
            return None

        brush = self._load_svg(pattern_id)
        if brush is not None:
            self._brush_cache[lithology_name] = brush
        return brush

    def get_color(self, name: str) -> QColor | None:
        """Return fallback color from FACIES_COLORS for a given name."""
        hex_color = FACIES_COLORS.get(name)
        if hex_color is None:
            return None
        return QColor(hex_color)
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_pattern_engine.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/pattern_engine.py tests/test_pattern_engine.py
git commit -m "feat(well-log): add PatternEngine for SVG pattern → QBrush cache

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: IntervalTrack — generic stratigraphy column

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/interval_track.py`
- Test: `tests/test_interval_track.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_interval_track.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import IntervalItem
from geoviz_well_log.renderer.interval_track import IntervalTrack


def _make_intervals():
    return [
        IntervalItem(top=0, bottom=100, name="System A"),
        IntervalItem(top=100, bottom=200, name="System B"),
        IntervalItem(top=200, bottom=300, name="System C"),
    ]


def test_interval_track_creation():
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    assert track.label == "System"
    assert track.width == 80


def test_interval_track_paint_no_crash():
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_interval_track_export_render():
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 80, 832))
    painter.end()


def test_interval_track_custom_colors():
    colors = {"System A": "#ff0000", "System B": "#00ff00"}
    track = IntervalTrack(intervals=_make_intervals(), label="System", width=80,
                          colors=colors)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_interval_track_empty_intervals():
    track = IntervalTrack(intervals=[], label="Empty", width=80)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_interval_track.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement IntervalTrack**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/interval_track.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtWidgets import QWidget

from ..models import IntervalItem
from .track_base import BaseTrack

_PASTEL_PALETTE = [
    "#d4e6f1", "#d5f5e3", "#fdebd0", "#e8daef",
    "#fcf3cf", "#fadbd8", "#d1f2eb", "#ebdef0",
]


class IntervalTrack(BaseTrack):
    """Generic interval column for stratigraphy, descriptions, etc."""

    def __init__(self, intervals: list[IntervalItem], label: str = "",
                 width: int = 80, colors: dict[str, str] | None = None,
                 header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._intervals = intervals
        self._colors = colors or {}

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def _get_color(self, index: int, name: str) -> QColor:
        if name in self._colors:
            return QColor(self._colors[name])
        return QColor(_PASTEL_PALETTE[index % len(_PASTEL_PALETTE)])

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        for i, interval in enumerate(self._intervals):
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            # Skip intervals outside visible range
            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            # Clamp to rect
            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)
            color = self._get_color(i, interval.name)

            painter.fillRect(interval_rect, QBrush(color))

            # Border
            painter.setPen(QPen(QColor("#666666"), 0.5))
            painter.drawRect(interval_rect)

            # Label
            painter.setPen(QPen(QColor("#333333"), 1))
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            if interval_rect.height() > 14:
                if rect.width() < 50:
                    painter.save()
                    painter.translate(text_rect.center())
                    painter.rotate(-90)
                    rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                     text_rect.height(), text_rect.width())
                    painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, interval.name)
                    painter.restore()
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, interval.name)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_interval_track.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/interval_track.py tests/test_interval_track.py
git commit -m "feat(well-log): add IntervalTrack for stratigraphy columns

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: LithologyTrack — lithology with SVG pattern fills

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/lithology_track.py`
- Test: `tests/test_lithology_track.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_lithology_track.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import LithologyInterval
from geoviz_well_log.renderer.lithology_track import LithologyTrack


def _make_intervals():
    return [
        LithologyInterval(top=0, bottom=100, lithology="砂岩", description="中砂岩"),
        LithologyInterval(top=100, bottom=200, lithology="泥岩", description="深灰色泥岩"),
        LithologyInterval(top=200, bottom=300, lithology="灰岩", description="生物灰岩"),
    ]


def test_lithology_track_creation():
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    assert track.label == "Lithology"
    assert track.width == 80


def test_lithology_track_paint_no_crash():
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_lithology_track_export_render():
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 80, 832))
    painter.end()


def test_lithology_track_unknown_lithology_no_crash():
    """Unknown lithology name falls back to color fill — no crash."""
    intervals = [LithologyInterval(top=0, bottom=100, lithology="未知岩石")]
    track = LithologyTrack(intervals=intervals, width=80)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_lithology_track_empty_intervals():
    track = LithologyTrack(intervals=[], width=80)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_lithology_track_zoomed_view():
    """Only a subset of intervals visible — should not crash."""
    track = LithologyTrack(intervals=_make_intervals(), width=80)
    track.set_depth_range(50, 150)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_lithology_track.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement LithologyTrack**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/lithology_track.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtWidgets import QWidget

from ..models import LithologyInterval
from ..pattern_map import FACIES_COLORS
from .pattern_engine import PatternEngine
from .track_base import BaseTrack


class LithologyTrack(BaseTrack):
    """Lithology column with SVG pattern fills."""

    def __init__(self, intervals: list[LithologyInterval], label: str = "Lithology",
                 width: int = 80, show_description: bool = True,
                 header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._intervals = intervals
        self._show_description = show_description
        self._pattern_engine = PatternEngine()

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def _fallback_color(self, lithology: str) -> QColor:
        hex_color = FACIES_COLORS.get(lithology, "#e0e0e0")
        return QColor(hex_color)

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect)

        desc_font = QFont()
        desc_font.setPointSize(6)

        for interval in self._intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)

            # Try SVG pattern fill first, fallback to color
            brush = self._pattern_engine.get_brush(interval.lithology)
            if brush is not None:
                painter.fillRect(interval_rect, brush)
            else:
                painter.fillRect(interval_rect, QBrush(self._fallback_color(interval.lithology)))

            # Border
            painter.setPen(QPen(QColor("#666666"), 0.5))
            painter.drawRect(interval_rect)

            # Description text (vertical, along right edge)
            if self._show_description and interval.description and interval_rect.height() > 16:
                painter.setFont(desc_font)
                painter.setPen(QPen(QColor("#555555"), 1))
                painter.save()
                tx = interval_rect.right() - 4
                ty = interval_rect.center().y()
                painter.translate(tx, ty)
                painter.rotate(-90)
                text_w = interval_rect.height() - 4
                text_h = 10
                painter.drawText(QRectF(-text_w / 2, -text_h / 2, text_w, text_h),
                                 Qt.AlignmentFlag.AlignCenter, interval.description)
                painter.restore()

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_lithology_track.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/lithology_track.py tests/test_lithology_track.py
git commit -m "feat(well-log): add LithologyTrack with SVG pattern fills

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: FaciesTrack — facies column with color fills

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/facies_track.py`
- Test: `tests/test_facies_track.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_facies_track.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import IntervalItem, FaciesData
from geoviz_well_log.renderer.facies_track import FaciesTrack


def _make_facies_data():
    return FaciesData(
        phase=[
            IntervalItem(top=0, bottom=150, name="三角洲"),
            IntervalItem(top=150, bottom=300, name="陆棚"),
        ],
        sub_phase=[
            IntervalItem(top=0, bottom=80, name="前三角洲"),
            IntervalItem(top=80, bottom=150, name="三角洲前缘"),
            IntervalItem(top=150, bottom=300, name="碳酸盐台地"),
        ],
        micro_phase=[
            IntervalItem(top=0, bottom=40, name="砂泥质陆棚"),
            IntervalItem(top=40, bottom=80, name="混积浅水陆棚"),
            IntervalItem(top=80, bottom=120, name="河口坝"),
            IntervalItem(top=120, bottom=150, name="远砂坝"),
            IntervalItem(top=150, bottom=220, name="局限台地"),
            IntervalItem(top=220, bottom=300, name="开阔台地"),
        ],
    )


def test_facies_track_creation():
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=80)
    assert track.label == "Facies"


def test_facies_track_paint_single_column():
    """Default mode: single column showing most specific level."""
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=80)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_facies_track_paint_nested_columns():
    """Nested mode: three columns for phase/sub_phase/micro_phase."""
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=180,
                        nested=True)
    track.set_depth_range(0, 300)
    pm = QPixmap(180, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 180, 800))
    painter.end()


def test_facies_track_export_render():
    track = FaciesTrack(facies_data=_make_facies_data(), label="Facies", width=80)
    track.set_depth_range(0, 300)
    pm = QPixmap(80, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 80, 832))
    painter.end()


def test_facies_track_empty_data():
    data = FaciesData()
    track = FaciesTrack(facies_data=data, label="Facies", width=80)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()


def test_facies_track_partial_data():
    """Only phase data, no sub/micro."""
    data = FaciesData(
        phase=[IntervalItem(top=0, bottom=100, name="三角洲")],
    )
    track = FaciesTrack(facies_data=data, label="Facies", width=80)
    track.set_depth_range(0, 100)
    pm = QPixmap(80, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 80, 800))
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_facies_track.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement FaciesTrack**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/facies_track.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PySide6.QtWidgets import QWidget

from ..models import IntervalItem, FaciesData
from ..pattern_map import FACIES_COLORS
from .track_base import BaseTrack


class FaciesTrack(BaseTrack):
    """Facies column with color fills. Supports single and nested display."""

    def __init__(self, facies_data: FaciesData, label: str = "Facies",
                 width: int = 80, nested: bool = False,
                 header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._facies_data = facies_data
        self._nested = nested

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def _get_color(self, name: str) -> QColor:
        hex_color = FACIES_COLORS.get(name, "#e0e0e0")
        return QColor(hex_color)

    def _paint_column(self, painter: QPainter, rect: QRectF, intervals: list[IntervalItem]):
        painter.save()
        painter.setClipRect(rect)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        for interval in intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)
            color = self._get_color(interval.name)

            painter.fillRect(interval_rect, QBrush(color))

            painter.setPen(QPen(QColor("#666666"), 0.5))
            painter.drawRect(interval_rect)

            painter.setPen(QPen(QColor("#333333"), 1))
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            if interval_rect.height() > 14:
                if rect.width() < 50:
                    painter.save()
                    painter.translate(text_rect.center())
                    painter.rotate(-90)
                    rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                     text_rect.height(), text_rect.width())
                    painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, interval.name)
                    painter.restore()
                else:
                    painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, interval.name)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()

    def paint_content(self, painter: QPainter, rect: QRectF):
        if self._nested:
            # Three columns: phase | sub_phase | micro_phase
            col_width = rect.width() / 3
            phase_rect = QRectF(rect.left(), rect.top(), col_width, rect.height())
            sub_rect = QRectF(rect.left() + col_width, rect.top(), col_width, rect.height())
            micro_rect = QRectF(rect.left() + 2 * col_width, rect.top(), col_width, rect.height())

            if self._facies_data.phase:
                self._paint_column(painter, phase_rect, self._facies_data.phase)
            if self._facies_data.sub_phase:
                self._paint_column(painter, sub_rect, self._facies_data.sub_phase)
            if self._facies_data.micro_phase:
                self._paint_column(painter, micro_rect, self._facies_data.micro_phase)
        else:
            # Single column: most specific level available
            if self._facies_data.micro_phase:
                self._paint_column(painter, rect, self._facies_data.micro_phase)
            elif self._facies_data.sub_phase:
                self._paint_column(painter, rect, self._facies_data.sub_phase)
            elif self._facies_data.phase:
                self._paint_column(painter, rect, self._facies_data.phase)
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_facies_track.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/facies_track.py tests/test_facies_track.py
git commit -m "feat(well-log): add FaciesTrack with color fills and nested mode

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: SystemsTractTrack — TST/HST triangles

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/systems_tract.py`
- Test: `tests/test_systems_tract.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_systems_tract.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import IntervalItem
from geoviz_well_log.renderer.systems_tract import SystemsTractTrack


def _make_tracts():
    return [
        IntervalItem(top=0, bottom=100, name="LST"),
        IntervalItem(top=100, bottom=200, name="TST"),
        IntervalItem(top=200, bottom=300, name="HST"),
    ]


def test_systems_tract_creation():
    track = SystemsTractTrack(intervals=_make_tracts(), width=60)
    assert track.label == "Systems Tract"


def test_systems_tract_paint_no_crash():
    track = SystemsTractTrack(intervals=_make_tracts(), width=60)
    track.set_depth_range(0, 300)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_systems_tract_export_render():
    track = SystemsTractTrack(intervals=_make_tracts(), width=60)
    track.set_depth_range(0, 300)
    pm = QPixmap(60, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 60, 832))
    painter.end()


def test_systems_tract_unknown_name():
    """Unknown tract name renders as gray rectangle."""
    intervals = [IntervalItem(top=0, bottom=100, name="UNKNOWN")]
    track = SystemsTractTrack(intervals=intervals, width=60)
    track.set_depth_range(0, 100)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_systems_tract_chinese_names():
    """Chinese tract names should also work."""
    intervals = [
        IntervalItem(top=0, bottom=100, name="海侵体系域"),
        IntervalItem(top=100, bottom=200, name="高位体系域"),
        IntervalItem(top=200, bottom=300, name="低位体系域"),
    ]
    track = SystemsTractTrack(intervals=intervals, width=60)
    track.set_depth_range(0, 300)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()


def test_systems_tract_empty():
    track = SystemsTractTrack(intervals=[], width=60)
    track.set_depth_range(0, 100)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_systems_tract.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement SystemsTractTrack**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/systems_tract.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QPointF
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QPolygonF, QBrush
from PySide6.QtWidgets import QWidget

from ..models import IntervalItem
from .track_base import BaseTrack

_TRACT_COLORS = {
    "TST": "#4472C4",
    "HST": "#ED7D31",
    "LST": "#70AD47",
    "海侵体系域": "#4472C4",
    "高位体系域": "#ED7D31",
    "低位体系域": "#70AD47",
}

_TRACT_SHAPES = {
    "TST": "triangle_up",
    "海侵体系域": "triangle_up",
    "HST": "triangle_down",
    "高位体系域": "triangle_down",
    "LST": "rectangle",
    "低位体系域": "rectangle",
}


class SystemsTractTrack(BaseTrack):
    """Systems tract column with geometric shape fills (TST/HST/LST)."""

    def __init__(self, intervals: list[IntervalItem], label: str = "Systems Tract",
                 width: int = 60, header_height: int = 32, parent=None):
        super().__init__(label=label, width=width, header_height=header_height,
                         parent=parent)
        self._intervals = intervals

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setClipRect(rect)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        for interval in self._intervals:
            y_top = self._depth_to_y(interval.top, rect)
            y_bottom = self._depth_to_y(interval.bottom, rect)

            if y_bottom < rect.top() or y_top > rect.bottom():
                continue

            y_top = max(y_top, rect.top())
            y_bottom = min(y_bottom, rect.bottom())

            interval_rect = QRectF(rect.left(), y_top, rect.width(), y_bottom - y_top)
            color = QColor(_TRACT_COLORS.get(interval.name, "#b0b0b0"))
            shape = _TRACT_SHAPES.get(interval.name, "rectangle")

            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor("#666666"), 0.5))

            if shape == "triangle_up":
                polygon = QPolygonF([
                    interval_rect.bottomLeft(),
                    interval_rect.bottomRight(),
                    QPointF(interval_rect.center().x(), interval_rect.top()),
                ])
                painter.drawPolygon(polygon)
            elif shape == "triangle_down":
                polygon = QPolygonF([
                    interval_rect.topLeft(),
                    interval_rect.topRight(),
                    QPointF(interval_rect.center().x(), interval_rect.bottom()),
                ])
                painter.drawPolygon(polygon)
            else:
                painter.drawRect(interval_rect)

            # Label
            painter.setPen(QPen(QColor("#333333"), 1))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            text_rect = QRectF(interval_rect.left() + 2, interval_rect.top() + 1,
                               interval_rect.width() - 4, interval_rect.height() - 2)
            if interval_rect.height() > 14:
                painter.save()
                painter.translate(text_rect.center())
                painter.rotate(-90)
                rotated = QRectF(-text_rect.height() / 2, -text_rect.width() / 2,
                                 text_rect.height(), text_rect.width())
                painter.drawText(rotated, Qt.AlignmentFlag.AlignCenter, interval.name)
                painter.restore()

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)
        painter.restore()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_systems_tract.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/systems_tract.py tests/test_systems_tract.py
git commit -m "feat(well-log): add SystemsTractTrack with TST/HST/LST shapes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: ZoomPanHandler — mouse wheel zoom + drag pan

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/interaction.py`
- Test: `tests/test_interaction.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_interaction.py
import pytest
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QWidget

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interaction import ZoomPanHandler


def _make_canvas():
    canvas = WellLogCanvas()
    canvas.resize(210, 500)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=1000))
    canvas.set_depth_range(0, 1000)
    return canvas


def test_handler_install():
    canvas = _make_canvas()
    handler = ZoomPanHandler(canvas)
    assert handler is not None


def test_wheel_zoom_in():
    canvas = _make_canvas()
    handler = ZoomPanHandler(canvas)
    # Simulate wheel event (positive delta = zoom in)
    from PySide6.QtCore import QPointF
    event = QWheelEvent(
        QPointF(100, 250), QPointF(100, 250), QPoint(0, 120), QPoint(0, 120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollBegin, False, Qt.Orientation.Vertical,
    )
    result = canvas.event(event)
    # After zoom, range should be smaller
    dt = canvas.tracks[0]
    assert dt.depth_span < 1000.0


def test_wheel_zoom_out():
    canvas = _make_canvas()
    handler = ZoomPanHandler(canvas)
    # First zoom in
    canvas.set_depth_range(400, 600)
    from PySide6.QtCore import QPointF
    event = QWheelEvent(
        QPointF(100, 250), QPointF(100, 250), QPoint(0, -120), QPoint(0, -120),
        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollBegin, False, Qt.Orientation.Vertical,
    )
    canvas.event(event)
    dt = canvas.tracks[0]
    assert dt.depth_span > 200.0


def test_double_click_reset():
    canvas = _make_canvas()
    handler = ZoomPanHandler(canvas)
    canvas.set_depth_range(400, 600)
    assert canvas.tracks[0].depth_span == pytest.approx(200.0)
    # Simulate double-click
    from PySide6.QtCore import QPointF
    event = QMouseEvent(QEvent.Type.MouseButtonDblClick, QPointF(100, 250),
                        QPointF(100, 250), Qt.MouseButton.LeftButton,
                        Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    canvas.event(event)
    assert canvas.tracks[0].depth_span == pytest.approx(1000.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_interaction.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement ZoomPanHandler**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/interaction.py
from __future__ import annotations

from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QWheelEvent, QMouseEvent
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canvas import WellLogCanvas


class ZoomPanHandler:
    """Event filter for zoom (wheel) and pan (middle-drag / Ctrl+left-drag) on WellLogCanvas.

    Install via: handler = ZoomPanHandler(canvas)
    """

    _ZOOM_FACTOR = 0.2

    def __init__(self, canvas: WellLogCanvas):
        self._canvas = canvas
        self._full_top = 0.0
        self._full_bottom = 100.0
        self._dragging = False
        self._last_y = 0.0
        canvas.installEventFilter(self)

    def set_full_range(self, top: float, bottom: float):
        """Set the data bounds for clamping zoom/pan."""
        self._full_top = top
        self._full_bottom = bottom

    def eventFilter(self, obj: QWidget, event: QEvent) -> bool:
        if obj is not self._canvas:
            return False

        if event.type() == QEvent.Type.Wheel:
            return self._handle_wheel(event)
        elif event.type() == QEvent.Type.MouseButtonDblClick:
            return self._handle_double_click(event)
        elif event.type() == QEvent.Type.MouseButtonPress:
            return self._handle_press(event)
        elif event.type() == QEvent.Type.MouseMove:
            return self._handle_move(event)
        elif event.type() == QEvent.Type.MouseButtonRelease:
            return self._handle_release(event)

        return False

    def _handle_wheel(self, event: QWheelEvent) -> bool:
        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None:
            return False

        top = track.depth_top
        bottom = track.depth_bottom
        span = bottom - top
        if span <= 0:
            return False

        # Zoom centered on cursor y position
        y_ratio = event.position().y() / self._canvas.height()
        cursor_depth = top + y_ratio * span

        delta = event.angleDelta().y()
        if delta > 0:
            factor = self._ZOOM_FACTOR
        else:
            factor = -self._ZOOM_FACTOR

        new_span = span * (1 - factor)
        new_top = cursor_depth - y_ratio * new_span
        new_bottom = new_top + new_span

        # Clamp to full range
        new_top = max(new_top, self._full_top)
        new_bottom = min(new_bottom, self._full_bottom)
        if new_bottom - new_top < 1.0:
            new_bottom = new_top + 1.0

        self._canvas.set_depth_range(new_top, new_bottom)
        return True

    def _handle_double_click(self, event: QMouseEvent) -> bool:
        if event.button() == Qt.MouseButton.LeftButton:
            self._canvas.set_depth_range(self._full_top, self._full_bottom)
            return True
        return False

    def _handle_press(self, event: QMouseEvent) -> bool:
        is_pan = (event.button() == Qt.MouseButton.MiddleButton or
                  (event.button() == Qt.MouseButton.LeftButton and
                   event.modifiers() & Qt.KeyboardModifier.ControlModifier))
        if is_pan:
            self._dragging = True
            self._last_y = event.position().y()
            return True
        return False

    def _handle_move(self, event: QMouseEvent) -> bool:
        if not self._dragging:
            return False

        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None:
            return False

        dy = event.position().y() - self._last_y
        self._last_y = event.position().y()

        span = track.depth_span
        depth_per_pixel = span / self._canvas.height() if self._canvas.height() > 0 else 0
        delta = -dy * depth_per_pixel

        new_top = track.depth_top + delta
        new_bottom = track.depth_bottom + delta

        # Clamp to full range
        if new_top < self._full_top:
            new_bottom += self._full_top - new_top
            new_top = self._full_top
        if new_bottom > self._full_bottom:
            new_top -= new_bottom - self._full_bottom
            new_bottom = self._full_bottom

        if new_bottom - new_top >= 1.0:
            self._canvas.set_depth_range(new_top, new_bottom)
        return True

    def _handle_release(self, event: QMouseEvent) -> bool:
        if self._dragging:
            self._dragging = False
            return True
        return False
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_interaction.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/interaction.py tests/test_interaction.py
git commit -m "feat(well-log): add ZoomPanHandler for mouse wheel zoom and drag pan

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: CrosshairOverlay — depth cursor + tooltip

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py`
- Test: `tests/test_overlay.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_overlay.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF, Qt

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.overlay import CrosshairOverlay


def _make_canvas():
    canvas = WellLogCanvas()
    canvas.resize(210, 500)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=1000))
    canvas.set_depth_range(0, 1000)
    return canvas


def test_overlay_creation():
    canvas = _make_canvas()
    overlay = CrosshairOverlay(canvas)
    assert overlay is not None


def test_overlay_depth_at_y():
    canvas = _make_canvas()
    overlay = CrosshairOverlay(canvas)
    depth = overlay.depth_at_y(250)
    assert depth == pytest.approx(500.0)


def test_overlay_depth_at_y_clamped():
    canvas = _make_canvas()
    overlay = CrosshairOverlay(canvas)
    depth = overlay.depth_at_y(-10)
    assert depth == pytest.approx(0.0)
    depth = overlay.depth_at_y(600)
    assert depth == pytest.approx(1000.0)


def test_overlay_paint_no_crash():
    canvas = _make_canvas()
    overlay = CrosshairOverlay(canvas)
    overlay.set_cursor_y(250)
    pm = QPixmap(210, 500)
    painter = QPainter(pm)
    overlay.paint_overlay(painter, QRectF(0, 0, 210, 500))
    painter.end()


def test_overlay_paint_hidden():
    """When cursor_y is None, paint does nothing."""
    canvas = _make_canvas()
    overlay = CrosshairOverlay(canvas)
    pm = QPixmap(210, 500)
    painter = QPainter(pm)
    overlay.paint_overlay(painter, QRectF(0, 0, 210, 500))
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_overlay.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement CrosshairOverlay**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QColor, QFont
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .canvas import WellLogCanvas


class CrosshairOverlay:
    """Crosshair depth cursor overlay for WellLogCanvas.

    Draws a horizontal dashed line at cursor y-position with a depth tooltip.
    Not a QWidget — renders via paint_overlay() called from canvas paintEvent.
    """

    def __init__(self, canvas: WellLogCanvas):
        self._canvas = canvas
        self._cursor_y: float | None = None

    def set_cursor_y(self, y: float | None):
        """Set cursor y-position (pixels) or None to hide."""
        self._cursor_y = y

    def depth_at_y(self, y: float) -> float:
        """Convert pixel y-coordinate to depth value."""
        track = self._canvas.tracks[0] if self._canvas.tracks else None
        if track is None or self._canvas.height() <= 0:
            return 0.0
        ratio = y / self._canvas.height()
        depth = track.depth_top + ratio * track.depth_span
        return max(track.depth_top, min(depth, track.depth_bottom))

    def paint_overlay(self, painter: QPainter, rect: QRectF):
        """Draw crosshair line and depth tooltip."""
        if self._cursor_y is None:
            return
        if self._cursor_y < rect.top() or self._cursor_y > rect.bottom():
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        # Dashed horizontal line
        pen = QPen(QColor("#ef4444"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(int(rect.left()), int(self._cursor_y),
                         int(rect.right()), int(self._cursor_y))

        # Depth tooltip
        depth = self.depth_at_y(self._cursor_y)
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        label = f"{depth:.1f} m"
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(font)
        text_width = fm.horizontalAdvance(label) + 8
        text_height = fm.height() + 4

        # Position tooltip at top-right, offset from cursor
        tooltip_x = rect.right() - text_width - 4
        tooltip_y = self._cursor_y - text_height - 2
        if tooltip_y < rect.top():
            tooltip_y = self._cursor_y + 4

        tooltip_rect = QRectF(tooltip_x, tooltip_y, text_width, text_height)
        painter.fillRect(tooltip_rect, QColor("#fef2f2"))
        painter.setPen(QPen(QColor("#ef4444"), 0.5))
        painter.drawRect(tooltip_rect)
        painter.setPen(QColor("#dc2626"))
        painter.drawText(tooltip_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.restore()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_overlay.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py tests/test_overlay.py
git commit -m "feat(well-log): add CrosshairOverlay with depth tooltip

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: Update renderer __init__.py + package __init__.py, run full suite

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/__init__.py`

- [ ] **Step 1: Update renderer/__init__.py**

Replace the entire file with:

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py
from .track_base import BaseTrack
from .depth_track import DepthTrack
from .curve_track import CurveTrack
from .interval_track import IntervalTrack
from .lithology_track import LithologyTrack
from .facies_track import FaciesTrack
from .systems_tract import SystemsTractTrack
from .canvas import WellLogCanvas
from .coordinator import LayoutCoordinator
from .pattern_engine import PatternEngine
from .interaction import ZoomPanHandler
from .overlay import CrosshairOverlay

__all__ = [
    "BaseTrack", "DepthTrack", "CurveTrack",
    "IntervalTrack", "LithologyTrack", "FaciesTrack", "SystemsTractTrack",
    "WellLogCanvas", "LayoutCoordinator", "PatternEngine",
    "ZoomPanHandler", "CrosshairOverlay",
]
```

- [ ] **Step 2: Update package __init__.py**

Add these lines to `packages/geoviz_well_log/geoviz_well_log/__init__.py` after the existing `# New QPainter renderer` imports:

```python
from .renderer import (
    IntervalTrack, LithologyTrack, FaciesTrack, SystemsTractTrack,
    PatternEngine, ZoomPanHandler, CrosshairOverlay,
)
```

Add to `__all__`:
```python
    "IntervalTrack", "LithologyTrack", "FaciesTrack", "SystemsTractTrack",
    "PatternEngine", "ZoomPanHandler", "CrosshairOverlay",
```

The full `__init__.py` should look like:

```python
from .chart_engine import ChartEngine
from .models import (
    WellLogData, CurveData, LithologyInterval, FaciesInterval,
    IntervalItem, WellIntervals, FaciesData, LineStyle
)
from .config import (
    ChartConfig, TrackConfig, TrackType, PatternMapping,
    CurveTrackConfig, IntervalTrackConfig, SystemsTractTrackConfig, TextTrackConfig
)
from .sync_manager import SyncManager
from .connection_overlay import ConnectionOverlay
from .location_map import LocationMapWidget
from .utils import build_default_payload
from .payload_builder import (
    build_tracks_from_data,
    build_curve_track,
    build_interval_track,
    build_depth_track,
    build_lithology_track,
    build_merged_curve_track,
    build_systems_tract_track,
    build_ai_prediction_tracks,
    build_legacy_display_items,
    LEGACY_DEFAULT_ACTIVE,
)
from .track_manager import TrackManager
from .pattern_map import PATTERN_MAP

# New QPainter renderer
from .renderer import (
    BaseTrack, DepthTrack, CurveTrack, WellLogCanvas, LayoutCoordinator,
    IntervalTrack, LithologyTrack, FaciesTrack, SystemsTractTrack,
    PatternEngine, ZoomPanHandler, CrosshairOverlay,
)
from .export_qpainter import export_svg as qpainter_export_svg
from .export_qpainter import export_pdf as qpainter_export_pdf
from .export_qpainter import export_png as qpainter_export_png

__version__ = "0.1.0"

__all__ = [
    "ChartEngine",
    "WellLogData",
    "CurveData",
    "LithologyInterval",
    "FaciesInterval",
    "IntervalItem",
    "WellIntervals",
    "FaciesData",
    "LineStyle",
    "ChartConfig",
    "TrackConfig",
    "TrackType",
    "PatternMapping",
    "CurveTrackConfig",
    "IntervalTrackConfig",
    "SystemsTractTrackConfig",
    "TextTrackConfig",
    "SyncManager",
    "ConnectionOverlay",
    "LocationMapWidget",
    "build_default_payload",
    "build_tracks_from_data",
    "build_curve_track",
    "build_interval_track",
    "build_depth_track",
    "build_lithology_track",
    "build_merged_curve_track",
    "build_systems_tract_track",
    "build_ai_prediction_tracks",
    "build_legacy_display_items",
    "LEGACY_DEFAULT_ACTIVE",
    "TrackManager",
    "PATTERN_MAP",
    # QPainter renderer
    "BaseTrack", "DepthTrack", "CurveTrack", "WellLogCanvas", "LayoutCoordinator",
    "IntervalTrack", "LithologyTrack", "FaciesTrack", "SystemsTractTrack",
    "PatternEngine", "ZoomPanHandler", "CrosshairOverlay",
    "qpainter_export_svg", "qpainter_export_pdf", "qpainter_export_png",
]
```

- [ ] **Step 3: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All existing tests + new tests pass.

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py packages/geoviz_well_log/geoviz_well_log/__init__.py
git commit -m "feat(well-log): export Plan 2 track types and interaction classes

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
