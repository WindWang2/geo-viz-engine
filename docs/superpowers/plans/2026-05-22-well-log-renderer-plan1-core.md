# Well Log Renderer Rewrite — Plan 1: Core Infrastructure + Depth + Curve + Export

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working pure-QPainter well log renderer that displays depth rulers and log curves with guaranteed display=export vector consistency.

**Architecture:** All tracks implement `paint_content(painter, rect)` where `painter` can point to screen/QSvgGenerator/QPrinter. WellLogCanvas manages track layout and depth range. Viewport culling + min-max downsampling for large datasets.

**Tech Stack:** PySide6 QPainter, QPainterPath, QSvgGenerator, QPrinter, numpy, bisect, Pydantic

---

## File Structure

```
packages/geoviz_well_log/geoviz_well_log/
├── renderer/
│   ├── __init__.py           # re-exports all public classes
│   ├── track_base.py         # BaseTrack abstract base
│   ├── depth_track.py        # DepthTrack
│   ├── curve_track.py        # CurveTrack with downsampling
│   ├── canvas.py             # WellLogCanvas main widget
│   ├── coordinator.py        # LayoutCoordinator depth sync
│   └── overlay.py            # Crosshair + tooltip overlay
├── models.py                 # Extended with mudlog models
├── export_qpainter.py        # New QPainter-based export
└── ...existing files unchanged...
```

Tests:
```
tests/
├── test_renderer_base.py
├── test_depth_track.py
├── test_curve_track.py
├── test_canvas.py
├── test_renderer_export.py
└── test_renderer_integration.py
```

---

### Task 1: BaseTrack abstract base class

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py`
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py`
- Test: `tests/test_renderer_base.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_renderer_base.py
import pytest
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPixmap


def test_base_track_is_abstract():
    """BaseTrack cannot be instantiated directly."""
    from geoviz_well_log.renderer.track_base import BaseTrack
    with pytest.raises(TypeError):
        BaseTrack(label="Test", width=100)


def test_concrete_track_paint_content_called():
    """A concrete subclass can be created and paint_content is callable."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class ConcreteTrack(BaseTrack):
        def __init__(self):
            super().__init__(label="GR", width=100)
            self.painted = False

        def paint_content(self, painter, rect):
            self.painted = True

    track = ConcreteTrack()
    assert track.label == "GR"
    assert track.width == 100
    assert track.header_height == 32

    # Simulate paint
    pm = QPixmap(100, 200)
    painter = QPainter(pm)
    track.paint_content(painter, pm.rect().toRectF())
    painter.end()
    assert track.painted is True


def test_base_track_depth_range():
    """set_depth_range updates stored range."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class ConcreteTrack(BaseTrack):
        def __init__(self):
            super().__init__(label="D", width=60)
        def paint_content(self, painter, rect):
            pass

    track = ConcreteTrack()
    track.set_depth_range(100.0, 200.0)
    assert track.depth_top == 100.0
    assert track.depth_bottom == 200.0


def test_base_track_depth_span():
    """depth_span returns bottom - top."""
    from geoviz_well_log.renderer.track_base import BaseTrack

    class ConcreteTrack(BaseTrack):
        def __init__(self):
            super().__init__(label="D", width=60)
        def paint_content(self, painter, rect):
            pass

    track = ConcreteTrack()
    track.set_depth_range(50.0, 150.0)
    assert track.depth_span == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_renderer_base.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Create renderer package and BaseTrack**

`packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py`:
```python
from .track_base import BaseTrack
from .depth_track import DepthTrack
from .curve_track import CurveTrack
from .canvas import WellLogCanvas
from .coordinator import LayoutCoordinator
from .overlay import OverlayManager

__all__ = [
    "BaseTrack", "DepthTrack", "CurveTrack",
    "WellLogCanvas", "LayoutCoordinator", "OverlayManager",
]
```

`packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py`:
```python
from __future__ import annotations

from PySide6.QtCore import QRectF, Signal
from PySide6.QtGui import QPainter, QFont
from PySide6.QtWidgets import QWidget


