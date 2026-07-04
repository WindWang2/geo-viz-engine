# Cross-Well Multi-Curve Overlay & Interactive Picking — Design Spec

**Date:** 2026-07-04  
**Status:** Approved  
**Branch target:** feat/cross-well-interactive-picking  
**Version:** v0.14.0  

---

## 1. Problem Statement

GeoViz Engine's well correlation panel (`geoviz-cross-well`) currently has basic support for displaying log curves, manual picking, and on-demand DTW auto-correlation. However, it lacks advanced interactive picking capabilities expected in professional software:
1. **No custom log curve overlay:** Curves are grouped statically matching `_MERGE_GROUPS` (e.g., AC/GR). Users cannot dynamically overlay arbitrary curves (e.g., SP and GR, or multiple resistivity logs) to customize their workflow.
2. **Missing multi-scale headers:** When curves are overlaid, only the scale range of the first curve is drawn. Display ranges of additional curves are hidden, making it difficult to read values.
3. **No feature-snapping for picking:** Picks are placed exactly where the user clicks. Professional geologists expect picks to "snap" automatically to local curve extrema (peaks, troughs, or inflection points) representing depositional/stratigraphic boundaries.
4. **No unified control panel:** Horizon management, active curve selection for snapping/DTW, and parameter configurations are scattered or hardcoded.

To address these needs, we will implement **Multi-Curve Overlay & Enhanced Picking Interaction** in the `geoviz-cross-well` package and main page.

---

## 2. Scope

### In Scope
1. **Dynamic Curve Overlay Manager:** A user interface to checklist available curves and dynamically map/merge them into single tracks or keep them separate.
2. **Multi-Scale Headers:** Draw side-by-side, color-matched scales at the top and bottom of the track for all overlaid curves to ensure value readability.
3. **Curve Feature Snapping:** Automatically adjust user-clicked depths to local maxima, local minima, or nearest values of the active curve within a vertical search window (e.g. ±1.5m).
4. **Collapsible Right Sidebar:** A sidebar panel on the right side of the canvas containing the Horizon Manager, Active Curve dropdown, Snap Mode/Radius controls, and Curve Overlay Config list.
5. **Interactive Snapping Preview:** Draw a real-time horizontal preview line and curve dot during hover to indicate where the pick will snap when clicked.
6. **DTW Integration Update:** Update the DTW engine propagation to run on the selected active curve instead of hardcoded lists.

### Out of Scope
- Automatic 3D horizon surface interpolation (staying in 2D well correlation section view).
- Cross-plot correlation between tracks (covered by plots package).
- Multi-dimensional DTW (using multiple curves simultaneously for similarity distance).

---

## 3. Architecture

The changes are distributed between the independent `geoviz-cross-well` rendering/interaction package and the `CrossWellPage` UI controller.

```
packages/geoviz_cross_well/geoviz_cross_well/
├── canvas.py             # UPDATED: Handles active picking curve, snap hover preview, and event filtering
├── correlation_layer.py  # Bezier tie lines (unchanged)
├── dtw_engine.py         # Banded DTW (unchanged)
├── picks_model.py        # Horizon pick model (unchanged)
└── tops_model.py         # Formation tops model (unchanged)

packages/geoviz_well_log/geoviz_well_log/renderer/
└── curve_track.py        # UPDATED: Implements multi-color side-by-side scale ranges in paint_content/paint_header

src/pages/cross_well/
├── page.py               # UPDATED: Integrates collapsible sidebar UI panel and dynamic track rebuilding
└── sidebar.py            # NEW: Sidebar widget managing horizons, snapping settings, and curve overlays
```

---

## 4. Detailed Design

### 4.1. Data Model & Configurations

In `CrossWellCanvas` (in `packages/geoviz_cross_well/geoviz_cross_well/canvas.py`), we add pick-state and snapping configurations:

```python
class CrossWellCanvas(QWidget):
    def __init__(self, parent=None):
        ...
        self._active_formation: str | None = None  # Active horizon name (e.g., "Horizon-1")
        self._active_curve: str = "GR"             # Curve to snap to and propagate via DTW
        self._snap_type: str = "max"               # "max" | "min" | "none" (snapping mode)
        self._snap_window_m: float = 1.5           # Vertical window size in meters
        
        # Dictionary mapping track label to list of curve names.
        # Controls which curves get merged into the same track.
        self._curve_groups: dict[str, list[str]] = {
            "AC/GR": ["AC", "GR"],
            "RT/RXO": ["RT", "RXO"]
        }
```

When rebuilding tracks for each well canvas:
1. We iterate over `self._curve_groups`.
2. For each group, we check if the well has the specified curves.
3. If so, we group them into a single `CurveTrack` instance.
4. Any remaining curves not in `self._curve_groups` are shown in their own separate tracks.

---

### 4.2. Multi-Scale Header Rendering

In `packages/geoviz_well_log/geoviz_well_log/renderer/curve_track.py`, we modify how display range labels are drawn.
If a `CurveTrack` contains $K$ curves, the track width $W$ is divided into $K$ sections:

