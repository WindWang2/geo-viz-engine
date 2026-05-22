# WebEngine Black Screen Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix QWebEngineView black screen on Windows by correcting initialization order and setting Chromium compositing flags.

**Architecture:** Set `QTWEBENGINE_CHROMIUM_FLAGS` before Qt imports on Windows to disable GPU compositing. Reorder page creation in `app.py` so pyqtgraph's `GLViewWidget` grabs the GPU context before any `QWebEngineView` is instantiated. Clean up stale PyVista/VTK references.

**Tech Stack:** PySide6 6.11, pyqtgraph 0.14, QtWebEngine (Chromium)

---

## Task 1: Set Chromium flags and add diagnostics in `src/main.py`

**Files:**
- Modify: `src/main.py`

- [ ] **Step 1: Add Chromium flags before Qt imports**

Replace lines 1–69 of `src/main.py` with:

```python
import sys
import os

# Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# ---------------------------------------------------------------------------
# DLL Directory Registration for PySide6 inside PyInstaller frozen environment
# ---------------------------------------------------------------------------
if getattr(sys, 'frozen', False) and sys.platform == 'win32' and hasattr(os, 'add_dll_directory'):
    from pathlib import Path

    base_dirs = []
    if hasattr(sys, '_MEIPASS'):
        base_dirs.append(Path(sys._MEIPASS))
    else:
        print("DEBUG: sys._MEIPASS is NOT set!", file=sys.stderr)

    exe_dir = Path(sys.executable).parent
    base_dirs.append(exe_dir)
    base_dirs.append(exe_dir / "_internal")

    print(f"DEBUG: base_dirs to search: {base_dirs}", file=sys.stderr)

    for base_dir in base_dirs:
        if base_dir.exists():
            try:
                os.add_dll_directory(str(base_dir))
                print(f"DEBUG: Added DLL directory: {base_dir}", file=sys.stderr)
            except Exception as e:
                print(f"DEBUG: Failed to add DLL directory {base_dir}: {e}", file=sys.stderr)
            for sub in ["PySide6", "shiboken6"]:
                sub_dir = base_dir / sub
                if sub_dir.exists():
                    try:
                        os.add_dll_directory(str(sub_dir))
                        print(f"DEBUG: Added DLL directory: {sub_dir}", file=sys.stderr)
                    except Exception as e:
                        print(f"DEBUG: Failed to add DLL directory {sub_dir}: {e}", file=sys.stderr)

    # Also add them to PATH as a fallback
    os.environ["PATH"] = str(exe_dir / "_internal" / "PySide6") + os.pathsep + os.environ["PATH"]
    os.environ["PATH"] = str(exe_dir / "_internal" / "shiboken6") + os.pathsep + os.environ["PATH"]
    os.environ["PATH"] = str(exe_dir / "_internal") + os.pathsep + os.environ["PATH"]
    print(f"DEBUG: Final PATH starts with: {os.environ['PATH'][:200]}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Windows: Chromium GPU compositing flags (MUST be before any Qt import)
# ---------------------------------------------------------------------------
# On Windows, QWebEngineView (Chromium) and pyqtgraph.opengl (QOpenGLWidget)
# compete for the GPU context.  Setting --disable-gpu-compositing forces
# Chromium to use software compositing, avoiding the conflict while keeping
# WebGL functional for map rendering.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    _flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if "--disable-gpu-compositing" not in _flags:
        _flags += " --disable-gpu-compositing"
    os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = _flags.strip()

    # Lightweight GPU diagnostics (stderr only)
    try:
        import subprocess
        gpu_info = subprocess.run(
            ["wmic", "path", "win32_VideoController", "get", "name"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        print(f"[GeoViz] GPU: {gpu_info}", file=sys.stderr)
        print(f"[GeoViz] Chromium flags: {os.environ.get('QTWEBENGINE_CHROMIUM_FLAGS', '(none)')}", file=sys.stderr)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Critical: OpenGL + QWebEngineView coexistence on Windows
# ---------------------------------------------------------------------------
# 1. AA_ShareOpenGLContexts — allows OpenGL contexts to be shared between
#    QOpenGLWidget (pyqtgraph) and Chromium's GPU process.
# 2. QQuickWindow.setGraphicsApi(OpenGL) — forces Qt Quick RHI to OpenGL
#    (instead of Direct3D/Vulkan default on Windows).
# 3. CompatibilityProfile — includes legacy GL functions that Chromium's
#    GLES emulation layer depends on.
# ---------------------------------------------------------------------------
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

try:
    from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
    QQuickWindow.setGraphicsApi(QSGRendererInterface.GraphicsApi.OpenGL)
except ImportError:
    pass

from PySide6.QtGui import QFont, QSurfaceFormat
from src.app import MainWindow


def main():
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CompatibilityProfile)
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)

    font = QFont()
    font.setFamilies(["Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", "Segoe UI", "Arial"])
    font.setPointSize(10)
    font.setStyleStrategy(QFont.StyleStrategy.PreferMatch)
    app.setFont(font)

    app.setStyleSheet("""
        QWidget { background: #ffffff; color: #1a202c; }
        QGroupBox { border: 1px solid #cbd5e0; border-radius: 4px; margin-top: 8px; padding-top: 16px; }
        QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 4px; }
        QPushButton { background: #edf2f7; border: 1px solid #cbd5e0; border-radius: 4px; padding: 6px 16px; color: #1a202c; }
        QPushButton:hover { background: #e2e8f0; }
        QPushButton:pressed { background: #cbd5e0; }
        QTableWidget { background: #ffffff; gridline-color: #e2e8f0; border: 1px solid #e2e8f0; }
        QHeaderView::section { background: #f7fafc; border: 1px solid #e2e8f0; padding: 4px; }
        QScrollBar:vertical { background: #f7fafc; width: 10px; }
        QScrollBar::handle:vertical { background: #cbd5e0; border-radius: 5px; }
        QScrollArea { border: none; }
    """)
    app.setApplicationName("GeoViz Engine")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

Key changes from current code:
- Chromium flags block moved BEFORE all Qt imports (was after)
- Removed dead `Qt.AA_ShareOpenGLContexts` no-op expression on old line 73
- Added `--disable-gpu-compositing` flag
- Added GPU diagnostics (Windows only, stderr)
- Updated block comments to reference pyqtgraph instead of VTK/QQuickWidget

- [ ] **Step 2: Verify the file parses correctly**

Run: `source .venv/bin/activate && python -c "import ast; ast.parse(open('src/main.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/main.py
git commit -m "fix(windows): set Chromium flags before Qt imports to prevent black screen"
```

---

## Task 2: Fix page creation order in `src/app.py`

**Files:**
- Modify: `src/app.py`

- [ ] **Step 1: Rewrite `_build_ui` method with correct initialization order**

Replace the entire `_build_ui` method (lines 73–158 of `src/app.py`) with:

```python
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(140)
        self.sidebar.setStyleSheet("background: #f7fafc; border-right: 1px solid #e2e8f0;")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(6)

        self.sidebar_buttons: list[SidebarButton] = []
        for i, (key, icon, tooltip) in enumerate(PAGES):
            btn = SidebarButton(icon, tooltip, key)
            btn.clicked.connect(lambda _checked=False, idx=i: self._switch_page(idx))
            self.sidebar_buttons.append(btn)
            sidebar_layout.addWidget(btn)

        self.sidebar_buttons[0].setChecked(True)
        sidebar_layout.addStretch()
        root.addWidget(self.sidebar)

        # Page stack
        self.stack = QStackedWidget()

        # Lazy-import pages.
        # IMPORTANT: SeismicPage (pyqtgraph QOpenGLWidget) must be created
        # BEFORE any QWebEngineView pages so pyqtgraph grabs the GPU context
        # first.  Chromium can then fall back to software compositing.
        try:
            from src.pages.seismic import SeismicPage
            self.seismic_page = SeismicPage()
            seismic_widget = self.seismic_page
        except Exception:
            seismic_widget = QLabel("地震3D (placeholder)")
            seismic_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            seismic_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")

        try:
            from src.pages.map import MapPage
            self.map_page = MapPage(self.cache, well_click_callback=self._on_well_clicked)
        except ImportError:
            self.map_page = None
        except Exception:
            self.map_page = None

        map_widget = self.map_page if self.map_page else QLabel("地图总览 (WebEngine unavailable)")

        try:
            from src.pages.paleo_map import PaleoMapPage
            self.paleo_map_page = PaleoMapPage()
            paleo_map_widget = self.paleo_map_page
        except Exception as e:
            paleo_map_widget = QLabel(f"古地理图 (unavailable: {e})")
            paleo_map_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            paleo_map_widget.setStyleSheet("font-size: 24px; color: #a0aec0;")

        from src.pages.well_log import WellLogPage
        self.well_log_page = WellLogPage()

        from src.pages.cross_well import CrossWellPage
        self.cross_well_page = CrossWellPage()

        from src.pages.data import DataPage
        self.data_page = DataPage(self.cache)

        from src.pages.tools import ToolsPage
        self.tools_page = ToolsPage()

        page_widgets = [
            map_widget,                            # map
            paleo_map_widget,                      # paleo map
            self.well_log_page,                   # well log
            self.cross_well_page,                # cross well
            seismic_widget,                       # seismic
            self.data_page,                      # data
            self.tools_page,                     # tools
        ]
        for pw in page_widgets:
            if isinstance(pw, QLabel):
                pw.setAlignment(Qt.AlignmentFlag.AlignCenter)
                pw.setStyleSheet("font-size: 24px; color: #a0aec0;")
            self.stack.addWidget(pw)
        root.addWidget(self.stack, 1)