class BaseTrack(QWidget):
    """Abstract base for all well log tracks.

    Every track implements paint_content(painter, rect) which is called
    with the same QPainter for both display and vector export.
    """

    depth_range_changed = Signal(float, float)

    def __init__(self, label: str = "", width: int = 100, header_height: int = 32, parent=None):
        super().__init__(parent)
        self._label = label
        self._width = width
        self._header_height = header_height
        self._depth_top = 0.0
        self._depth_bottom = 100.0
        self.setMinimumWidth(width)
        self.setMaximumWidth(width)

    @property
    def label(self) -> str:
        return self._label

    @property
    def width(self) -> int:
        return self._width

    @property
    def header_height(self) -> int:
        return self._header_height

    @property
    def depth_top(self) -> float:
        return self._depth_top

    @property
    def depth_bottom(self) -> float:
        return self._depth_bottom

    @property
    def depth_span(self) -> float:
        return self._depth_bottom - self._depth_top

    def set_depth_range(self, top: float, bottom: float):
        self._depth_top = top
        self._depth_bottom = bottom
        self.update()

    def paint_content(self, painter: QPainter, rect: QRectF):
        """Render track content. Must be implemented by subclasses."""
        raise NotImplementedError

    def paint_header(self, painter: QPainter, rect: QRectF):
        """Render track header (label)."""
        painter.save()
        painter.setPen(Qt.GlobalColor.black)
        font = QFont()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self._label)
        painter.restore()

    def export_render(self, painter: QPainter, full_rect: QRectF):
        """Export: header + content together."""
        header_rect = QRectF(full_rect.topLeft(), QSizeF(full_rect.width(), self._header_height))
        content_rect = QRectF(
            full_rect.left(), full_rect.top() + self._header_height,
            full_rect.width(), full_rect.height() - self._header_height,
        )
        painter.save()
        # Header background
        painter.fillRect(header_rect, QColor("#f0f0f0"))
        painter.drawRect(header_rect)
        self.paint_header(painter, header_rect)
        # Content
        self.paint_content(painter, content_rect)
        painter.drawRect(content_rect)
        painter.restore()


from PySide6.QtCore import Qt, QSizeF
from PySide6.QtGui import QColor
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_renderer_base.py -v`
Expected: PASS (3-4 tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/ tests/test_renderer_base.py
git commit -m "feat(well-log): add BaseTrack abstract base for QPainter renderer

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: DepthTrack — depth ruler with adaptive ticks

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py`
- Test: `tests/test_depth_track.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_depth_track.py
import pytest
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF


def test_depth_track_creation():
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=1000.0)
    assert track.label == "Depth"
    assert track.depth_top == 0.0
    assert track.depth_bottom == 1000.0


def test_depth_track_set_range():
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=1000.0)
    track.set_depth_range(100.0, 300.0)
    assert track.depth_top == 100.0
    assert track.depth_bottom == 300.0


def test_depth_track_paint_does_not_crash():
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=500.0)
    pm = QPixmap(60, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 60, 800))
    painter.end()
    # No crash = success


def test_depth_track_export_render():
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=500.0)
    pm = QPixmap(60, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 60, 832))
    painter.end()
    # No crash = success


def test_depth_track_tick_interval_adaptive():
    """Tick interval adapts to visible depth range."""
    from geoviz_well_log.renderer.depth_track import DepthTrack
    track = DepthTrack(top_depth=0.0, bottom_depth=10000.0)

    # Large range → larger tick interval
    track.set_depth_range(0, 10000)
    assert track.tick_interval >= 50

    # Small range → smaller tick interval
    track.set_depth_range(2500, 2520)
    assert track.tick_interval <= 10
```

- [ ] **Step 2: Run test**

Run: `source .venv/bin/activate && pytest tests/test_depth_track.py -v`
Expected: FAIL

- [ ] **Step 3: Implement DepthTrack**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QFont, QColor
from PySide6.QtWidgets import QWidget

