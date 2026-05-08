# Cross-Well Facies Correlation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Implement a standalone "Cross-Well" tab for correlating sedimentary facies across multiple wells with smooth vertical synchronization and interactive linking.

**Architecture:** Modular assembly of existing `ChartEngine` (ECharts) instances, managed by a `SyncManager` for viewport lock-step, and a `ConnectionOverlay` for drawing inter-well correlation polygons using Qt `QPainter`.

**Tech Stack:** Python, PySide6 (Qt), ECharts (via WebEngine), Pydantic.

---

### Task 1: Navigation and Data Models

**Files:**
- Modify: `src/data/models.py`
- Modify: `src/app.py`
- Create: `src/resources/icons/cross_well.svg`

- [x] **Step 1: Define the CorrelationLink model in `src/data/models.py`**

```python
class CorrelationLink(BaseModel):
    source_well: str
    target_well: str
    source_interval_id: str  # UID of the facies interval (top_bottom_name)
    target_interval_id: str
    color: str
    is_manual: bool = False
```

- [x] **Step 2: Add sidebar icon `src/resources/icons/cross_well.svg`**

```xml
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 3v18h18"/>
  <path d="M7 14l3-3 4 4 4-4"/>
  <rect x="2" y="2" width="20" height="20" rx="2" opacity="0.1"/>
</svg>
```

- [x] **Step 3: Register the new page in `src/app.py`**

```python
# Update PAGES list
PAGES = [
    ("map", "src/resources/icons/map.svg", "地图总览"),
    ("well_log", "src/resources/icons/well_log.svg", "井剖面"),
    ("cross_well", "src/resources/icons/cross_well.svg", "连井对比"), # Add this
    ("seismic", "src/resources/icons/seismic.svg", "地震3D"),
    ("data", "src/resources/icons/data.svg", "数据管理"),
]
# ... in _build_ui ...
from src.pages.cross_well_page import CrossWellPage
self.cross_well_page = CrossWellPage()
# ... in page_widgets ...
page_widgets = [
    map_widget,
    self.well_log_page,
    self.cross_well_page, # Add this
    seismic_widget,
    self.data_page,
]
```

- [x] **Step 4: Commit**
```bash
git add src/data/models.py src/app.py src/resources/icons/cross_well.svg
git commit -m "feat(nav): add Cross-Well tab and data models"
```

---

### Task 2: Cross-Well Page Foundation

**Files:**
- Create: `src/pages/cross_well_page.py`

- [x] **Step 1: Create a basic `CrossWellPage` with well loading capabilities**

```python
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QPushButton, QLabel
from src.renderers.well_log.chart_engine import ChartEngine
from src.data.well_registry import get_well_data

class CrossWellPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        
        # Toolbar
        self.toolbar = QHBoxLayout()
        self.add_well_btn = QPushButton("添加井")
        self.toolbar.addWidget(self.add_well_btn)
        self.toolbar.addStretch()
        layout.addLayout(self.toolbar)
        
        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.well_layout = QHBoxLayout(self.container)
        self.well_layout.setSpacing(100) # Gap for connections
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        
        self.engines = []

    def add_well(self, well_name):
        engine = ChartEngine(self)
        self.engines.append(engine)
        self.well_layout.addWidget(engine)
        # Placeholder data load...
```

- [x] **Step 2: Commit**
```bash
git add src/pages/cross_well_page.py
git commit -m "feat(ui): implement basic Cross-Well page container"
```

---

### Task 3: Multi-Well Viewport Synchronization

**Files:**
- Create: `src/renderers/well_log/sync_manager.py`
- Modify: `src/pages/cross_well_page.py`

- [x] **Step 1: Implement `SyncManager` to bridge ECharts dataZoom events**

```python
from PySide6.QtCore import QObject, Slot

class SyncManager(QObject):
    def __init__(self, engines):
        super().__init__()
        self.engines = engines
        self._is_syncing = False

    def sync_range(self, source_engine, start, end):
        if self._is_syncing: return
        self._is_syncing = True
        for engine in self.engines:
            if engine != source_engine:
                engine.view.page().runJavaScript(f"window.geoviz.setRange({start}, {end});")
        self._is_syncing = False
```

- [x] **Step 2: Connect ECharts events to SyncManager in `CrossWellPage`**

- [x] **Step 3: Commit**
```bash
git add src/renderers/well_log/sync_manager.py src/pages/cross_well_page.py
git commit -m "feat(sync): implement vertical viewport synchronization"
```

---

### Task 4: Connection Overlay Rendering

**Files:**
- Create: `src/renderers/well_log/connection_overlay.py`
- Modify: `src/pages/cross_well_page.py`

- [x] **Step 1: Implement `ConnectionOverlay` with QPainter**

```python
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPolygonF, QColor
from PySide6.QtCore import QPointF

class ConnectionOverlay(QWidget):
    def __init__(self, parent, engines):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.engines = engines
        self.links = [] # List of CorrelationLink

    def paintEvent(self, event):
        painter = QPainter(self)
        # Logic to map well interval depths to widget coordinates
        # and draw polygons between adjacent engines.
```

- [x] **Step 2: Update overlay on scroll/zoom events**

- [x] **Step 3: Commit**
```bash
git add src/renderers/well_log/connection_overlay.py
git commit -m "feat(render): implement connection overlay for correlation polygons"
```

---

### Task 5: Auto-Suggest and Interaction

**Files:**
- Modify: `src/pages/cross_well_page.py`
- Modify: `src/renderers/well_log/connection_overlay.py`

- [x] **Step 1: Implement "Auto-Suggest" algorithm for facies linking**
- [x] **Step 2: Implement manual "Click to Link" mode**
- [x] **Step 3: Verify and Commit**
```bash
git add .
git commit -m "feat(correlation): add auto-suggest and manual linking interaction"
```