```

Key changes:
- `SeismicPage` created first (was fourth)
- `MapPage` and `PaleoMapPage` created second and third (were fifth and sixth)
- `WellLogPage` and `CrossWellPage` created fourth and fifth (were first and second)
- Comment updated: "SeismicPage (VTK)" → "SeismicPage (pyqtgraph QOpenGLWidget)"

- [ ] **Step 2: Verify the file parses correctly**

Run: `source .venv/bin/activate && python -c "import ast; ast.parse(open('src/app.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/app.py
git commit -m "fix(windows): create seismic page before WebEngine pages to fix GPU context order"
```

---

## Task 3: Remove stale PyVista/VTK dependencies

**Files:**
- Modify: `pyproject.toml` (line 9)
- Modify: `packages/geoviz_seismic/pyproject.toml` (line 19)

- [ ] **Step 1: Remove `pyvista` from root `pyproject.toml`**

In `pyproject.toml`, delete the line:
```
    "pyvista>=0.43",
```

(Originally line 9.)

- [ ] **Step 2: Remove `pyvista` from seismic package `pyproject.toml`**

In `packages/geoviz_seismic/pyproject.toml`, delete the line:
```
    "pyvista>=0.43",
```

(Originally line 19.)

- [ ] **Step 3: Verify both files parse correctly**

Run:
```bash
source .venv/bin/activate && python -c "
from tomllib import loads
loads(open('pyproject.toml', 'rb').read())
loads(open('packages/geoviz_seismic/pyproject.toml', 'rb').read())
print('OK')
"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml packages/geoviz_seismic/pyproject.toml
git commit -m "chore: remove stale pyvista dependencies (seismic uses pyqtgraph)"
```

---

## Task 4: Update stale VTK/PyVista references in code

**Files:**
- Modify: `packages/geoviz_seismic/geoviz_seismic/__init__.py`
- Modify: `scripts/build.py`

- [ ] **Step 1: Update seismic package docstring**

In `packages/geoviz_seismic/geoviz_seismic/__init__.py`, replace the docstring (lines 1–6):

```python
"""geoviz-seismic — 3D seismic volume visualization + 2D profile display for PySide6.

Independent package providing SEGY loading, pyqtgraph OpenGL 3D rendering,
VD heatmap / Wiggle trace 2D profiles, horizon parsing, and LRU slice caching.
Optional CuPy GPU acceleration for volume slicing and colormapping.
Works in any PySide6 project: ``pip install geoviz-seismic``.
"""
```

- [ ] **Step 2: Remove stale hidden imports from `scripts/build.py`**

In `scripts/build.py`, delete these two lines (originally lines 46–47):
```python
        "--hidden-import", "pyvistaqt",
        "--hidden-import", "vtkmodules",
