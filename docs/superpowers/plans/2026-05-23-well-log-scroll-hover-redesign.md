# Well Log Scrolling & Hover Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken scrolling and hover panel in the QPainter well log renderer, add a depth ruler, and add linear interpolation for curve values.

**Architecture:** Remove the vertical scrollbar (which conflicts with wheel zoom), add a custom DepthRuler widget on the right edge, fix coordinate mapping in the crosshair overlay, and add linear interpolation for curve value readouts.

**Tech Stack:** PySide6 (Qt for Python), QPainter, QScrollArea

---

### Task 1: Fix QPainterWidget — remove vertical scrollbar, simplify canvas sizing

**Files:**
- Modify: `src/pages/well_log/qpainter_widget.py`

- [ ] **Step 1: Rewrite QPainterWidget to remove vertical scrollbar**

Replace the entire file with:

```python
from __future__ import annotations

from PySide6.QtCore import Qt, QRectF, QObject, QEvent
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics, QBrush, QMouseEvent
from PySide6.QtWidgets import QWidget, QScrollArea, QApplication

from geoviz_well_log import WellLogCanvas, ZoomPanHandler, CrosshairOverlay
from geoviz_well_log.renderer.track_base import BaseTrack


class _CrosshairOverlayWidget(QWidget):
    """Transparent widget sitting on top of viewport that paints the crosshair overlay."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def paintEvent(self, event):
        pass  # painted externally by QPainterWidget


class QPainterWidget(QScrollArea):
    """Scroll area wrapping WellLogCanvas with zoom/pan and crosshair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_top = 0.0
        self._full_bottom = 100.0

        self._canvas = WellLogCanvas(self)
        self._zoom_handler = ZoomPanHandler(self._canvas, self)
        self._crosshair = CrosshairOverlay(self._canvas)

        self.setWidget(self._canvas)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._canvas.setMouseTracking(True)
        self._canvas.mouse_moved.connect(self._on_mouse_moved)

        # Transparent overlay on top of viewport for crosshair painting
        self._overlay = _CrosshairOverlayWidget(self.viewport())

    @property
    def canvas(self) -> WellLogCanvas:
        return self._canvas

    def set_tracks(self, tracks: list[BaseTrack]):
        self._canvas.set_tracks(tracks)
        if tracks:
            self._full_top = tracks[0].depth_top
            self._full_bottom = tracks[0].depth_bottom
            self._zoom_handler.set_full_range(self._full_top, self._full_bottom)
        self._sync_overlay_geometry()
        self._update_canvas_size()

    def set_depth_range(self, top: float, bottom: float):
        self._canvas.set_depth_range(top, bottom)

    def reset_view(self):
        self._canvas.set_depth_range(self._full_top, self._full_bottom)

    def _sync_overlay_geometry(self):
        """Keep overlay widget covering the full viewport."""
        if hasattr(self, "_overlay"):
            self._overlay.setGeometry(self.viewport().rect())

    def _update_canvas_size(self):
        viewport_w = self.viewport().width()
        total_w = self._canvas.total_width
        self._canvas.setMinimumWidth(max(total_w, viewport_w))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_overlay_geometry()
        self._update_canvas_size()

    def _on_mouse_moved(self, canvas_y: float):
        if canvas_y < 0:
            self._crosshair.set_cursor_y(None)
        else:
            self._crosshair.set_cursor_y(canvas_y)
        self._overlay.update()

    def wheelEvent(self, event):
        """Forward wheel events to canvas so ZoomPanHandler handles zoom."""
        from PySide6.QtGui import QWheelEvent
        canvas_pos = self._canvas.mapFrom(self.viewport(), event.position().toPoint())
        canvas_global = event.globalPosition().toPoint() - event.position().toPoint() + canvas_pos
        new_event = QWheelEvent(
            canvas_pos,
            canvas_global,
            event.pixelDelta(),
            event.angleDelta(),
            event.buttons(),
            event.modifiers(),
            event.phase(),
            event.inverted(),
        )
        QApplication.sendEvent(self._canvas, new_event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._crosshair.visible and self._canvas.tracks:
            painter = QPainter(self._overlay)
            self._crosshair.paint_overlay(painter, QRectF(self._overlay.rect()))
            painter.end()
```

