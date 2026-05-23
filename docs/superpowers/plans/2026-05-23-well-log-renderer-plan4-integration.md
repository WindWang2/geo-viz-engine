# WellLogPage QPainter Integration — Plan 4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the QPainter renderer into WellLogPage so users can toggle between ECharts and QPainter rendering of well logs.

**Architecture:** Add a QComboBox renderer toggle in the toolbar. When QPainter is selected, create a `QScrollArea` containing `WellLogCanvas` + `ZoomPanHandler`. Both renderers share the same data loading path (`load_well`). A new `qpainter_widget.py` module wraps the canvas/scroll/zoom setup. Export routes through `qpainter_export_svg/pdf/png` when QPainter is active. Track control panel (merge/split/AI predict) stays ECharts-only and is disabled in QPainter mode.

**Tech Stack:** PySide6, geoviz_well_log QPainter renderer

---

## File Structure

```
src/pages/well_log/
├── page.py              # MODIFY: add renderer toggle, QPainter path in load_well/export
└── qpainter_widget.py   # NEW: QScrollArea + WellLogCanvas + ZoomPanHandler wrapper

tests/
└── test_qpainter_widget.py  # NEW
```

---

### Task 1: QPainterWidget wrapper — test + implement

**Files:**
- Create: `src/pages/well_log/qpainter_widget.py`
- Create: `tests/test_qpainter_widget.py`

- [ ] **Step 1: Write the test**

```python
# tests/test_qpainter_widget.py
import pytest
from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt

from geoviz_well_log import (
    WellLogCanvas, DepthTrack, CurveTrack, CurveData,
)
from src.pages.well_log.qpainter_widget import QPainterWidget


def _make_tracks():
    return [
        DepthTrack(top_depth=0, bottom_depth=100),
        CurveTrack(
            curves=[CurveData(name="GR", depth=list(range(100)),
                              values=[50.0] * 100, display_range=(0, 150))],
            label="GR (API)", width=150,
        ),
    ]


def test_widget_creates_scroll_area(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    assert isinstance(widget, QScrollArea)


def test_widget_has_canvas(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    assert isinstance(widget.canvas, WellLogCanvas)


def test_set_tracks(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    tracks = _make_tracks()
    widget.set_tracks(tracks)
    assert len(widget.canvas.tracks) == 2


def test_set_depth_range(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    widget.set_tracks(_make_tracks())
    widget.set_depth_range(10.0, 90.0)
    # First track should have updated range
    t = widget.canvas.tracks[0]
    assert t.depth_top == 10.0
    assert t.depth_bottom == 90.0


def test_reset_view(qtbot):
    widget = QPainterWidget()
    qtbot.addWidget(widget)
    widget.set_tracks(_make_tracks())
    widget.set_depth_range(10.0, 90.0)
    widget.reset_view()
    t = widget.canvas.tracks[0]
    assert t.depth_top == 0.0
    assert t.depth_bottom == 100.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_qpainter_widget.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement QPainterWidget**

```python
# src/pages/well_log/qpainter_widget.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea
from PySide6.QtGui import QMouseEvent

from geoviz_well_log import (
    WellLogCanvas, ZoomPanHandler, CrosshairOverlay,
)
from geoviz_well_log.renderer import BaseTrack


