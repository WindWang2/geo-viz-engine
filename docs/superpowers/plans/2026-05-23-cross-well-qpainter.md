# Cross-Well QPainter Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the cross-well comparison page from ECharts (ChartEngine/QWebEngineView) to QPainter rendering, matching the single-well architecture. Add well reordering, depth ruler, crosshair, and per-well track control.

**Architecture:** Each well is an independent `WellLogCanvas` in a horizontal layout. A `ConnectionOverlay` draws correlation polygons between adjacent canvases. A `QPainterSyncManager` synchronizes zoom/pan via Qt signals. A shared `DepthRuler` sits on the right edge. Export composites all canvases into a single SVG/PDF/PNG.

**Tech Stack:** PySide6 (Qt for Python), QPainter, Pydantic models

---

## File Structure

### New files
- `packages/geoviz_well_log/geoviz_well_log/painter_sync_manager.py` — Signal-based zoom sync for WellLogCanvas
- `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py` — New cross-well page widget
- `tests/test_painter_sync_manager.py` — Unit tests for sync manager
- `tests/test_connection_overlay_painter.py` — Unit tests for updated ConnectionOverlay
- `tests/test_cross_well_widget.py` — Integration tests for the new page

### Modified files
- `packages/geoviz_well_log/geoviz_well_log/connection_overlay.py` — Adapt for WellLogCanvas coordinate mapping
- `packages/geoviz_well_log/geoviz_well_log/__init__.py` — Export new classes
- `src/pages/cross_well/page.py` — Thin wrapper calling package

### Removed
- `packages/geoviz_well_log/geoviz_well_log/sync_manager.py` — JS-based sync (replaced by `painter_sync_manager.py`)

---

### Task 1: QPainterSyncManager

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/painter_sync_manager.py`
- Test: `tests/test_painter_sync_manager.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_painter_sync_manager.py
import pytest
from PySide6.QtWidgets import QApplication
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.painter_sync_manager import QPainterSyncManager


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_sync_manager_creation(app):
    mgr = QPainterSyncManager()
    assert mgr._canvases == []
    assert mgr._is_syncing is False