```python
# In CurveTrack.paint_content
if self._curves:
    W = rect.width()
    K = len(self._curves)
    for i, curve in enumerate(self._curves):
        lo, hi = curve.display_range
        color = QColor(curve.color)
        font = QFont()
        font.setPixelSize(10)
        painter.setFont(font)
        painter.setPen(color)
        
        # Calculate horizontal bounds for this curve's scale labels
        x_start = rect.left() + i * (W / K)
        
        # Draw min (lo) at the top of the track content
        painter.drawText(
            QRectF(x_start, rect.top() + 2, W / K, 12),
            Qt.AlignmentFlag.AlignLeft,
            f"{lo:.1f}"
        )
        # Draw max (hi) at the bottom of the track content
        painter.drawText(
            QRectF(x_start, rect.bottom() - 14, W / K, 12),
            Qt.AlignmentFlag.AlignLeft,
            f"{hi:.1f}"
        )
```

---

### 4.3. Curve Snapping Algorithm

In `CrossWellCanvas`, we implement snapping inside the mouse-handling logic.

```python
def _get_snapped_depth(self, canvas: WellLogCanvas, clicked_depth: float) -> float:
    if self._snap_type == "none" or not self._active_curve:
        return clicked_depth

    # Extract depths and values of the active curve for the targeted well
    curve_data = self._extract_curve(canvas, preferred=(self._active_curve,))
    if curve_data is None:
        return clicked_depth

    depths, values = curve_data  # numpy arrays
    
    # Filter points within search window [clicked_depth - window, clicked_depth + window]
    mask = (depths >= clicked_depth - self._snap_window_m) & (depths <= clicked_depth + self._snap_window_m)
    window_depths = depths[mask]
    window_values = values[mask]
    
    if len(window_values) == 0:
        return clicked_depth

    # Find index of extremum
    if self._snap_type == "max":
        idx = np.argmax(window_values)
    elif self._snap_type == "min":
        idx = np.argmin(window_values)
    else:
        return clicked_depth

    return float(window_depths[idx])
```

#### Hover Snapping Feedback
* In `_PickEventFilter.eventFilter` on `MouseMove`, we call `_get_snapped_depth()` and store it as `self._hover_snapped_depth`.
* `PickingOverlay.paintEvent` will draw a thin, horizontal dashed line at `self._hover_snapped_depth` extending across the clicked well's track width, with a small highlighted dot on the active curve line.

---

### 4.4. Collapsible Sidebar UI

We introduce `src/pages/cross_well/sidebar.py` containing the `CrossWellSidebar` widget, inheriting `QWidget`.

```
┌────────────────────────────────────────────────────────┐
│ ◀ 收起                                                 │
├────────────────────────────────────────────────────────┤
│ 📂 层位管理器 (Horizon Manager)                          │
│   当前层位: [ Horizon-1                      ▾] [+] [-]│
│   层位列表:                                            │
│   - Horizon-1  (绿色 #10b981)                          │
│   - Horizon-2  (橙色 #f59e0b)                          │
├────────────────────────────────────────────────────────┤
│ 🎯 特征自动吸附 (Curve Snapping)                        │
│   敏感曲线: [ GR                             ▾]        │
│   吸附类型: ( ) 无  (●) 极大值  ( ) 极小值               │
│   搜索半径: [ 1.50 ] m                                 │
├────────────────────────────────────────────────────────┤
│ 🔗 曲线合并/叠加 (Curve Overlay Manager)                │
│   GR   ──► [ 叠加至: AC       ▾]                       │
│   AC   ──► [ 独立显示         ▾]                       │
│   RT   ──► [ 叠加至: RXO      ▾]                       │
│   RXO  ──► [ 独立显示         ▾]                       │
├────────────────────────────────────────────────────────┤
│ ⚡ DTW 一键自动对比 (Auto DTW)                           │
│   [ 运行 DTW 传播 ]                                     │
└────────────────────────────────────────────────────────┘
```

#### Rebuilding Canvases
When a dropdown selection in the "曲线合并/叠加" section changes:
1. Update `canvas._curve_groups`.
2. Emit a signal to `CrossWellPage`.
3. `CrossWellPage._rebuild_canvases()` is invoked, rebuilding all tracks according to the new `_curve_groups` dictionary.

---

## 5. Testing & Verification

1. **Unit Tests (`packages/geoviz_cross_well/tests/`)**:
   - `test_curve_snapping`: Test snapping calculations with mock curve data (peaks, troughs, and out-of-bounds clicks).
   - `test_curve_groups_rebuild`: Verify that setting `_curve_groups` updates track layout structures correctly.
2. **UI Regression Tests (`tests/test_cross_well_page_picking.py`)**:
   - Test sidebar expansion/collapse transitions.
   - Verify active curve switches correctly adjust the DTW target curve.
   - Test snapping preview rendering coordinates during simulated hover events.