```

- [ ] **Step 3: Verify files parse correctly**

Run:
```bash
source .venv/bin/activate && python -c "import ast; ast.parse(open('scripts/build.py').read()); print('OK')"
```
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add packages/geoviz_seismic/geoviz_seismic/__init__.py scripts/build.py
git commit -m "chore: update stale VTK/PyVista references to pyqtgraph + CuPy"
```

---

## Task 5: Update `CLAUDE.md` architecture description

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update architecture references**

In `CLAUDE.md`, make these replacements (use `replace_all` where noted):

1. Replace `PyVista + VTK` with `pyqtgraph OpenGL + CuPy` (in the architecture tree, `SeismicPage` line)

2. Replace the `geoviz-seismic` package description block:
```
│   └── geoviz-seismic/    → Independent PyVista-based seismic visualization engine
│       ├── renderer_3d.py       → Renderer3D (PyVista Qt + interactive slice planes)
│       ├── seismic_view.py      → SeismicView (3D + 2D profile + toolbar)
│       ├── loader.py            → SeismicLoader (segyio on-demand slicing)
│       ├── profile_vd.py        → VD heatmap profile rendering
│       ├── profile_wiggle.py    → Wiggle trace rendering (VisPy fallback)
│       ├── profile_widget.py    → Unified VD/Wiggle switcher
│       ├── horizon.py           → HorizonParser (nearest/RBF fill)
│       ├── colormap.py          → ColormapManager (seismic/gray/jet/hsv)
│       ├── cache.py             → SeismicCache (LRU slice cache)
│       └── models.py            → SeismicVolumeMeta, SliceInfo, HorizonData
```
with:
```
│   └── geoviz-seismic/    → Independent pyqtgraph-based seismic visualization engine
│       ├── renderer_3d.py       → Renderer3D (pyqtgraph GLViewWidget + interactive slice planes)
│       ├── seismic_view.py      → SeismicView (3D + 2D profile + toolbar)
│       ├── loader.py            → SeismicLoader (segyio on-demand slicing)
│       ├── gpu_ops.py           → CuPy GPU acceleration (optional, NumPy fallback)
│       ├── profile_vd.py        → VD heatmap profile rendering (QPainter)
│       ├── profile_wiggle.py    → Wiggle trace rendering (QPainter)
│       ├── profile_widget.py    → Unified VD/Wiggle switcher
│       ├── horizon.py           → HorizonParser (nearest/RBF fill)
│       ├── colormap.py          → ColormapManager (seismic/gray/jet/hsv)
│       ├── cache.py             → SeismicCache (LRU slice cache)
│       └── models.py            → SeismicVolumeMeta, SliceInfo, HorizonData
```