class QPainterWidget(QScrollArea):
    """Scroll area wrapping WellLogCanvas with zoom/pan and crosshair."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._full_top = 0.0
        self._full_bottom = 100.0

        self._canvas = WellLogCanvas(self)
        self._zoom_handler = ZoomPanHandler(self._canvas, self)
        self._crosshair = CrosshairOverlay()

        self.setWidget(self._canvas)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._canvas.setMouseTracking(True)
        self._canvas.installEventFilter(self)

    @property
    def canvas(self) -> WellLogCanvas:
        return self._canvas

    def set_tracks(self, tracks: list[BaseTrack]):
        self._canvas.set_tracks(tracks)
        if tracks:
            self._full_top = tracks[0].depth_top
            self._full_bottom = tracks[0].depth_bottom
            self._zoom_handler.set_full_range(self._full_top, self._full_bottom)
        self._update_canvas_size()

    def set_depth_range(self, top: float, bottom: float):
        self._canvas.set_depth_range(top, bottom)

    def reset_view(self):
        self._canvas.set_depth_range(self._full_top, self._full_bottom)

    def _update_canvas_size(self):
        w = self._canvas.total_width
        h = max(self.height(), 600)
        self._canvas.setFixedSize(w, h)

    def eventFilter(self, obj, event):
        if obj is self._canvas:
            if isinstance(event, QMouseEvent) and event.type() == event.Type.MouseMove:
                if self._canvas.tracks:
                    t = self._canvas.tracks[0]
                    if t.depth_span > 0:
                        ratio = event.position().y() / self._canvas.height()
                        depth = t.depth_top + ratio * t.depth_span
                        self._crosshair.set_cursor(depth)
                    else:
                        self._crosshair.hide()
            elif isinstance(event, QMouseEvent) and event.type() == event.Type.Leave:
                self._crosshair.hide()
        return super().eventFilter(obj, event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._crosshair.visible and self._canvas.tracks:
            from PySide6.QtGui import QPainter
            painter = QPainter(self.viewport())
            self._crosshair.paint_overlay(painter, self.viewport().rect(),
                                          self._canvas.tracks[0])
            painter.end()
```

- [ ] **Step 4: Run test**

Run: `source .venv/bin/activate && pytest tests/test_qpainter_widget.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/pages/well_log/qpainter_widget.py tests/test_qpainter_widget.py
git commit -m "feat(well-log): add QPainterWidget wrapper for QPainter renderer

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

### Task 2: Wire renderer toggle into WellLogPage

**Files:**
- Modify: `src/pages/well_log/page.py`

- [ ] **Step 1: Add renderer toggle and QPainter path**

Modify `src/pages/well_log/page.py`:

**2a. Add imports** — after the existing `from geoviz_well_log.export import export_dialog` line (line 14), add:

```python
from src.pages.well_log.qpainter_widget import QPainterWidget
```

Replace the geoviz_well_log import block (lines 9-13) with:

```python
from geoviz_well_log import (
    ChartEngine, TrackManager, PATTERN_MAP,
    build_tracks_from_data, build_ai_prediction_tracks,
    build_legacy_display_items, LEGACY_DEFAULT_ACTIVE,
    build_qpainter_tracks,
)
from geoviz_well_log.export import export_dialog
from geoviz_well_log.export_qpainter import export_svg as qpainter_export_svg
from geoviz_well_log.export_qpainter import export_pdf as qpainter_export_pdf
from geoviz_well_log.export_qpainter import export_png as qpainter_export_png
```

**2b. Add renderer combo** — in `__init__`, after the export button block (after line 198 `toolbar_layout.addWidget(self._export_btn)`), add:

```python
        toolbar_layout.addSpacing(12)

        self._renderer_combo = QComboBox()
        self._renderer_combo.setFixedHeight(28)
        self._renderer_combo.addItem("ECharts")
        self._renderer_combo.addItem("QPainter")
        self._renderer_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 0 8px; font-size: 13px; background: white;
                min-width: 100px;
            }
            QComboBox:hover { border-color: #3182ce; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)
        self._renderer_combo.currentTextChanged.connect(self._on_renderer_changed)
        toolbar_layout.addWidget(self._renderer_combo)
```

**2c. Add QPainter state** — in `__init__`, after `self._cached_metadata = {}` (line 278), add:

```python
        self._qpainter_widget: QPainterWidget | None = None
```

**2d. Add `_on_renderer_changed` method** — add after `_on_well_selected` (line 373):

```python
    def _on_renderer_changed(self, text: str):
        if not self._current_data:
            return
        if text == "QPainter":
            self._switch_to_qpainter()
        else:
            self._switch_to_echarts()

    def _switch_to_qpainter(self):
        if self._qpainter_widget:
            return
        if self._chart_widget:
            self._stack.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None

        self._qpainter_widget = QPainterWidget(self)
        tracks = build_qpainter_tracks(self._current_data)
        self._qpainter_widget.set_tracks(tracks)
        self._stack.addWidget(self._qpainter_widget)
        self._stack.setCurrentWidget(self._qpainter_widget)

        self._merge_btn.setEnabled(False)
        self._split_btn.setEnabled(False)

    def _switch_to_echarts(self):
        if self._chart_widget:
            return
        if self._qpainter_widget:
            self._stack.removeWidget(self._qpainter_widget)
            self._qpainter_widget.deleteLater()
            self._qpainter_widget = None

        self._chart_widget = ChartEngine(self)
        self._chart_widget.bridge.svg_received.connect(self._save_svg_to_disk)
        self._stack.addWidget(self._chart_widget)
        self._stack.setCurrentWidget(self._chart_widget)
        self._update_chart()

        self._merge_btn.setEnabled(True)
        self._split_btn.setEnabled(True)
```

**2e. Modify `load_well`** — in `load_well` (line 280), update the cleanup block at lines 290-293 to also clean up QPainter widget:

Replace:
```python
        if self._chart_widget:
            self._stack.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None
```

With:
```python
        if self._chart_widget:
            self._stack.removeWidget(self._chart_widget)
            self._chart_widget.deleteLater()
            self._chart_widget = None
        if self._qpainter_widget:
            self._stack.removeWidget(self._qpainter_widget)
            self._qpainter_widget.deleteLater()
            self._qpainter_widget = None
```

Also in `load_well`, after the ECharts rendering is set up (after line 305 `self._stack.setCurrentWidget(self._chart_widget)`), add renderer-aware widget selection. But keep the existing code path that creates `ChartEngine` by default. After `_update_chart()` is called at the end of `load_well`, add a check to auto-switch to QPainter if that's the active renderer:

After line 336 (`self._update_chart()`), add:

```python
        if self._renderer_combo.currentText() == "QPainter":
            self._switch_to_qpainter()
```

**2f. Modify `_on_export`** — replace the `_on_export` method (lines 441-447) with:

```python
    def _on_export(self):
        if self._qpainter_widget:
            from PySide6.QtWidgets import QFileDialog
            path, _ = QFileDialog.getSaveFileName(
                self, "导出测井图",
                f"{self._current_well}_well_log",
                "SVG 矢量 (*.svg);;PDF 矢量 (*.pdf);;PNG 位图 (*.png)",
            )
            if not path:
                return
            canvas = self._qpainter_widget.canvas
            if path.endswith(".svg"):
                qpainter_export_svg(canvas, path)
            elif path.endswith(".pdf"):
                qpainter_export_pdf(canvas, path)
            elif path.endswith(".png"):
                qpainter_export_png(canvas, path)
        elif self._chart_widget:
            export_dialog(
                self._chart_widget, parent=self,
                default_name=f"{self._current_well}_well_log",
            )
```

- [ ] **Step 2: Run full test suite**

Run: `source .venv/bin/activate && pytest --tb=short`
Expected: All existing + new tests pass.

- [ ] **Step 3: Commit**

```bash
git add src/pages/well_log/page.py
git commit -m "feat(well-log): add ECharts/QPainter renderer toggle to WellLogPage

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>"
```

---

## Out of Scope

- Removing ECharts backend (preserved for backward compatibility)
- Cross-well page migration
- Track reordering/merge/split in QPainter mode
- AI prediction in QPainter mode (uses ECharts track pool)
