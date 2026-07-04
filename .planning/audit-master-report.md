# GeoViz Engine — Dead UI Audit Master Report

**Date:** 2026-06-02  
**8 agents scanned all 8 pages/modules + app shell. 138 total controls examined.**

---

## Summary

| Category | Count |
|----------|-------|
| Controls examined | 138 |
| ✅ WORKS | 78 (57%) |
| ❌ DEAD (no handler) | 28 (20%) |
| ⚠️ STUB (handler exists, does nothing) | 16 (12%) |
| 🔴 BROKEN (will crash at runtime) | 3 (2%) |
| 🟡 WARNING (works, has bugs) | 13 (9%) |

---

## 🔴 BROKEN — Will Crash at Runtime (3 items)

| Page | Control | Problem | Fix |
|------|---------|---------|-----|
| Plots | SVG Export button | `NameError: QSvgGenerator` and `QPainter` not imported | Add `from PySide6.QtSvg import QSvgGenerator` and `from PySide6.QtGui import QPainter` |
| Plots | PDF Export button | Same `NameError: QPainter` | Same fix |
| PaleoMap | "显示井位标定" / "显示沉积相标注" toggles | `AttributeError: self.map_view.layers` doesn't exist | Add `layers` property to `PaleoMapCanvas`; add `visible` attr to `PaleoLayer` |

---

## ❌ DEAD — No Handler Connected (28 items)

### Header Tool Buttons (all 20, across 8 pages)
Every `HeaderToolButton` is created in `app.py:475` with styling + icon but **never connected to `clicked`**. They are purely decorative icons.

| Page | Dead Buttons |
|------|-------------|
| Map | `layers`, `ruler`, `settings` |
| PaleoMap | `layers`, `palette`, `export` |
| WellLog | `seg:测井图,数据` (SegmentedControl), `layers` |
| CrossWell | `undo`, `redo`, `export` |
| Seismic | `grid3d`, `palette`, `settings` |
| Plots | `contour`, `palette`, `export` |
| Data | `filter`, `upload` |
| Tools | `settings` |

**Fix**: In `_update_header_and_footer()`, after creating each `HeaderToolButton(t)`, connect `.clicked` to a dispatch method on the active page, or remove buttons that have no backend support.

### MapPage (6 items)
| Control | Fix |
|---------|-----|
| Chips "全部 46" / "已解释 31" / "含气 12" | Connect `toggled` to filter well list by data status |
| Checkbox "井位标记" | Add `visible` property to `WellsLayer`; connect `stateChanged` |
| Checkbox "坐标网格" | Add `visible` property to `GraticuleLayer`; connect `stateChanged` |
| Ruler button "📏" | Implement or remove |

### WellLogPage (2 items)
| Control | Fix |
|---------|-----|
| "综合柱状" button | Either remove or implement column-vs-overlay rendering mode |
| "曲线叠合" button | Same as above |

### DataPage (3 items)
| Control | Fix |
|---------|-----|
| "导入数据" button | Connect to file dialog handler |
| "重命名" button | Wire to `QInputDialog` + cache mutation |
| "删除" button | Wire to confirmation dialog + cache mutation |

### CrossWellPage (1 item)
| Control | Fix |
|---------|-----|
| Worker progress signal | Add `self._worker.progress.connect(self._on_worker_progress)` |

### App Shell (1 item)
| Control | Fix |
|---------|-----|
| `lang_label` "中文" | Remove globe icon or add language toggle handler |

---

## ⚠️ STUB — Handler Exists, Does Nothing (16 items)

### DataPage (3 items)
| Control | Issue | Fix |
|---------|-------|-----|
| 导入 Excel | Opens file dialog then `pass` | Wire to `load_well_log_from_excel` |
| 导入 LAS | Opens file dialog then `pass` | Wire to LAS loader |
| 导入 SEGY | Opens file dialog then `pass` | Wire to SEGY loader |

### ToolsPage (5 items)
| Dialog | Issue | Fix |
|--------|-------|-----|
| LASCurveResamplerDialog | "执行降采样" only calls `self.accept()` — closes dialog | Override to load LAS, resample, show results |
| DeviationTVDDialog | `_compute_min_curvature()` is `pass`, never called | Implement minimum curvature algorithm |
| XMLCoordsConverterDialog | "批量转换" only calls `self.accept()` | Add pyproj-based conversion logic |
| TopsCompletionDialog | "执行插值" only calls `self.accept()` | Add interpolation logic |
| CalamineCompilerDialog | **Never instantiated** — no 7th card slot | Add 7th card or remove class |

