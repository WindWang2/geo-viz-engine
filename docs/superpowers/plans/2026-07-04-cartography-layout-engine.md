# Publishing Cartography & Layout Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an interactive WYSIWYG Cartography Layout Window with dual template support (Chinese Exploration Standard `GB_EXPLORATION_SPEC` & Academic Journal `ACADEMIC_JOURNAL`), 8-point resize handles, magnetic snapping, and 300 DPI vector PDF/SVG export.

**Architecture:**
- Create `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/` package.
- Implement `PaperGraphicsScene` (A4/A3/A2 paper dimensions, margin boundaries, grid snapping).
- Implement interactive items: `LayoutGraphicsItem`, `MapGraphicsItem`, `TitleBlockGraphicsItem`, `LegendGraphicsItem`, `NorthArrowItem`, `ScaleBarItem`.
- Implement `CartographyLayoutWindow` with template selector, property inspector sidebar, and PDF/SVG export triggers.
- Create `tests/test_cartography_layout.py` for full automated test validation.

**Tech Stack:** PySide6 (Qt Graphics View framework), PySide6.QtSvg, PySide6.QtPrintSupport, NumPy, pytest + pytest-qt.

**Spec:** `docs/superpowers/specs/2026-07-04-cartography-layout-engine-design.md`

---

## File Structure

| File | Responsibility |
|------|---------------|
| `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/scene.py` | Paper canvas scene managing paper sizes, margins, and snapping guides |
| `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/base_item.py` | Base `LayoutGraphicsItem` with 8 resize handles and selection feedback |
| `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/title_block_item.py` | Chinese Exploration standard 3-column title block |
| `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/legend_item.py` | Multi-column legend item for facies patterns and symbols |
| `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/window.py` | CartographyLayoutWindow UI with Property Inspector & Export actions |
| `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/templates.py` | Preset templates (`GB_EXPLORATION_SPEC` and `ACADEMIC_JOURNAL`) |
| `tests/test_cartography_layout.py` | Automated unit and integration tests |

---

## Tasks

### Task 1: Paper Canvas Scene & Layout Items Base

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/scene.py`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/base_item.py`

- [ ] **Step 1: Write unit test for `PaperGraphicsScene`**
  - Verify paper dimensions for A4, A3, and A2 in portrait and landscape modes.

- [ ] **Step 2: Implement `PaperGraphicsScene` & `LayoutGraphicsItem`**
  - Implement paper background rect, printable margin bounds, and magnetic snap guidelines.
  - Implement 8-point resize handles in `LayoutGraphicsItem`.

---

### Task 2: Standard Title Block & Multi-Column Legend Items

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/title_block_item.py`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/items/legend_item.py`

- [ ] **Step 1: Write unit test for Title Block and Legend Item**
  - Verify Chinese Exploration title block text positioning and grid formatting.
  - Verify multi-column legend wrapping calculation.

- [ ] **Step 2: Implement `TitleBlockGraphicsItem` & `LegendGraphicsItem`**
  - Draw 3-column exploration title block with editable fields.
  - Implement multi-column legend box supporting pattern swatches.

---

### Task 3: Templates & Cartography Layout Window UI

**Files:**
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/templates.py`
- Create: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/window.py`

- [ ] **Step 1: Write unit test for template presets**
  - Test `GB_EXPLORATION_SPEC` and `ACADEMIC_JOURNAL` template items generation.

- [ ] **Step 2: Implement `CartographyLayoutWindow`**
  - Build window with paper view in center, Property Inspector sidebar on right, and template dropdown in toolbar.

---

### Task 4: 300 DPI Vector PDF & SVG Export Pipeline

**Files:**
- Modify: `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/window.py`

- [ ] **Step 1: Write unit test for PDF and SVG export**
  - Verify PDF generation via `QPrinter` and SVG generation via `QSvgGenerator`.

- [ ] **Step 2: Implement PDF and SVG export handlers**
  - Wire export buttons to `scene.render(painter)` with 300 DPI resolution settings.

---

### Task 5: TDD Testing & Integration

**Files:**
- Create: `tests/test_cartography_layout.py`

- [ ] **Step 1: Run full cartography test suite**
  - Command: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src:packages/geoviz_map:packages/geoviz_paleo_map:packages/geoviz_well_log:packages/geoviz_cross_well:packages/geoviz_seismic:packages/geoviz_well_tie:packages/geoviz_plots pytest tests/test_cartography_layout.py -v`