Key changes:
- `setWidgetResizable(True)` — canvas fills viewport height
- `ScrollBarAlwaysOff` vertical — no vertical scrollbar
- `_update_canvas_size` only sets `setMinimumWidth` (no height manipulation)
- Removed `_px_per_depth`, `_on_depth_range_changed`, `depth_range_changed` connection
- `wheelEvent` override forwards to canvas
- `paintOverlay` called without `scroll_offset` (always 0 with no vertical scroll)

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All 213 tests pass

- [ ] **Step 3: Commit**

```bash
git add src/pages/well_log/qpainter_widget.py
git commit -m "fix(well-log): remove vertical scrollbar, fix wheel zoom forwarding

- SetWidgetResizable(True) so canvas fills viewport
- ScrollBarAlwaysOff vertical eliminates wheel event conflict
- wheelEvent override forwards to canvas for ZoomPanHandler
- Simplified canvas sizing to setMinimumWidth only"
```

---

### Task 2: Create DepthRuler widget

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/renderer/depth_ruler.py`
- Test: `tests/test_depth_ruler.py`

- [ ] **Step 1: Write the failing test for DepthRuler**

```python
import pytest
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtCore import QRectF, Qt

from geoviz_well_log.renderer.depth_ruler import DepthRuler


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_depth_ruler_creation(app):
    ruler = DepthRuler()
    assert ruler is not None
    assert ruler.width() == 50


def test_depth_ruler_nice_intervals(app):
    ruler = DepthRuler()
    # Full range 0-3000m in 600px viewport => 5m/px
    # Target spacing 60px => 300m interval => rounds to 500
    intervals = ruler._compute_nice_intervals(0, 3000, 600)
    assert intervals == 500

    # Zoomed range 1000-1100m in 600px viewport => 0.167m/px
    # Target spacing 60px => 10m interval
    intervals = ruler._compute_nice_intervals(1000, 1100, 600)
    assert intervals == 10


def test_depth_ruler_paint_no_crash(app):
    ruler = DepthRuler()
    ruler.set_depth_range(0, 1000)
    ruler.set_cursor_depth(500.0)
    ruler.resize(50, 600)
    pm = QPixmap(50, 600)
    painter = QPainter(pm)
    ruler.paintEvent(None)  # paint directly
    painter.end()


def test_depth_ruler_cursor_indicator(app):
    ruler = DepthRuler()
    ruler.set_depth_range(0, 1000)
    ruler.set_cursor_depth(500.0)
    # depth 500 in range 0-1000 => 50% from top
    y = ruler._depth_to_y(500.0)
    assert y == pytest.approx(300.0, abs=1.0)  # 600px viewport * 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_depth_ruler.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'geoviz_well_log.renderer.depth_ruler'"

- [ ] **Step 3: Implement DepthRuler**

Create `packages/geoviz_well_log/geoviz_well_log/renderer/depth_ruler.py`:

```python
from __future__ import annotations

import math
from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QPainter, QPen, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget


class DepthRuler(QWidget):
    """Depth ruler widget showing depth labels and cursor position on the right edge."""

    _NICE_NUMBERS = [1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]
    _TARGET_PIXEL_SPACING = 60

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(50)
        self._depth_top = 0.0
        self._depth_bottom = 1000.0
        self._cursor_depth: float | None = None

    def set_depth_range(self, top: float, bottom: float):
        self._depth_top = top
        self._depth_bottom = bottom
        self.update()

    def set_cursor_depth(self, depth: float | None):
        self._cursor_depth = depth
        self.update()

    def _depth_to_y(self, depth: float) -> float:
        """Convert depth value to widget Y coordinate."""
        span = self._depth_bottom - self._depth_top
        if span <= 0:
            return 0.0
        ratio = (depth - self._depth_top) / span
        return ratio * self.height()

    def _compute_nice_intervals(self, top: float, bottom: float, height: int) -> float:
        """Compute a nice label interval for the given depth range and pixel height."""
        span = bottom - top
        if span <= 0 or height <= 0:
            return 1.0
        raw = (span / height) * self._TARGET_PIXEL_SPACING
        exp = math.floor(math.log10(raw)) if raw > 0 else 0
        base = 10 ** exp
        for n in self._NICE_NUMBERS:
            candidate = n * base
            if candidate >= raw:
                return candidate
        return self._NICE_NUMBERS[-1] * base

    def paintEvent(self, event):
        if self._depth_bottom <= self._depth_top:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(self.rect(), QColor("#f8fafc"))

        # Left border
        painter.setPen(QPen(QColor("#cbd5e1"), 2))
        painter.drawLine(0, 0, 0, h)

        # Compute label interval
        interval = self._compute_nice_intervals(self._depth_top, self._depth_bottom, h)

        # Draw depth labels and tick marks
        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(QPen(QColor("#64748b")))

        fm = QFontMetrics(font)
        start = math.ceil(self._depth_top / interval) * interval
        depth = start
        while depth <= self._depth_bottom:
            y = self._depth_to_y(depth)
            if 0 <= y <= h:
                # Tick mark (6px wide)
                painter.setPen(QPen(QColor("#94a3b8"), 1))
                painter.drawLine(0, int(y), 6, int(y))
                # Depth label
                painter.setPen(QPen(QColor("#64748b")))
                label = f"{depth:.0f}" if depth == int(depth) else f"{depth:.1f}"
                text_rect = QRectF(8, y - fm.height() / 2, w - 10, fm.height())
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, label)
            depth += interval

        # Cursor depth indicator
        if self._cursor_depth is not None:
            cy = self._depth_to_y(self._cursor_depth)
            if 0 <= cy <= h:
                # Highlight band
                band_h = 20
                band_top = max(0, cy - band_h / 2)
                band_rect = QRectF(0, band_top, w, band_h)
                painter.fillRect(band_rect, QColor(254, 242, 242))
                painter.setPen(QPen(QColor("#ef4444"), 1))
                painter.drawLine(0, int(band_top), w, int(band_top))
                painter.drawLine(0, int(band_top + band_h), w, int(band_top + band_h))
                # Depth label
                painter.setPen(QPen(QColor("#dc2626")))
                bold_font = QFont(font)
                bold_font.setBold(True)
                painter.setFont(bold_font)
                label = f"{self._cursor_depth:.0f}m" if self._cursor_depth == int(self._cursor_depth) else f"{self._cursor_depth:.1f}m"
                text_rect = QRectF(0, band_top + 2, w, band_h - 4)
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        painter.end()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_depth_ruler.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/depth_ruler.py tests/test_depth_ruler.py
git commit -m "feat(well-log): add DepthRuler widget with smart label spacing"
```

---