### SettingsPage (2 items)
| Control | Issue | Fix |
|---------|-------|-----|
| theme_combo | Emits `theme_changed` — zero listeners anywhere | Add listener in MainWindow to swap QSS stylesheet |
| clear_cache_btn | Emits `cache_cleared` — zero listeners | Connect to `DataCache.invalidate()` + refresh DataPage |

### PaleoMapPage (3 items)
| Control | Issue | Fix |
|---------|-------|-----|
| Fit button | Resets zoom to 1.0 instead of fitting data bounds | Call `self.map_view.fit_viewport_to_data()` |
| coordinate_format subscription | Repaint does nothing — no layer reads format | Wire `ScaleBarLayer` or remove |
| selection_changed handler | Body is `pass` | Implement or remove |

### CrossWellPage (3 items)
| Control | Issue | Fix |
|---------|-------|-----|
| TWT domain toggle | Axis never renders — no checkshot loading UI | Add "Load Checkshot" button |
| CrossWellScenePage | Entire class is orphan — never instantiated | Wire in or delete |
| SeismicTie.load_csv / move_pick / save_picks / remove_canvas | Public API never called | Wire to UI or remove from exports |

---

## 🟡 WARNING — Works But Has Bugs (13 items)

| Page | Issue | Fix |
|------|-------|-----|
| WellLog | Orphaned QThread on rapid well switching | Quit+wait old `_load_thread` before reassigning |
| WellLog | Orphaned QThread on rapid AI prediction | Same for `_thread` in `_run_ai_prediction()` |
| WellLog | Track drag-drop reorder is cosmetic-only | Build visible tracks list from list widget order |
| WellLog | `_tracks_btn` checked state desync with panel | Set `_tracks_btn.setChecked(True)` when panel shown programmatically |
| WellLog | `_on_prediction_error` doesn't re-enable combo | Add `self._well_combo.setEnabled(True)` |
| WellLog | `laolong1_config` unpacked but never used | Remove dead variable |
| Plots | Power slider enabled for non-IDW method on startup | Disable slider when default method is SciPy Linear |
| Plots | 9 unused imports | Clean up |
| Map | `well_hovered` signal emitted but never connected | Connect to status bar or sidebar highlight |
| CrossWell | TWT domain toggle label changes but axis is blank | See STUB section |
| App | Settings `coordinate_format_changed` only reaches PaleoMap | Connect MapPage too |
| App | `status_dot` always green | Wire to real health signal or remove |
| App | `version_label` hardcoded "v0.8.0" | Read from package `__version__` |

---

## What Works Well

These pages have solid, fully-functional controls:

- **SeismicPage/SeismicView**: All 20+ toolbar controls work correctly (SEGY load, demo, horizon, colormaps, opacity, picking, annotation, well-tie, RGB fusion, crossplot, export). Only issue is the 3 decorative header tool buttons.
- **CrossWellPage core**: Pick/Link/Browse modes, DTW propagation, auto-link, tops import/export, undo/redo, keyboard shortcuts, context menus, SVG export — all functional.
- **PlotsPage interpolation**: Method/power/resolution/colormap/step/mask controls all trigger real async interpolation via QThread.

---

## Priority Action Plan

### Phase 22a (Critical — fix broken + dead)
1. Fix PlotsPage SVG/PDF export imports (2 lines)
2. Fix PaleoMapPage layer toggles (add `layers` property + `visible` attr)
3. Connect or remove all 20 HeaderToolButtons
4. Wire DataPage import buttons (Excel/LAS/SEGY)
5. Wire MapPage chips + layer checkboxes
6. Wire WellLogPage 综合柱状/曲线叠合 or remove buttons

### Phase 22b (High — fix stubs)
7. Implement ToolsPage 4 dialog backends (LAS resample, TVD calc, coord convert, tops interpolate)
8. Wire SettingsPage theme + cache signals to real listeners
9. Wire DataPage rename/delete buttons to cache mutations
10. Fix PaleoMap fit button to use `fit_viewport_to_data()`
11. Add checkshot loading UI for CrossWell TWT domain

### Phase 22c (Medium — fix warnings)
12. Fix QThread leaks in WellLogPage
13. Fix WellLog track reorder to be functional, not just cosmetic
14. Fix PlotsPage power slider initial enabled state
15. Clean up unused imports + orphan code (CrossWellScenePage, CalamineCompilerDialog)
