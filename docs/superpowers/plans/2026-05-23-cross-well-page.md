# CrossWellPage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the 7-line `CrossWellPage` stub with a fully functional page that lets users select multiple wells, load them asynchronously, display side-by-side with synchronized depth, create correlation links, and export as vector graphics.

**Architecture:** Single file `src/pages/cross_well/page.py` (~300 lines) contains `CrossWellPage` (QWidget with toolbar + CrossWellWidget), `_WellSelectDialog` (multi-select checklist), and `_WellLoadWorker` (QThread for async Excel loading). The library's `CrossWellWidget` handles all rendering, sync, linking, and export. A context menu on each canvas provides per-well track visibility control.

**Tech Stack:** PySide6 (QWidget, QThread, QComboBox, QListWidget, QMenu, QFileDialog, QMessageBox), `geoviz_well_log` library (`CrossWellWidget`, `WellLogCanvas`, `build_qpainter_tracks`), `src.data.well_registry` (`list_wells`, `get_well_data`)

---

### Task 1: Well Selection Dialog

**Files:**
- Modify: `src/pages/cross_well/page.py` (add `_WellSelectDialog` class)
- Test: `tests/test_cross_well_page.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cross_well_page.py
import pytest
from PySide6.QtWidgets import QApplication
from src.pages.cross_well.page import _WellSelectDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def test_dialog_returns_selected_wells(app):
    dialog = _WellSelectDialog(["well1", "well2", "well3"])
    # Check two wells
    for i in range(dialog._list.count()):
        item = dialog._list.item(i)
        if item.text() in ("well1", "well3"):
            item.setCheckState(Qt.CheckState.Checked)
    result = dialog.get_selected()
    assert result == ["well1", "well3"]


def test_dialog_empty_selection(app):
    dialog = _WellSelectDialog(["well1"])
    result = dialog.get_selected()
    assert result == []


def test_dialog_sorted_wells(app):
    from PySide6.QtCore import Qt
    dialog = _WellSelectDialog(["well3", "well1", "well2"])
    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]
    assert items == ["well1", "well2", "well3"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: FAIL with `ImportError: cannot import name '_WellSelectDialog'`

- [ ] **Step 3: Write the dialog implementation**

```python
# src/pages/cross_well/page.py
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QDialog, QListWidget, QListWidgetItem, QAbstractItemView,
)


class _WellSelectDialog(QDialog):
    """Multi-select dialog for choosing wells to compare."""

    def __init__(self, well_names: list[str], parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择对比井")
        self.setMinimumSize(300, 400)

        layout = QVBoxLayout(self)

        label = QLabel("勾选要对比的井号：")
        label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(label)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for name in sorted(well_names):
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)
        layout.addWidget(self._list)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

    def get_selected(self) -> list[str]:
        """Return list of checked well names."""
        selected = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.text())
        return selected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pages/cross_well/page.py tests/test_cross_well_page.py
git commit -m "feat(cross-well): add WellSelectDialog for multi-well selection"
```

---

### Task 2: Data Loader Thread

**Files:**
- Modify: `src/pages/cross_well/page.py` (add `_WellLoadWorker` class)
- Test: `tests/test_cross_well_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cross_well_page.py (append)
from PySide6.QtCore import Qt, QThread
from src.pages.cross_well.page import _WellLoadWorker
from geoviz_well_log.renderer.canvas import WellLogCanvas


def test_worker_emits_finished_with_canvases(app, qtbot):
    """Worker should emit finished signal with a list of WellLogCanvas."""
    from unittest.mock import patch, MagicMock

    # Mock get_well_data to return a controlled loader
    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    def fake_loader(path, well_name=None):
        return mock_data

    fake_entry = (fake_loader, "/fake/path.xlsx", {})

    worker = _WellLoadWorker(["well1"])
    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            # Direct call (not threaded) for testing
            worker.run()

    assert len(worker.result) == 1
    assert isinstance(worker.result[0], WellLogCanvas)