def test_sync_manager_add_canvas(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    assert len(mgr._canvases) == 2


def test_sync_manager_range_sync(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    # Set initial range on both
    c1.set_depth_range(0, 100)
    c2.set_depth_range(0, 100)
    # Change range on c1 — should propagate to c2
    c1.set_depth_range(10, 90)
    assert c2.depth_span == 80.0


def test_sync_manager_no_recursion(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    c1.set_depth_range(0, 100)
    c2.set_depth_range(0, 100)
    # This should not infinite-loop
    c1.set_depth_range(20, 80)
    assert c2.depth_span == 60.0


def test_sync_manager_remove_canvas(app):
    mgr = QPainterSyncManager()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    mgr.add_canvas(c1)
    mgr.add_canvas(c2)
    mgr.remove_canvas(c1)
    assert len(mgr._canvases) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_painter_sync_manager.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'geoviz_well_log.painter_sync_manager'"

- [ ] **Step 3: Write minimal implementation**

```python
# packages/geoviz_well_log/geoviz_well_log/painter_sync_manager.py
from __future__ import annotations

from PySide6.QtCore import QObject

from .renderer.canvas import WellLogCanvas


class QPainterSyncManager(QObject):
    """Synchronizes depth range across multiple WellLogCanvas widgets via Qt signals."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvases: list[WellLogCanvas] = []
        self._is_syncing = False

    def add_canvas(self, canvas: WellLogCanvas):
        if canvas not in self._canvases:
            self._canvases.append(canvas)
            canvas.depth_range_changed.connect(self._on_range_changed)

    def remove_canvas(self, canvas: WellLogCanvas):
        if canvas in self._canvases:
            canvas.depth_range_changed.disconnect(self._on_range_changed)
            self._canvases.remove(canvas)

    def _on_range_changed(self, top: float, bottom: float):
        if self._is_syncing:
            return
        self._is_syncing = True
        try:
            for canvas in self._canvases:
                canvas.blockSignals(True)
                canvas.set_depth_range(top, bottom)
                canvas.blockSignals(False)
        finally:
            self._is_syncing = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_painter_sync_manager.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/painter_sync_manager.py tests/test_painter_sync_manager.py
git commit -m "feat(well-log): add QPainterSyncManager for cross-well zoom sync"
```

---

### Task 2: Update ConnectionOverlay for QPainter Canvases

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/connection_overlay.py`
- Test: `tests/test_connection_overlay_painter.py`

The current `ConnectionOverlay` uses an `_depth_cache` dict populated by JavaScript calls. With QPainter canvases, we compute pixel positions directly from canvas geometry and depth range.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_connection_overlay_painter.py
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QImage

from geoviz_well_log.connection_overlay import ConnectionOverlay
from geoviz_well_log.renderer.canvas import WellLogCanvas
from geoviz_well_log.renderer.depth_track import DepthTrack
from src.data.models import CorrelationLink


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_canvas(well_name: str, top: float, bottom: float) -> WellLogCanvas:
    canvas = WellLogCanvas()
    canvas.resize(200, 600)
    track = DepthTrack(top_depth=top, bottom_depth=bottom, width=60, label="深度")
    canvas.set_tracks([track])
    return canvas


def test_connection_overlay_creation(app):
    overlay = ConnectionOverlay()
    assert overlay._canvases == []
    assert overlay._links == []


def test_connection_overlay_set_canvases(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    c2 = _make_canvas("well2", 0, 100)
    overlay.set_canvases([c1, c2])
    assert len(overlay._canvases) == 2


def test_connection_overlay_depth_to_y(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    overlay.set_canvases([c1])
    # depth 50 should map to roughly halfway down the content area
    y = overlay.depth_to_y(c1, 50.0)
    assert isinstance(y, float)
    assert y > 0


def test_connection_overlay_paint_no_crash(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    c2 = _make_canvas("well2", 0, 100)
    overlay.set_canvases([c1, c2])
    link = CorrelationLink(
        source_well="well1", target_well="well2",
        source_interval_id="10_50_FormationA",
        target_interval_id="15_55_FormationA",
        color="#f59e0b",
    )
    overlay.set_links([link])
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    overlay.paint_event(painter, QRectF(img.rect()))
    painter.end()


def test_connection_overlay_empty_links_no_crash(app):
    overlay = ConnectionOverlay()
    c1 = _make_canvas("well1", 0, 100)
    overlay.set_canvases([c1])
    img = QImage(800, 600, QImage.Format.Format_ARGB32)
    img.fill(0)
    painter = QPainter(img)
    overlay.paint_event(painter, QRectF(img.rect()))
    painter.end()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_connection_overlay_painter.py -v`
Expected: FAIL — `ConnectionOverlay` doesn't have `set_canvases` or `depth_to_y` methods

- [ ] **Step 3: Write minimal implementation**

Replace `connection_overlay.py` with:

```python
# packages/geoviz_well_log/geoviz_well_log/connection_overlay.py
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QPainter, QColor, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .renderer.canvas import WellLogCanvas


class ConnectionOverlay(QWidget):
    """Transparent overlay drawing correlation polygons between WellLogCanvas widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._canvases: list[WellLogCanvas] = []
        self._links: list = []

    def set_canvases(self, canvases: list[WellLogCanvas]):
        self._canvases = list(canvases)
        self.update()

    def set_links(self, links: list):
        self._links = list(links)
        self.update()

    def depth_to_y(self, canvas: WellLogCanvas, depth: float) -> float:
        """Convert a depth value to Y pixel position within the canvas."""
        if not canvas.tracks:
            return 0.0
        header_h = max((t.header_height for t in canvas.tracks), default=56)
        content_h = canvas.height() - header_h
        if content_h <= 0:
            return 0.0
        track = canvas.tracks[0]
        span = track.depth_span
        if span <= 0:
            return header_h
        ratio = (depth - track.depth_top) / span
        return header_h + ratio * content_h

    def _canvas_left(self, canvas: WellLogCanvas) -> float:
        """Get canvas left edge x position relative to this widget."""
        return canvas.mapTo(self, canvas.rect().topLeft()).x()

    def _canvas_right(self, canvas: WellLogCanvas) -> float:
        return canvas.mapTo(self, canvas.rect().topRight()).x()

    def paintEvent(self, event):
        self.paint_event(QPainter(self), QRectF(self.rect()))

    def paint_event(self, painter: QPainter, rect: QRectF):
        if not self._links or not self._canvases:
            return
        canvas_map = {c: c for c in self._canvases}
        # Also match by well_name if available
        name_map = {}
        for c in self._canvases:
            if c.tracks:
                name_map[c.tracks[0].label] = c

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        for link in self._links:
            source = canvas_map.get(link.source_well) or name_map.get(link.source_well)
            target = canvas_map.get(link.target_well) or name_map.get(link.target_well)
            if source is None or target is None:
                continue

            src_left = self._canvas_left(source)
            src_right = self._canvas_right(source)
            tgt_left = self._canvas_left(target)
            tgt_right = self._canvas_right(target)

            # Parse interval_id format: "top_bottom_name"
            try:
                src_parts = link.source_interval_id.split("_")
                src_top = float(src_parts[0])
                src_bot = float(src_parts[1])
                tgt_parts = link.target_interval_id.split("_")
                tgt_top = float(tgt_parts[0])
                tgt_bot = float(tgt_parts[1])
            except (ValueError, IndexError):
                continue

            # Map depths to Y positions (offset by scroll)
            sy1 = self.depth_to_y(source, src_top)
            sy2 = self.depth_to_y(source, src_bot)
            ty1 = self.depth_to_y(target, tgt_top)
            ty2 = self.depth_to_y(target, tgt_bot)

            polygon = QPolygonF([
                (src_right, sy1),
                (tgt_left, ty1),
                (tgt_left, ty2),
                (src_right, sy2),
            ])

            color = QColor(link.color)
            color.setAlpha(120)
            painter.setPen(QPen(color.darker(120), 1))
            painter.setBrush(color)
            painter.drawPolygon(polygon)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_connection_overlay_painter.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/connection_overlay.py tests/test_connection_overlay_painter.py
git commit -m "feat(well-log): adapt ConnectionOverlay for QPainter canvas coordinate mapping"
```

---

### Task 3: CrossWellWidget — Core Container

**Files:**
- Create: `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`
- Test: `tests/test_cross_well_widget.py`

This is the main cross-well widget. It contains the toolbar, scroll area with canvas containers, overlay, sync manager, and depth ruler.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cross_well_widget.py
import pytest
from PySide6.QtWidgets import QApplication

from geoviz_well_log.cross_well_widget import CrossWellWidget
from geoviz_well_log.renderer.canvas import WellLogCanvas


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_cross_well_widget_creation(app):
    widget = CrossWellWidget()
    assert widget.canvas_count == 0
    assert widget._canvases == []


def test_cross_well_widget_add_well(app):
    widget = CrossWellWidget()
    canvas = WellLogCanvas()
    widget.add_canvas(canvas, "well1")
    assert widget.canvas_count == 1
    assert widget._canvases[0] is canvas


def test_cross_well_widget_remove_well(app):
    widget = CrossWellWidget()
    c1 = WellLogCanvas()
    c2 = WellLogCanvas()
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.remove_canvas(c1)
    assert widget.canvas_count == 1


def test_cross_well_widget_clear_all(app):
    widget = CrossWellWidget()
    widget.add_canvas(WellLogCanvas(), "well1")
    widget.add_canvas(WellLogCanvas(), "well2")
    widget.clear_all()
    assert widget.canvas_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'geoviz_well_log.cross_well_widget'"

- [ ] **Step 3: Write minimal implementation**

```python
# packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QToolBar, QMenu,
    QPushButton, QComboBox, QSizePolicy, QSpacerItem,
)

from .renderer.canvas import WellLogCanvas
from .renderer.depth_ruler import DepthRuler
from .connection_overlay import ConnectionOverlay
from .painter_sync_manager import QPainterSyncManager
from .qpainter_builder import build_qpainter_tracks


class CrossWellWidget(QWidget):
    """Multi-well cross-section view using QPainter-rendered WellLogCanvas widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._canvases: list[WellLogCanvas] = []
        self._well_names: list[str] = []
        self._sync_manager = QPainterSyncManager(self)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self._toolbar = QToolBar()
        main_layout.addWidget(self._toolbar)

        # Scroll area with horizontal layout
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(150)
        self._container_layout.addStretch()
        self._scroll.setWidget(self._container)
        main_layout.addWidget(self._scroll)

        # Connection overlay on container
        self._overlay = ConnectionOverlay(self._container)

        # Depth ruler on right edge of scroll viewport
        self._depth_ruler = DepthRuler(self._scroll.viewport())

        # Track data cache
        self._well_data_cache: dict[str, object] = {}

    @property
    def canvas_count(self) -> int:
        return len(self._canvases)

    def add_canvas(self, canvas: WellLogCanvas, well_name: str):
        """Add a well canvas to the cross-well view."""
        self._canvases.append(canvas)
        self._well_names.append(well_name)
        # Insert before the stretch
        idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(idx, canvas)
        self._sync_manager.add_canvas(canvas)
        canvas.setMouseTracking(True)
        self._update_overlay_geometry()

    def remove_canvas(self, canvas: WellLogCanvas):
        """Remove a well canvas from the cross-well view."""
        if canvas in self._canvases:
            idx = self._canvases.index(canvas)
            self._sync_manager.remove_canvas(canvas)
            self._container_layout.removeWidget(canvas)
            canvas.setParent(None)
            self._canvases.pop(idx)
            self._well_names.pop(idx)
            self._update_overlay_geometry()

    def clear_all(self):
        """Remove all wells and clear state."""
        for canvas in self._canvases[:]:
            self.remove_canvas(canvas)
        self._overlay.set_links([])
        self._well_data_cache.clear()

    def _update_overlay_geometry(self):
        """Update overlay geometry to cover the container."""
        if self._overlay:
            self._overlay.setGeometry(self._container.rect())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_overlay_geometry()
        # Position depth ruler
        vp = self._scroll.viewport().rect()
        ruler_w = self._depth_ruler.width()
        self._depth_ruler.setGeometry(vp.width() - ruler_w, 0, ruler_w, vp.height())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py tests/test_cross_well_widget.py
git commit -m "feat(well-log): add CrossWellWidget container for multi-well QPainter view"
```

---

### Task 4: Auto-Link and Manual Link

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`
- Test: `tests/test_cross_well_widget.py`

Migrate the auto-link algorithm and manual link interaction from the old `CrossWellPage`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cross_well_widget.py`:

```python
from geoviz_well_log.renderer.depth_track import DepthTrack
from geoviz_well_log.renderer.interval_track import IntervalTrack
from geoviz_well_log.models import IntervalItem
from src.data.models import CorrelationLink


def _make_well_canvas(well_name: str, intervals: list[IntervalItem]) -> WellLogCanvas:
    canvas = WellLogCanvas()
    canvas.resize(200, 600)
    tracks = [DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度")]
    if intervals:
        tracks.append(IntervalTrack(intervals=intervals, label="组", width=50))
    canvas.set_tracks(tracks)
    return canvas


def test_auto_link_matches_common_intervals(app):
    widget = CrossWellWidget()
    iv1 = [IntervalItem(top=10, bottom=50, name="FormationA")]
    iv2 = [IntervalItem(top=15, bottom=55, name="FormationA")]
    c1 = _make_well_canvas("well1", iv1)
    c2 = _make_well_canvas("well2", iv2)
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    assert len(widget._overlay._links) == 1
    link = widget._overlay._links[0]
    assert link.source_well == "well1"
    assert link.target_well == "well2"


def test_auto_link_no_match(app):
    widget = CrossWellWidget()
    iv1 = [IntervalItem(top=10, bottom=50, name="FormationA")]
    iv2 = [IntervalItem(top=15, bottom=55, name="FormationB")]
    c1 = _make_well_canvas("well1", iv1)
    c2 = _make_well_canvas("well2", iv2)
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    assert len(widget._overlay._links) == 0


def test_manual_link(app):
    widget = CrossWellWidget()
    iv1 = [IntervalItem(top=10, bottom=50, name="FormationA")]
    iv2 = [IntervalItem(top=15, bottom=55, name="FormationA")]
    c1 = _make_well_canvas("well1", iv1)
    c2 = _make_well_canvas("well2", iv2)
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.toggle_manual_link()
    assert widget._manual_link_active is True
    # Simulate picking two intervals
    widget._manual_link_picks = [
        ("well1", IntervalItem(top=10, bottom=50, name="FormationA")),
        ("well2", IntervalItem(top=15, bottom=55, name="FormationA")),
    ]
    widget._finish_manual_link()
    assert len(widget._overlay._links) == 1
    assert widget._overlay._links[0].is_manual is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_widget.py -v -k "auto_link or manual_link"`
Expected: FAIL — `auto_link`, `toggle_manual_link`, `_finish_manual_link` don't exist

- [ ] **Step 3: Write implementation**

Add to `cross_well_widget.py`:

```python
from .models import IntervalItem

# In CrossWellWidget.__init__:
        self._manual_link_active = False
        self._manual_link_picks: list[tuple[str, IntervalItem]] = []

    def auto_link(self):
        """Auto-correlate intervals between adjacent wells by name matching."""
        links = []
        for i in range(len(self._canvases) - 1):
            c1 = self._canvases[i]
            c2 = self._canvases[i + 1]
            name1 = self._well_names[i]
            name2 = self._well_names[i + 1]
            ivs1 = self._collect_intervals(c1)
            ivs2 = self._collect_intervals(c2)
            # Match by name
            names1 = {iv.name: iv for iv in ivs1}
            names2 = {iv.name: iv for iv in ivs2}
            common = set(names1.keys()) & set(names2.keys())
            for iv_name in common:
                iv1 = names1[iv_name]
                iv2 = names2[iv_name]
                link = CorrelationLink(
                    source_well=name1, target_well=name2,
                    source_interval_id=f"{iv1.top}_{iv1.bottom}_{iv1.name}",
                    target_interval_id=f"{iv2.top}_{iv2.bottom}_{iv2.name}",
                    color="#f59e0b",
                )
                links.append(link)
        self._overlay.set_links(links)

    def _collect_intervals(self, canvas: WellLogCanvas) -> list[IntervalItem]:
        """Collect all IntervalItem objects from a canvas's tracks."""
        from .renderer.interval_track import IntervalTrack
        intervals = []
        for track in canvas.tracks:
            if isinstance(track, IntervalTrack):
                intervals.extend(track._intervals)
        return intervals

    def toggle_manual_link(self):
        """Toggle manual linking mode."""
        self._manual_link_active = not self._manual_link_active
        self._manual_link_picks.clear()

    def _finish_manual_link(self):
        """Complete a manual link from collected picks."""
        if len(self._manual_link_picks) < 2:
            return
        w1, iv1 = self._manual_link_picks[0]
        w2, iv2 = self._manual_link_picks[1]
        link = CorrelationLink(
            source_well=w1, target_well=w2,
            source_interval_id=f"{iv1.top}_{iv1.bottom}_{iv1.name}",
            target_interval_id=f"{iv2.top}_{iv2.bottom}_{iv2.name}",
            color="#ef4444", is_manual=True,
        )
        links = self._overlay._links + [link]
        self._overlay.set_links(links)
        self._manual_link_active = False
        self._manual_link_picks.clear()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: All tests pass (including previous tests)

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py tests/test_cross_well_widget.py
git commit -m "feat(well-log): add auto-link and manual link to CrossWellWidget"
```

---

### Task 5: Depth Ruler and Crosshair

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`
- Test: `tests/test_cross_well_widget.py`

Integrate the shared `DepthRuler` and cross-well crosshair.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cross_well_widget.py`:

```python
def test_depth_ruler_updates_on_add(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [IntervalItem(top=0, bottom=100, name="A")])
    widget.add_canvas(c1, "well1")
    assert widget._depth_ruler._depth_top == 0
    assert widget._depth_ruler._depth_bottom == 100


def test_crosshair_syncs_across_canvases(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [])
    c2 = _make_well_canvas("well2", [])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    # Each canvas should have its own crosshair overlay
    assert c1.crosshair is not None
    assert c2.crosshair is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_widget.py -v -k "depth_ruler or crosshair"`
Expected: FAIL

- [ ] **Step 3: Write implementation**

In `CrossWellWidget.add_canvas`, after adding the canvas, set up crosshair:

```python
    def add_canvas(self, canvas: WellLogCanvas, well_name: str):
        self._canvases.append(canvas)
        self._well_names.append(well_name)
        idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(idx, canvas)
        self._sync_manager.add_canvas(canvas)
        canvas.setMouseTracking(True)
        # Set up crosshair overlay per canvas
        from .renderer.overlay import CrosshairOverlay
        overlay = CrosshairOverlay(canvas)
        canvas.crosshair = overlay
        # Update depth ruler from first canvas's tracks
        if canvas.tracks:
            t = canvas.tracks[0]
            self._depth_ruler.set_depth_range(t.depth_top, t.depth_bottom)
        self._update_overlay_geometry()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py
git commit -m "feat(well-log): integrate DepthRuler and per-canvas CrosshairOverlay"
```

---

### Task 6: Composite Vector Export

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`
- Test: `tests/test_cross_well_widget.py`

Export all canvases + correlation polygons into a single SVG/PDF/PNG.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cross_well_widget.py`:

```python
import tempfile, os
from PySide6.QtGui import QImage


def test_export_composite_svg_no_crash(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [IntervalItem(top=0, bottom=100, name="A")])
    c2 = _make_well_canvas("well2", [IntervalItem(top=0, bottom=100, name="A")])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.auto_link()
    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        path = f.name
    try:
        widget.export_composite(path, fmt="svg")
        assert os.path.exists(path)
        assert os.path.getsize(path) > 0
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_widget.py -v -k "export_composite"`
Expected: FAIL — `export_composite` doesn't exist

- [ ] **Step 3: Write implementation**

Add to `cross_well_widget.py`:

```python
import os
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter as QPaintEngine
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtPrintSupport import QPrinter
from PySide6.QtGui import QImage


def export_composite(self, path: str, fmt: str = "svg"):
    """Export all canvases + correlation polygons as a single file."""
    if not self._canvases:
        return

    # Compute total dimensions
    total_w = sum(c.width() for c in self._canvases) + \
              150 * (len(self._canvases) - 1)  # spacing
    total_h = max(c.height() for c in self._canvases)

    if fmt == "svg":
        self._export_svg(path, total_w, total_h)
    elif fmt == "pdf":
        self._export_pdf(path, total_w, total_h)
    elif fmt == "png":
        self._export_png(path, total_w, total_h)

def _export_svg(self, path: str, w: int, h: int):
    gen = QSvgGenerator()
    gen.setFileName(path)
    gen.setSize(QSizeF(w, h))
    gen.setViewBox(QRectF(0, 0, w, h))
    painter = QPaintEngine(gen)
    self._paint_composite(painter, w, h)
    painter.end()

def _export_pdf(self, path: str, w: int, h: int):
    printer = QPrinter(QPrinter.PrinterFormat.HighResolution)
    printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(path)
    # Size page to match aspect ratio
    mm_w = w * 25.4 / 96  # px to mm at 96dpi
    mm_h = h * 25.4 / 96
    printer.setPageSizeMM(QSizeF(mm_w, mm_h))
    painter = QPaintEngine(printer)
    self._paint_composite(painter, w, h)
    painter.end()

def _export_png(self, path: str, w: int, h: int):
    img = QImage(w, h, QImage.Format.Format_ARGB32)
    img.fill(0xFFFFFFFF)
    painter = QPaintEngine(img)
    self._paint_composite(painter, w, h)
    painter.end()
    img.save(path)

def _paint_composite(self, painter, total_w: int, total_h: int):
    """Paint all canvases at computed x-offsets, then overlay polygons."""
    spacing = 150
    x_off = 0
    canvas_offsets = {}
    for canvas in self._canvases:
        painter.save()
        painter.translate(x_off, 0)
        canvas.paint_all(painter)
        painter.restore()
        canvas_offsets[canvas] = (x_off, canvas.width())
        x_off += canvas.width() + spacing

    # Paint correlation polygons
    if self._overlay._links:
        self._overlay.paint_event(painter, QRectF(0, 0, total_w, total_h))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py tests/test_cross_well_widget.py
git commit -m "feat(well-log): add composite vector export for cross-well sections"
```

---

### Task 7: Well Reordering (Drag-and-Drop)

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`
- Test: `tests/test_cross_well_widget.py`

Allow drag-and-drop reordering of well canvases in the horizontal layout.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cross_well_widget.py`:

```python
def test_well_reorder_changes_order(app):
    widget = CrossWellWidget()
    c1 = _make_well_canvas("well1", [])
    c2 = _make_well_canvas("well2", [])
    c3 = _make_well_canvas("well3", [])
    widget.add_canvas(c1, "well1")
    widget.add_canvas(c2, "well2")
    widget.add_canvas(c3, "well3")
    widget.move_well(0, 2)  # Move well1 to position 2
    assert widget._well_names == ["well2", "well3", "well1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_widget.py -v -k "reorder"`
Expected: FAIL — `move_well` doesn't exist

- [ ] **Step 3: Write implementation**

Add to `cross_well_widget.py`:

```python
    def move_well(self, from_idx: int, to_idx: int):
        """Move a well canvas from one position to another."""
        if from_idx == to_idx:
            return
        canvas = self._canvases[from_idx]
        name = self._well_names[from_idx]
        # Remove from lists and layout
        self._sync_manager.remove_canvas(canvas)
        self._container_layout.removeWidget(canvas)
        self._canvases.pop(from_idx)
        self._well_names.pop(from_idx)
        # Insert at new position (before stretch)
        insert_idx = min(to_idx, len(self._canvases))
        self._canvases.insert(insert_idx, canvas)
        self._well_names.insert(insert_idx, name)
        # Re-add to layout
        layout_idx = self._container_layout.count() - 1
        self._container_layout.insertWidget(layout_idx, canvas)
        self._sync_manager.add_canvas(canvas)
        self._update_overlay_geometry()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py
git commit -m "feat(well-log): add well reordering to CrossWellWidget"
```

---

### Task 8: Per-Well Track Control

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py`

Allow toggling individual tracks on each well canvas.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_cross_well_widget.py`:

```python
def test_per_well_track_toggle(app):
    widget = CrossWellWidget()
    iv = [IntervalItem(top=0, bottom=100, name="A")]
    c1 = _make_well_canvas("well1", iv)
    initial_track_count = len(c1.tracks)
    widget.add_canvas(c1, "well1")
    # Hide the interval track
    widget.set_track_visible(c1, 1, False)
    assert len(c1.tracks) < initial_track_count or \
           any(not t.visible for t in c1.tracks if hasattr(t, 'visible'))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_widget.py -v -k "track_toggle"`
Expected: FAIL — `set_track_visible` doesn't exist

- [ ] **Step 3: Write implementation**

Add to `cross_well_widget.py`:

```python
    def set_track_visible(self, canvas: WellLogCanvas, track_index: int, visible: bool):
        """Show or hide a specific track on a canvas."""
        if 0 <= track_index < len(canvas.tracks):
            # Rebuild tracks with visibility filter
            all_tracks = canvas._coordinator._tracks
            if track_index < len(all_tracks):
                all_tracks[track_index]._visible = visible
                canvas.update()
```

Note: This assumes `BaseTrack` gets a `_visible` attribute. If not yet present, add to `track_base.py`:

```python
# In BaseTrack.__init__:
self._visible = True
```

And in `WellLogCanvas.paint_all`, skip invisible tracks:

```python
# In paint_all, after computing scaled offsets:
visible_tracks = [(i, t) for i, t in enumerate(self.tracks) if getattr(t, '_visible', True)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_widget.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/cross_well_widget.py packages/geoviz_well_log/geoviz_well_log/renderer/track_base.py
git commit -m "feat(well-log): add per-well track visibility control"
```

---

### Task 9: Update Package Exports and Thin Wrapper

**Files:**
- Modify: `packages/geoviz_well_log/geoviz_well_log/__init__.py`
- Modify: `src/pages/cross_well/page.py`

Wire up the new cross-well widget as a thin wrapper in the app.

- [ ] **Step 1: Update package exports**

In `packages/geoviz_well_log/geoviz_well_log/__init__.py`, add:

```python
from .cross_well_widget import CrossWellWidget
from .painter_sync_manager import QPainterSyncManager

# Add to __all__:
    "CrossWellWidget",
    "QPainterSyncManager",
```

- [ ] **Step 2: Update thin wrapper**

Replace `src/pages/cross_well/page.py` with:

```python
# src/pages/cross_well/page.py
"""Thin wrapper around the QPainter cross-well widget."""
from geoviz_well_log import CrossWellWidget


class CrossWellPage(CrossWellWidget):
    """Cross-well comparison page for the main application."""
    pass
```

- [ ] **Step 3: Remove old sync_manager.py**

```bash
git rm packages/geoviz_well_log/geoviz_well_log/sync_manager.py
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/test_painter_sync_manager.py tests/test_connection_overlay_painter.py tests/test_cross_well_widget.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add packages/geoviz_well_log/geoviz_well_log/__init__.py src/pages/cross_well/page.py
git commit -m "feat(well-log): wire up CrossWellWidget as cross-well page, remove old JS sync"
```