from .track_base import BaseTrack


class DepthTrack(BaseTrack):
    """Depth ruler track with adaptive tick spacing."""

    def __init__(self, top_depth: float = 0.0, bottom_depth: float = 100.0,
                 width: int = 60, header_height: int = 32, parent=None):
        super().__init__(label="Depth (m)", width=width, header_height=header_height, parent=parent)
        self._tick_interval = 10.0

    @property
    def tick_interval(self) -> float:
        return self._tick_interval

    def _compute_tick_interval(self, rect_height: float) -> float:
        span = self.depth_span
        if span <= 0:
            return 10.0
        candidates = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000, 5000]
        for c in candidates:
            num_ticks = span / c
            pixels_per_tick = rect_height / num_ticks
            if pixels_per_tick >= 20:
                return float(c)
        return float(candidates[-1])

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.setClipRect(rect)

        self._tick_interval = self._compute_tick_interval(rect.height())

        pen = QPen(QColor("#333333"), 1)
        painter.setPen(pen)

        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)

        span = self.depth_span
        start = int(self.depth_top / self._tick_interval) * self._tick_interval
        depth = float(start)
        while depth <= self.depth_bottom:
            y = self._depth_to_y(depth, rect)
            if rect.top() <= y <= rect.bottom():
                painter.drawLine(int(rect.right()) - 10, int(y), int(rect.right()), int(y))
                text_rect = QRectF(rect.left(), y - 8, rect.width() - 12, 16)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                                 f"{depth:.0f}")
            depth += self._tick_interval

        # Border
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.drawLine(int(rect.right()), int(rect.top()), int(rect.right()), int(rect.bottom()))
        painter.restore()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_depth_track.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/depth_track.py tests/test_depth_track.py
git commit -m "feat(well-log): add DepthTrack with adaptive tick spacing

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 3: CurveTrack — log curves with viewport culling + downsampling

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py`
- Test: `tests/test_curve_track.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_curve_track.py
import pytest
import numpy as np
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.models import CurveData, LineStyle


def _make_curve(name="GR", n=100, lo=0, hi=1000):
    depths = np.linspace(lo, hi, n).tolist()
    values = np.random.uniform(10, 150, n).tolist()
    return CurveData(name=name, unit="API", depth=depths, values=values,
                     display_range=(0, 150), color="#00ff00", line_style=LineStyle.SOLID)


def test_curve_track_creation():
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve()
    track = CurveTrack(curves=[curve], label="GR", width=150)
    assert track.label == "GR"


def test_curve_track_paint_no_crash():
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=500)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    track.set_depth_range(0, 1000)
    pm = QPixmap(150, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 150, 800))
    painter.end()


def test_curve_track_viewport_culling():
    """Only points within visible range are rendered."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=1000)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    track.set_depth_range(400, 600)
    visible = track._visible_data(curve)
    # All visible depths should be within [400, 600] (with small margin)
    for d in visible[0]:
        assert 395 <= d <= 605


def test_curve_track_downsampling():
    """Large dataset gets downsampled but preserves peaks."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    depths = list(range(10000))
    values = [50.0] * 10000
    values[5000] = 999.0  # spike
    curve = CurveData(name="GR", depth=depths, values=values, display_range=(0, 1000))
    track = CurveTrack(curves=[curve], label="GR", width=150)
    track.set_depth_range(0, 10000)
    downsampled = track._downsample(depths, values, 800)
    # Spike should be preserved
    assert 999.0 in downsampled[1]
    # Downsampled should be fewer points than original
    assert len(downsampled[0]) < 10000