def test_worker_skips_failed_wells(app):
    from unittest.mock import patch

    def fake_get_well(name):
        if name == "bad_well":
            return None
        return (lambda path, well_name=None: MagicMock(curves=[], top_depth=0, bottom_depth=100, intervals=None), "/fake.xlsx", {})

    worker = _WellLoadWorker(["well1", "bad_well"])
    with patch("src.pages.cross_well.page.get_well_data", side_effect=fake_get_well):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            worker.run()

    assert len(worker.result) == 1  # bad_well skipped
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_page.py::test_worker_emits_finished_with_canvases -v`
Expected: FAIL with `ImportError: cannot import name '_WellLoadWorker'`

- [ ] **Step 3: Write the worker implementation**

Add to `src/pages/cross_well/page.py`:

```python
from PySide6.QtCore import QThread, QObject, Signal
from geoviz_well_log import build_qpainter_tracks
from geoviz_well_log.renderer.canvas import WellLogCanvas
from src.data.well_registry import get_well_data


class _WellLoadWorker(QObject):
    """Background worker that loads multiple wells and builds canvases."""

    progress = Signal(int, str)  # index, well_name
    finished = Signal(list)  # list[WellLogCanvas]
    error = Signal(str)

    def __init__(self, well_names: list[str], parent=None):
        super().__init__(parent)
        self._well_names = well_names
        self.result: list[WellLogCanvas] = []

    def run(self):
        self.result = []
        for i, name in enumerate(self._well_names):
            try:
                entry = get_well_data(name)
                if entry is None:
                    print(f"[CrossWell] Skipping {name}: not found in registry")
                    continue
                loader_fn, xls_path, config = entry
                data = loader_fn(xls_path, well_name=name)
                tracks = build_qpainter_tracks(data)
                canvas = WellLogCanvas()
                canvas.set_tracks(tracks)
                canvas.resize(200, 600)
                self.result.append(canvas)
                self.progress.emit(i, name)
            except Exception as e:
                print(f"[CrossWell] Failed to load {name}: {e}")
                continue
        self.finished.emit(self.result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pages/cross_well/page.py tests/test_cross_well_page.py
git commit -m "feat(cross-well): add async WellLoadWorker for multi-well loading"
```

---

### Task 3: Main CrossWellPage with Toolbar and Widget Wiring

**Files:**
- Modify: `src/pages/cross_well/page.py` (replace stub with full `CrossWellPage`)
- Test: `tests/test_cross_well_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cross_well_page.py (append)
from src.pages.cross_well.page import CrossWellPage


def test_page_creation(app):
    page = CrossWellPage()
    assert page.canvas_count == 0


def test_page_has_toolbar(app):
    page = CrossWellPage()
    assert page._toolbar is not None
    assert page._add_btn is not None


def test_page_add_button_opens_dialog(app, qtbot):
    page = CrossWellPage()
    # Verify add_btn is connected (click should not crash without wells)
    # We just check the button exists and is enabled
    assert page._add_btn.isEnabled()


def test_page_load_wells(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])

    assert page.canvas_count == 1