3. In the Key Code Patterns section, update the seismic rendering bullet:
```
- **Seismic rendering**: `SeismicView` (in `geoviz-seismic` package) combines `Renderer3D` (PyVista 3D volume + interactive slice planes) with `ProfileWidget` (VD heatmap / Wiggle trace) and toolbar. `SeismicPage` is a thin wrapper (~5 lines) inheriting `SeismicView`. Data transposed from segyio convention `(n_traces, n_samples)` to display convention `(n_samples, n_traces)` before rendering.
```
→
```
- **Seismic rendering**: `SeismicView` (in `geoviz-seismic` package) combines `Renderer3D` (pyqtgraph GLViewWidget 3D volume + interactive slice planes) with `ProfileWidget` (VD heatmap / Wiggle trace) and toolbar. `SeismicPage` is a thin wrapper (~5 lines) inheriting `SeismicView`. Data transposed from segyio convention `(n_traces, n_samples)` to display convention `(n_samples, n_traces)` before rendering. Optional CuPy GPU acceleration for volume slicing and colormapping.
```

4. Update the `geoviz_seismic/` file listing under Project Layout:
```
- `packages/geoviz_seismic/` — Independent seismic visualization package
  - `geoviz_seismic/renderer_3d.py` — Renderer3D (PyVista 3D + slice planes)
```
→
```
- `packages/geoviz_seismic/` — Independent seismic visualization package
  - `geoviz_seismic/renderer_3d.py` — Renderer3D (pyqtgraph OpenGL 3D + slice planes)
  - `geoviz_seismic/gpu_ops.py` — CuPy GPU acceleration (optional, NumPy fallback)
```

5. Update the standalone usage note:
```
- **Seismic package can be used standalone**: `from geoviz_seismic import SeismicView, SeismicLoader, Renderer3D` works without the main app. `pyvistaqt` is optional — `Renderer3D` shows a fallback `QLabel` when unavailable.
```
→
```
- **Seismic package can be used standalone**: `from geoviz_seismic import SeismicView, SeismicLoader, Renderer3D` works without the main app. Optional CuPy acceleration for GPU-accelerated volume slicing.
```

6. Update Development Notes:
```
- **PyVista offscreen**: On headless CI, set `PYVISTA_OFFSCREEN=true`. For local dev, PyVista uses Qt interactor directly.
```
→
```
- **pyqtgraph OpenGL**: Uses `pyqtgraph.opengl.GLViewWidget` (inherits `QOpenGLWidget`) for 3D seismic rendering. Must be initialized before any `QWebEngineView` on Windows to avoid GPU context conflicts.
```

7. In the architecture summary section, update:
```
- **Independent Package**: `geoviz-seismic` is a fully decoupled seismic visualization engine. It contains 3D volume rendering (`Renderer3D`), SEGY loading (`SeismicLoader`), 2D profile display (`ProfileVD`/`ProfileWiggle`), horizon parsing (`HorizonParser`), and composite widget (`SeismicView`). It can be `pip install`-ed and used in any PySide6 project.
```
No change needed — this description is already accurate (doesn't mention PyVista).

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md seismic architecture from PyVista to pyqtgraph + CuPy"
```

---

## Task 6: Run tests and verify

- [ ] **Step 1: Run existing test suite**

Run: `source .venv/bin/activate && pytest -v`
Expected: All existing tests pass.

- [ ] **Step 2: Verify app starts on current platform**

Run: `source .venv/bin/activate && timeout 5 python -m src.main 2>&1 || true`
Expected: App window appears briefly (or times out on headless CI). No Python import errors. On Linux, check stderr for `[GeoViz]` messages (should NOT appear — diagnostics are Windows-only).

- [ ] **Step 3: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: address test failures from black screen fix"
```
(Only if changes are needed.)