def test_curve_track_log_scale():
    """Log scale curve renders without crash."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = CurveData(name="RT", unit="ohm.m", depth=list(range(100)),
                      values=[10 ** (i / 20) for i in range(100)],
                      display_range=(0.1, 1000), color="red")
    track = CurveTrack(curves=[curve], label="RT", width=150, log_scale=True)
    track.set_depth_range(0, 100)
    pm = QPixmap(150, 800)
    painter = QPainter(pm)
    track.paint_content(painter, QRectF(0, 0, 150, 800))
    painter.end()


def test_curve_track_export_render():
    from geoviz_well_log.renderer.curve_track import CurveTrack
    curve = _make_curve(n=200)
    track = CurveTrack(curves=[curve], label="GR", width=150)
    track.set_depth_range(0, 1000)
    pm = QPixmap(150, 832)
    painter = QPainter(pm)
    track.export_render(painter, QRectF(0, 0, 150, 832))
    painter.end()
```

- [ ] **Step 2: Run test**

Run: `source .venv/bin/activate && pytest tests/test_curve_track.py -v`
Expected: FAIL

- [ ] **Step 3: Implement CurveTrack**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py
from __future__ import annotations

import bisect
from math import log10

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QPen, QPainterPath, QColor, QFont
from PySide6.QtWidgets import QWidget

from ..models import CurveData, LineStyle
from .track_base import BaseTrack


class CurveTrack(BaseTrack):
    """Log curve track with viewport culling and adaptive downsampling."""

    def __init__(self, curves: list[CurveData], label: str = "",
                 width: int = 150, log_scale: bool = False,
                 header_height: int = 32, parent=None):
        super().__init__(label=label or (curves[0].name if curves else ""),
                         width=width, header_height=header_height, parent=parent)
        self._curves = curves
        self._log_scale = log_scale
        # Pre-sort depths for binary search
        for c in self._curves:
            if c.depth != sorted(c.depth):
                pairs = sorted(zip(c.depth, c.values))
                c.depth = [p[0] for p in pairs]
                c.values = [p[1] for p in pairs]

    def _depth_to_y(self, depth: float, rect: QRectF) -> float:
        if self.depth_span <= 0:
            return rect.top()
        return rect.top() + (depth - self.depth_top) / self.depth_span * rect.height()

    def _value_to_x(self, value: float, display_range: tuple[float, float],
                    rect: QRectF) -> float:
        lo, hi = display_range
        if self._log_scale:
            if value <= 0:
                value = lo
            lo = max(lo, 1e-10)
            hi = max(hi, 1e-10)
            t = (log10(value) - log10(lo)) / (log10(hi) - log10(lo))
        else:
            t = (value - lo) / (hi - lo) if hi != lo else 0.5
        return rect.left() + t * rect.width()

    def _visible_data(self, curve: CurveData) -> tuple[list[float], list[float]]:
        margin = (self.depth_bottom - self.depth_top) * 0.01
        top = self.depth_top - margin
        bottom = self.depth_bottom + margin
        start = bisect.bisect_left(curve.depth, top)
        end = bisect.bisect_right(curve.depth, bottom)
        return curve.depth[start:end], curve.values[start:end]

    def _downsample(self, depths: list[float], values: list[float],
                    pixel_height: int) -> tuple[list[float], list[float]]:
        if len(depths) <= pixel_height * 2:
            return depths, values
        arr_v = np.array(values)
        step = max(1, len(arr_v) // pixel_height)
        result_d: list[float] = []
        result_v: list[float] = []
        for i in range(0, len(arr_v), step):
            chunk = arr_v[i:i + step]
            max_idx = i + int(np.argmax(chunk))
            min_idx = i + int(np.argmin(chunk))
            result_d.append(depths[max_idx])
            result_v.append(values[max_idx])
            result_d.append(depths[min_idx])
            result_v.append(values[min_idx])
        return result_d, result_v

    def _make_pen(self, curve: CurveData) -> QPen:
        pen = QPen(QColor(curve.color), 1.5)
        if curve.line_style == LineStyle.DASHED:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif curve.line_style == LineStyle.DOTTED:
            pen.setStyle(Qt.PenStyle.DotLine)
        else:
            pen.setStyle(Qt.PenStyle.SolidLine)
        return pen

    def paint_content(self, painter: QPainter, rect: QRectF):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setClipRect(rect)

        # Light grid
        painter.setPen(QPen(QColor("#e5e7eb"), 0.5, Qt.PenStyle.DotLine))
        painter.drawLine(int(rect.left()), int(rect.top()), int(rect.left()), int(rect.bottom()))

        pixel_height = max(1, int(rect.height()))

        for curve in self._curves:
            depths, values = self._visible_data(curve)
            depths, values = self._downsample(depths, values, pixel_height)
            if len(depths) < 2:
                continue

            path = QPainterPath()
            first = True
            for d, v in zip(depths, values):
                x = self._value_to_x(v, curve.display_range, rect)
                y = self._depth_to_y(d, rect)
                if first:
                    path.moveTo(x, y)
                    first = False
                else:
                    path.lineTo(x, y)

            painter.setPen(self._make_pen(curve))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(path)

        # Display range labels
        if self._curves:
            c = self._curves[0]
            lo, hi = c.display_range
            font = QFont()
            font.setPointSize(6)
            painter.setFont(font)
            painter.setPen(QColor("#999999"))
            painter.drawText(QRectF(rect.left(), rect.top() + 2, rect.width(), 12),
                             Qt.AlignmentFlag.AlignLeft, f"{lo}")
            painter.drawText(QRectF(rect.left(), rect.bottom() - 14, rect.width(), 12),
                             Qt.AlignmentFlag.AlignLeft, f"{hi}")

        # Border
        painter.setPen(QPen(QColor("#999999"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setClipping(False)
        painter.drawRect(rect)
        painter.restore()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_curve_track.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py tests/test_curve_track.py
git commit -m "feat(well-log): add CurveTrack with viewport culling and min-max downsampling

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 4: LayoutCoordinator — depth synchronization

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/coordinator.py`
- Test: `tests/test_coordinator.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_coordinator.py
from geoviz_well_log.renderer.coordinator import LayoutCoordinator
from geoviz_well_log.renderer.track_base import BaseTrack
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF


class StubTrack(BaseTrack):
    def __init__(self, label="stub", width=100):
        super().__init__(label=label, width=width)
        self.synced_range = None

    def paint_content(self, painter, rect):
        pass

    def set_depth_range(self, top, bottom):
        self.synced_range = (top, bottom)
        super().set_depth_range(top, bottom)


def test_coordinator_broadcasts_range():
    t1 = StubTrack()
    t2 = StubTrack()
    coord = LayoutCoordinator(tracks=[t1, t2])
    coord.set_depth_range(100.0, 500.0)
    assert t1.synced_range == (100.0, 500.0)
    assert t2.synced_range == (100.0, 500.0)


def test_coordinator_total_width():
    t1 = StubTrack(width=60)
    t2 = StubTrack(width=150)
    t3 = StubTrack(width=100)
    coord = LayoutCoordinator(tracks=[t1, t2, t3])
    assert coord.total_width == 310
```

- [ ] **Step 2: Run test**

Run: `source .venv/bin/activate && pytest tests/test_coordinator.py -v`
Expected: FAIL

- [ ] **Step 3: Implement LayoutCoordinator**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/coordinator.py
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .track_base import BaseTrack


class LayoutCoordinator:
    """Synchronizes depth range across all tracks in a canvas."""

    def __init__(self, tracks: list[BaseTrack] | None = None):
        self._tracks: list[BaseTrack] = tracks or []

    @property
    def tracks(self) -> list[BaseTrack]:
        return self._tracks

    def add_track(self, track: BaseTrack):
        self._tracks.append(track)

    def remove_track(self, track: BaseTrack):
        self._tracks.remove(track)

    @property
    def total_width(self) -> int:
        return sum(t.width for t in self._tracks)

    def set_depth_range(self, top: float, bottom: float):
        for track in self._tracks:
            track.set_depth_range(top, bottom)
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_coordinator.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/coordinator.py tests/test_coordinator.py
git commit -m "feat(well-log): add LayoutCoordinator for depth sync

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 5: WellLogCanvas — main widget

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py`
- Test: `tests/test_canvas.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_canvas.py
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData


def _make_gr_curve(n=100):
    return CurveData(name="GR", unit="API",
                     depth=list(range(n)), values=[50.0] * n,
                     display_range=(0, 150), color="#00ff00")


def test_canvas_creation():
    canvas = WellLogCanvas()
    assert len(canvas.tracks) == 0


def test_canvas_add_tracks():
    canvas = WellLogCanvas()
    depth = DepthTrack(top_depth=0, bottom_depth=100)
    curve = CurveTrack(curves=[_make_gr_curve()], label="GR", width=150)
    canvas.add_track(depth)
    canvas.add_track(curve)
    assert len(canvas.tracks) == 2
    assert canvas.total_width == 60 + 150


def test_canvas_set_depth_range():
    canvas = WellLogCanvas()
    depth = DepthTrack(top_depth=0, bottom_depth=100)
    curve = CurveTrack(curves=[_make_gr_curve()], label="GR", width=150)
    canvas.add_track(depth)
    canvas.add_track(curve)
    canvas.set_depth_range(10, 90)
    assert depth.depth_top == 10
    assert curve.depth_top == 10


def test_canvas_paint_all():
    canvas = WellLogCanvas()
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100))
    canvas.add_track(CurveTrack(curves=[_make_gr_curve()], label="GR", width=150))
    canvas.set_depth_range(0, 100)
    pm = QPixmap(canvas.total_width, 500)
    painter = QPainter(pm)
    canvas.paint_all(painter)
    painter.end()


def test_canvas_remove_track():
    canvas = WellLogCanvas()
    t1 = DepthTrack(top_depth=0, bottom_depth=100)
    t2 = CurveTrack(curves=[_make_gr_curve()], label="GR", width=150)
    canvas.add_track(t1)
    canvas.add_track(t2)
    canvas.remove_track(t1)
    assert len(canvas.tracks) == 1
    assert canvas.tracks[0] is t2
```

- [ ] **Step 2: Run test**

Run: `source .venv/bin/activate && pytest tests/test_canvas.py -v`
Expected: FAIL

- [ ] **Step 3: Implement WellLogCanvas**

```python
# packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget, QHBoxLayout

from .track_base import BaseTrack
from .coordinator import LayoutCoordinator


class WellLogCanvas(QWidget):
    """Main canvas widget for well log visualization.

    Manages track layout, depth range, and provides unified paint_all()
    for both display and vector export.
    """

    depth_range_changed = Signal(float, float)
    interval_clicked = Signal(str, float, float)
    cursor_moved = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._coordinator = LayoutCoordinator()
        self.setMinimumSize(200, 400)

    @property
    def tracks(self) -> list[BaseTrack]:
        return self._coordinator.tracks

    @property
    def total_width(self) -> int:
        return self._coordinator.total_width

    def add_track(self, track: BaseTrack):
        self._coordinator.add_track(track)
        self.setMinimumWidth(self.total_width)

    def remove_track(self, track: BaseTrack):
        self._coordinator.remove_track(track)
        self.setMinimumWidth(self.total_width)

    def set_depth_range(self, top: float, bottom: float):
        self._coordinator.set_depth_range(top, bottom)
        self.depth_range_changed.emit(top, bottom)

    def set_tracks(self, tracks: list[BaseTrack]):
        for t in self._coordinator.tracks[:]:
            self._coordinator.remove_track(t)
        for t in tracks:
            self._coordinator.add_track(t)
        self.setMinimumWidth(self.total_width)

    def paint_all(self, painter: QPainter):
        """Unified render entry: header + content for all tracks."""
        if not self.tracks:
            return

        w = self.width()
        h = self.height()
        x_offset = 0.0

        for track in self.tracks:
            full_rect = QRectF(x_offset, 0, track.width, h)
            track.export_render(painter, full_rect)
            x_offset += track.width

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        self.paint_all(painter)
        painter.end()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_canvas.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/canvas.py tests/test_canvas.py
git commit -m "feat(well-log): add WellLogCanvas main widget

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 6: QPainter export — SVG/PDF/PNG

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/export_qpainter.py`
- Test: `tests/test_renderer_export.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_renderer_export.py
import os
import tempfile

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData
from geoviz_well_log.export_qpainter import export_svg, export_pdf, export_png


def _make_canvas():
    canvas = WellLogCanvas()
    canvas.resize(210, 500)
    canvas.add_track(DepthTrack(top_depth=0, bottom_depth=100))
    curve = CurveData(name="GR", depth=list(range(100)), values=[50.0] * 100,
                      display_range=(0, 150), color="#00ff00")
    canvas.add_track(CurveTrack(curves=[curve], label="GR", width=150))
    canvas.set_depth_range(0, 100)
    return canvas


def test_export_svg_creates_file():
    canvas = _make_canvas()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.svg")
        export_svg(canvas, path)
        assert os.path.exists(path)
        content = open(path).read()
        assert "<svg" in content.lower() or "svg" in content.lower()
        assert os.path.getsize(path) > 100


def test_export_pdf_creates_file():
    canvas = _make_canvas()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.pdf")
        export_pdf(canvas, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 100


def test_export_png_creates_file():
    canvas = _make_canvas()
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "test.png")
        export_png(canvas, path)
        assert os.path.exists(path)
        assert os.path.getsize(path) > 100
```

- [ ] **Step 2: Run test**

Run: `source .venv/bin/activate && pytest tests/test_renderer_export.py -v`
Expected: FAIL

- [ ] **Step 3: Implement export_qpainter**

```python
# packages/geoviz_well_log/geoviz_well_log/export_qpainter.py
from __future__ import annotations

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QPageSize
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QPainter

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .renderer.canvas import WellLogCanvas


def export_svg(canvas: WellLogCanvas, path: str):
    """Export to SVG — fully vector, identical to display."""
    generator = QSvgGenerator()
    generator.setFileName(path)
    generator.setSize(canvas.size())
    generator.setViewBox(canvas.rect())
    painter = QPainter(generator)
    canvas.paint_all(painter)
    painter.end()


def export_pdf(canvas: WellLogCanvas, path: str):
    """Export to PDF — fully vector, identical to display."""
    printer = QPrinter(QPrinter.PrinterMode.HighResolution)
    printer.setOutputFileName(path)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    # Page size matches canvas aspect ratio
    size_mm = QSizeF(canvas.width() * 0.264583, canvas.height() * 0.264583)
    printer.setPageSize(QPageSize(size_mm, QPageSize.Unit.Millimeter))
    printer.setPageMargins(0, 0, 0, 0, QPageSize.Unit.Millimeter)
    painter = QPainter(printer)
    painter.setWindow(canvas.rect())
    canvas.paint_all(painter)
    painter.end()


def export_png(canvas: WellLogCanvas, path: str):
    """Export to PNG — raster screenshot of display."""
    pixmap = canvas.grab()
    pixmap.save(path, "PNG")
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_renderer_export.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/export_qpainter.py tests/test_renderer_export.py
git commit -m "feat(well-log): add QPainter-based vector export (SVG/PDF/PNG)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 7: Integration test — full pipeline

**Files:**
- Test: `tests/test_renderer_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_renderer_integration.py
"""Integration test: load data → build tracks → render → export."""
import os
import tempfile

from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.curve_track import CurveTrack
from geoviz_well_log.models import CurveData, LineStyle, WellLogData
from geoviz_well_log.export_qpainter import export_svg, export_pdf, export_png
import numpy as np


def _make_well_log_data(n_curves=3, n_points=2000):
    """Simulate a realistic well with 3 curves and 2000 sample points."""
    depths = np.linspace(2500, 2600, n_points).tolist()
    curves = [
        CurveData(name="GR", unit="API", depth=depths,
                  values=np.random.uniform(10, 120, n_points).tolist(),
                  display_range=(0, 150), color="#22c55e"),
        CurveData(name="AC", unit="us/ft", depth=depths,
                  values=np.random.uniform(40, 80, n_points).tolist(),
                  display_range=(40, 240), color="#3b82f6", line_style=LineStyle.DASHED),
        CurveData(name="RT", unit="ohm.m", depth=depths,
                  values=np.random.uniform(0.5, 200, n_points).tolist(),
                  display_range=(0.2, 2000), color="#ef4444"),
    ]
    return WellLogData(well_name="Test-1", top_depth=2500, bottom_depth=2600, curves=curves)


def test_full_pipeline_svg_export():
    data = _make_well_log_data()
    canvas = WellLogCanvas()
    canvas.resize(360, 800)

    # Build tracks
    canvas.add_track(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))
    for c in data.curves:
        is_log = c.name in ("RT", "RXO")
        canvas.add_track(CurveTrack(curves=[c], label=f"{c.name} ({c.unit})",
                                    width=100, log_scale=is_log))
    canvas.set_depth_range(data.top_depth, data.bottom_depth)

    # Export SVG
    with tempfile.TemporaryDirectory() as tmp:
        svg_path = os.path.join(tmp, "integration.svg")
        export_svg(canvas, svg_path)
        assert os.path.exists(svg_path)
        content = open(svg_path).read()
        # SVG should contain path elements (vector curves)
        assert "path" in content.lower()
        assert os.path.getsize(svg_path) > 500


def test_full_pipeline_pdf_export():
    data = _make_well_log_data(n_points=5000)
    canvas = WellLogCanvas()
    canvas.resize(360, 800)
    canvas.add_track(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))
    for c in data.curves:
        is_log = c.name in ("RT", "RXO")
        canvas.add_track(CurveTrack(curves=[c], label=f"{c.name} ({c.unit})",
                                    width=100, log_scale=is_log))
    canvas.set_depth_range(data.top_depth, data.bottom_depth)

    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "integration.pdf")
        export_pdf(canvas, pdf_path)
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 500


def test_depth_zoom_performance():
    """Zooming should be fast even with 5000 points."""
    import time
    data = _make_well_log_data(n_points=5000)
    canvas = WellLogCanvas()
    canvas.resize(260, 800)
    canvas.add_track(DepthTrack(top_depth=data.top_depth, bottom_depth=data.bottom_depth))
    canvas.add_track(CurveTrack(curves=[data.curves[0]], label="GR", width=200))
    canvas.set_depth_range(data.top_depth, data.bottom_depth)

    # Force layout
    canvas.show()

    # Simulate zoom
    start = time.time()
    for _ in range(10):
        canvas.set_depth_range(2520, 2540)
        canvas.set_depth_range(2500, 2600)
    elapsed = time.time() - start
    assert elapsed < 1.0, f"10 zoom cycles took {elapsed:.2f}s — too slow"
```

- [ ] **Step 2: Run test**

Run: `source .venv/bin/activate && pytest tests/test_renderer_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_renderer_integration.py
git commit -m "test(well-log): add integration tests for full QPainter renderer pipeline

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 8: Update __init__.py and run full test suite

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/__init__.py`

- [ ] **Step 1: Add renderer exports to __init__.py**

Add these lines to the existing `__init__.py` (after existing imports):

```python
# New QPainter renderer
from .renderer import BaseTrack, DepthTrack, CurveTrack, WellLogCanvas, LayoutCoordinator, OverlayManager
from .export_qpainter import export_svg as qpainter_export_svg
from .export_qpainter import export_pdf as qpainter_export_pdf
from .export_qpainter import export_png as qpainter_export_png
```

Add to `__all__`:
```python
    "BaseTrack", "DepthTrack", "CurveTrack", "WellLogCanvas",
    "LayoutCoordinator", "OverlayManager",
    "qpainter_export_svg", "qpainter_export_pdf", "qpainter_export_png",
```

- [ ] **Step 2: Run full test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All existing tests + new renderer tests pass.

- [ ] **Step 3: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/__init__.py
git commit -m "feat(well-log): export new QPainter renderer from package __init__

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```