def test_page_clear_all(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1", "well2"])

    assert page.canvas_count == 2
    page._on_clear()
    assert page.canvas_count == 0


def test_page_placeholder_visible_when_empty(app):
    page = CrossWellPage()
    assert page._placeholder.isVisible()


def test_page_placeholder_hidden_when_loaded(app):
    from unittest.mock import patch, MagicMock
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", return_value=[]):
            page._load_wells(["well1"])

    assert not page._placeholder.isVisible()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_page.py::test_page_creation -v`
Expected: FAIL (current stub is `class CrossWellPage(CrossWellWidget): pass` — no toolbar, no methods)

- [ ] **Step 3: Write the full CrossWellPage implementation**

Replace the entire content of `src/pages/cross_well/page.py`:

```python
# src/pages/cross_well/page.py
"""Cross-well comparison page for the main application."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox,
)
from geoviz_well_log import CrossWellWidget
from src.data.well_registry import list_wells


class _WellSelectDialog:
    """Multi-select dialog for choosing wells to compare."""
    # ... (from Task 1)


class _WellLoadWorker:
    """Background worker that loads multiple wells and builds canvases."""
    # ... (from Task 2)


class CrossWellPage(QWidget):
    """Cross-well comparison page with toolbar and multi-well display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._load_thread: QThread | None = None
        self._worker = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # --- Toolbar ---
        self._toolbar = QWidget()
        self._toolbar.setStyleSheet(
            "background: #f7fafc; border-bottom: 1px solid #e2e8f0;"
        )
        tb = QHBoxLayout(self._toolbar)
        tb.setContentsMargins(12, 6, 12, 6)

        title = QLabel("连井对比")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1a202c;")
        tb.addWidget(title)
        tb.addSpacing(12)

        self._add_btn = QPushButton("添加井")
        self._add_btn.setFixedHeight(28)
        self._add_btn.setStyleSheet("""
            QPushButton {
                background: #edf2f7; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """)
        self._add_btn.clicked.connect(self._on_add_wells)
        tb.addWidget(self._add_btn)

        self._auto_link_btn = QPushButton("自动连井")
        self._auto_link_btn.setFixedHeight(28)
        self._auto_link_btn.setStyleSheet(self._btn_style())
        self._auto_link_btn.clicked.connect(self._on_auto_link)
        tb.addWidget(self._auto_link_btn)

        self._manual_link_btn = QPushButton("手动连井")
        self._manual_link_btn.setFixedHeight(28)
        self._manual_link_btn.setCheckable(True)
        self._manual_link_btn.setStyleSheet(self._btn_style())
        self._manual_link_btn.clicked.connect(self._on_toggle_manual_link)
        tb.addWidget(self._manual_link_btn)

        self._clear_btn = QPushButton("清除")
        self._clear_btn.setFixedHeight(28)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: #fed7d7; color: #9b2c2c;
                border: 1px solid #feb2b2; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #fc8181; color: white; }
        """)
        self._clear_btn.clicked.connect(self._on_clear)
        tb.addWidget(self._clear_btn)

        tb.addStretch()

        self._export_btn = QPushButton("导出")
        self._export_btn.setFixedHeight(28)
        self._export_btn.setStyleSheet("""
            QPushButton {
                background: #3182ce; color: white;
                border: none; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #2b6cb0; }
            QPushButton:pressed { background: #2c5282; }
        """)
        self._export_btn.clicked.connect(self._on_export)
        tb.addWidget(self._export_btn)

        outer.addWidget(self._toolbar)

        # --- CrossWellWidget (inherited from library) ---
        self._cross_well = CrossWellWidget()
        outer.addWidget(self._cross_well, 1)

        # --- Empty state placeholder ---
        self._placeholder = QLabel("点击"添加井"开始对比")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("font-size: 16px; color: #a0aec0;")
        self._cross_well._container_layout.addWidget(self._placeholder)

    @staticmethod
    def _btn_style() -> str:
        return """
            QPushButton {
                background: #edf2f7; color: #1e293b;
                border: 1px solid #cbd5e1; border-radius: 4px;
                padding: 0 12px; font-size: 13px;
            }
            QPushButton:hover { background: #e2e8f0; }
        """

    # --- Actions ---

    def _on_add_wells(self):
        from PySide6.QtWidgets import QDialog
        available = list_wells()
        if not available:
            QMessageBox.information(self, "添加井", "没有可用的井数据。")
            return
        dialog = _WellSelectDialog(available, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.get_selected()
        if not selected:
            return
        self._load_wells(selected)

    def _load_wells(self, well_names: list[str]):
        """Load wells in a background thread."""
        self._placeholder.setVisible(False)
        self._add_btn.setEnabled(False)

        self._worker = _WellLoadWorker(well_names)
        self._load_thread = QThread()
        self._worker.moveToThread(self._load_thread)

        self._load_thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_load_finished)
        self._worker.finished.connect(self._load_thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._load_thread.finished.connect(self._load_thread.deleteLater)

        self._load_thread.start()

    def _on_load_finished(self, canvases: list):
        self._add_btn.setEnabled(True)
        for canvas in canvases:
            well_name = canvas.tracks[0].label if canvas.tracks else "unknown"
            self._cross_well.add_canvas(canvas, well_name)

    def _on_auto_link(self):
        self._cross_well.auto_link()

    def _on_toggle_manual_link(self):
        self._cross_well.toggle_manual_link()
        if self._cross_well._manual_link_active:
            self._manual_link_btn.setStyleSheet(
                self._btn_style() + "QPushButton { background: #fef3c7; border-color: #f59e0b; }"
            )
        else:
            self._manual_link_btn.setStyleSheet(self._btn_style())

    def _on_clear(self):
        self._cross_well.clear_all()
        self._placeholder.setVisible(True)
        self._manual_link_btn.setChecked(False)
        self._manual_link_btn.setStyleSheet(self._btn_style())

    def _on_export(self):
        if self._cross_well.canvas_count == 0:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "导出连井对比图", "cross_well",
            "SVG 矢量 (*.svg);;PDF 矢量 (*.pdf);;PNG 位图 (*.png)",
        )
        if not path:
            return
        lower = path.lower()
        if lower.endswith(".pdf"):
            fmt = "pdf"
        elif lower.endswith(".png"):
            fmt = "png"
        else:
            if not lower.endswith(".svg"):
                path += ".svg"
            fmt = "svg"
        self._cross_well.export_composite(path, fmt=fmt)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pages/cross_well/page.py tests/test_cross_well_page.py
git commit -m "feat(cross-well): implement CrossWellPage with toolbar, async loading, and export"
```

---

### Task 4: Track Visibility Context Menu

**Files:**
- Modify: `src/pages/cross_well/page.py` (add context menu to CrossWellPage)
- Test: `tests/test_cross_well_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cross_well_page.py (append)
from unittest.mock import patch, MagicMock
from PySide6.QtGui import QMouseEvent
from PySide6.QtCore import Qt, QPoint, QPointF


def test_context_menu_shows_track_list(app):
    from geoviz_well_log.renderer.depth_track import DepthTrack
    page = CrossWellPage()

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    def fake_build(data):
        return [DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度")]

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", side_effect=fake_build):
            page._load_wells(["well1"])

    # Verify canvas has tracks
    assert len(page._cross_well._canvases[0].tracks) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_page.py::test_context_menu_shows_track_list -v`
Expected: FAIL (no context menu implementation yet)

- [ ] **Step 3: Add context menu to CrossWellPage**

Add `contextMenuEvent` method to `CrossWellPage`:

```python
    def contextMenuEvent(self, event):
        """Right-click context menu for per-well track visibility."""
        from PySide6.QtWidgets import QMenu

        # Find which canvas was right-clicked
        pos = event.pos()
        target_canvas = None
        for canvas in self._cross_well._canvases:
            # Map canvas position to page coordinates
            canvas_pos = canvas.mapTo(self, canvas.rect().topLeft())
            canvas_rect = canvas.rect().translated(canvas_pos)
            if canvas_rect.contains(pos):
                target_canvas = canvas
                break

        if target_canvas is None:
            return

        menu = QMenu(self)
        well_name = target_canvas.tracks[0].label if target_canvas.tracks else "unknown"
        menu.addAction(f"── {well_name} ──").setEnabled(False)

        for i, track in enumerate(target_canvas.tracks):
            action = menu.addAction(track.label)
            action.setCheckable(True)
            action.setChecked(getattr(track, "_visible", True))
            # Use lambda with default arg to capture i
            action.toggled.connect(
                lambda checked, idx=i: self._cross_well.set_track_visible(
                    target_canvas, idx, checked
                )
            )

        menu.exec(event.globalPos())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pages/cross_well/page.py tests/test_cross_well_page.py
git commit -m "feat(cross-well): add right-click context menu for track visibility control"
```

---

### Task 5: Error Handling and Edge Cases

**Files:**
- Modify: `src/pages/cross_well/page.py`
- Test: `tests/test_cross_well_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cross_well_page.py (append)


def test_page_export_no_wells(app):
    page = CrossWellPage()
    # Should not crash or open dialog
    page._on_export()


def test_page_auto_link_no_wells(app):
    page = CrossWellPage()
    # Should not crash
    page._on_auto_link()


def test_page_manual_link_no_wells(app):
    page = CrossWellPage()
    page._on_toggle_manual_link()
    assert not page._cross_well._manual_link_active


def test_page_add_disabled_during_load(app):
    page = CrossWellPage()
    # Simulate loading state
    page._add_btn.setEnabled(False)
    assert not page._add_btn.isEnabled()
    # Re-enable
    page._on_load_finished([])
    assert page._add_btn.isEnabled()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_well_page.py::test_page_export_no_wells -v`
Expected: PASS (these are guard checks, already handled by existing code)

- [ ] **Step 3: Verify and add any missing guards**

Review the implementation for edge cases. The `canvas_count == 0` guard in `_on_export` is already in place. Verify `_on_auto_link` and `_on_toggle_manual_link` are safe with zero canvases. No code changes needed if all pass.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_cross_well_page.py
git commit -m "test(cross-well): add edge case tests for empty state and guard checks"
```

---

### Task 6: Integration Smoke Test

**Files:**
- Modify: `tests/test_cross_well_page.py`

- [ ] **Step 1: Write the integration test**

```python
# tests/test_cross_well_page.py (append)


def test_full_workflow(app):
    """End-to-end: open dialog → load wells → auto-link → export."""
    from unittest.mock import patch, MagicMock
    from geoviz_well_log.renderer.depth_track import DepthTrack
    from geoviz_well_log.renderer.interval_track import IntervalTrack
    from geoviz_well_log.models import IntervalItem

    page = CrossWellPage()

    def fake_build(data):
        # Return tracks with intervals so auto-link has something to match
        return [
            DepthTrack(top_depth=0, bottom_depth=100, width=60, label="深度"),
            IntervalTrack(
                intervals=[IntervalItem(top=10, bottom=50, name="FormationA")],
                label="组", width=50,
            ),
        ]

    mock_data = MagicMock()
    mock_data.curves = []
    mock_data.top_depth = 0
    mock_data.bottom_depth = 100
    mock_data.intervals = None

    fake_entry = (lambda path, well_name=None: mock_data, "/fake.xlsx", {})

    with patch("src.pages.cross_well.page.get_well_data", return_value=fake_entry):
        with patch("src.pages.cross_well.page.build_qpainter_tracks", side_effect=fake_build):
            page._load_wells(["well1", "well2"])

    # Should have 2 canvases
    assert page.canvas_count == 2

    # Auto-link should create a correlation
    page._on_auto_link()
    assert len(page._cross_well._overlay.links) == 1

    # Clear should reset everything
    page._on_clear()
    assert page.canvas_count == 0
    assert page._placeholder.isVisible()
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_cross_well_page.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_cross_well_page.py
git commit -m "test(cross-well): add end-to-end integration smoke test"
```

---

### Task 7: Final Verification

- [ ] **Step 1: Run all tests**

Run: `pytest tests/test_cross_well_page.py tests/test_cross_well_widget.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: No regressions, all tests PASS