### Task 3: Add linear interpolation to CrosshairOverlay

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py:40-56`
- Test: `tests/test_overlay.py`

- [ ] **Step 1: Write the failing test for interpolation**

Add to `tests/test_overlay.py`:

```python
def test_overlay_interpolation(qtbot):
    """Curve values should be linearly interpolated between depth points."""
    from geoviz_well_log.renderer.curve_track import CurveTrack
    from geoviz_well_log.models import CurveData

    canvas = WellLogCanvas()
    qtbot.addWidget(canvas)
    canvas.resize(210, 500)

    # Create a curve with known values
    curve = CurveData(
        name="GR",
        depth=[0.0, 100.0],
        values=[10.0, 20.0],
    )
    track = CurveTrack(top_depth=0, bottom_depth=100)
    track.add_curve(curve)
    canvas.add_track(track)
    canvas.set_depth_range(0, 100)

    overlay = CrosshairOverlay(canvas)
    # depth=50 should interpolate to 15.0 (midpoint)
    rows = overlay._collect_values(50.0)
    gr_rows = [(n, v) for n, v in rows if n == "GR"]
    assert len(gr_rows) == 1
    assert float(gr_rows[0][1]) == pytest.approx(15.0, abs=0.1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tests/test_overlay.py::test_overlay_interpolation -v`
Expected: FAIL (currently returns nearest neighbor value, not interpolated)

- [ ] **Step 3: Add linear interpolation to `_collect_values`**

In `packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py`, replace the CurveTrack branch in `_collect_values` (lines 46-56):

```python
            if isinstance(track, CurveTrack):
                for curve in track._curves:
                    depths = track._sorted_depths.get(curve.name, curve.depth)
                    values = track._sorted_values.get(curve.name, curve.values)
                    if len(depths) < 2:
                        continue
                    idx = bisect.bisect_left(depths, depth)
                    # Clamp to valid range
                    idx = max(0, min(idx, len(depths) - 1))
                    # Find bracketing indices for interpolation
                    if idx > 0 and depth < depths[idx]:
                        i0, i1 = idx - 1, idx
                    elif idx < len(depths) - 1 and depth > depths[idx]:
                        i0, i1 = idx, idx + 1
                    else:
                        i0, i1 = idx, idx
                    d0, d1 = depths[i0], depths[i1]
                    v0, v1 = values[i0], values[i1]
                    if d1 - d0 > 0:
                        interp = v0 + (depth - d0) / (d1 - d0) * (v1 - v0)
                    else:
                        interp = v0
                    rows.append((curve.name, f"{interp:.2f}"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tests/test_overlay.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/overlay.py tests/test_overlay.py
git commit -m "feat(well-log): add linear interpolation to crosshair value readout"
```

---

### Task 4: Export DepthRuler from package

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py`
- Modify: `packages/geoviz_well_log/geoviz_well_log/__init__.py`

- [ ] **Step 1: Add DepthRuler to renderer __init__.py**

In `packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py`, add:

```python
from .depth_ruler import DepthRuler
```

And add `"DepthRuler"` to `__all__`.

- [ ] **Step 2: Add DepthRuler to package __init__.py**

In `packages/geoviz_well_log/geoviz_well_log/__init__.py`, add `DepthRuler` to the import from `.renderer` and to `__all__`.

- [ ] **Step 3: Run all tests**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/renderer/__init__.py packages/geoviz_well_log/geoviz_well_log/__init__.py
git commit -m "feat(well-log): export DepthRuler from package"
```

---

### Task 5: Integrate DepthRuler into QPainterWidget

**Files:**
- Modify: `src/pages/well_log/qpainter_widget.py`

- [ ] **Step 1: Add DepthRuler to QPainterWidget**

Update `qpainter_widget.py` to import and use DepthRuler:

```python
from geoviz_well_log import WellLogCanvas, ZoomPanHandler, CrosshairOverlay, DepthRuler
```

In `__init__`, after creating the overlay:

```python
        # Depth ruler on right edge
        self._depth_ruler = DepthRuler(self.viewport())
```

In `set_tracks`, after setting full range:

```python
        self._depth_ruler.set_depth_range(self._full_top, self._full_bottom)
```

In `_sync_overlay_geometry`, also sync ruler geometry:

```python
    def _sync_overlay_geometry(self):
        if hasattr(self, "_overlay"):
            vp = self.viewport().rect()
            ruler_w = self._depth_ruler.width()
            self._overlay.setGeometry(vp.adjusted(0, 0, -ruler_w, 0))
            self._depth_ruler.setGeometry(vp.width() - ruler_w, 0, ruler_w, vp.height())
```

In `_on_mouse_moved`, update ruler cursor depth:

```python
    def _on_mouse_moved(self, canvas_y: float):
        if canvas_y < 0:
            self._crosshair.set_cursor_y(None)
            self._depth_ruler.set_cursor_depth(None)
        else:
            self._crosshair.set_cursor_y(canvas_y)
            depth = self._crosshair.depth_at_y(canvas_y)
            self._depth_ruler.set_cursor_depth(depth)
        self._overlay.update()
```

In `resizeEvent`, sync ruler depth range:

```python
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_overlay_geometry()
        self._update_canvas_size()
```

- [ ] **Step 2: Run all tests**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/pages/well_log/qpainter_widget.py
git commit -m "feat(well-log): integrate DepthRuler into QPainterWidget"
```

---

### Task 6: Final verification and cleanup

**Files:**
- Modify: `src/pages/well_log/qpainter_widget.py` (remove unused imports)

- [ ] **Step 1: Clean up unused imports in qpainter_widget.py**

Remove unused imports: `QMouseEvent`, `QPen`, `QColor`, `QFont`, `QFontMetrics`, `QBrush`, `QEvent`, `QObject`

- [ ] **Step 2: Run full test suite**

Run: `source .venv/bin/activate && python -m pytest tests/ -v`
Expected: All tests pass, no regressions

- [ ] **Step 3: Manual verification**

Launch the app and verify:
1. Wheel zoom works (no scrollbar conflict)
2. Depth ruler shows labels on right edge
3. Hover panel shows correct depth and interpolated values
4. Horizontal scrollbar works for wide tracks

- [ ] **Step 4: Final commit**

```bash
git add src/pages/well_log/qpainter_widget.py
git commit -m "chore(well-log): clean up unused imports"
```
