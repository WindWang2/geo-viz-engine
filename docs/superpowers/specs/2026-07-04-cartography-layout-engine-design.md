# Publishing Cartography & Layout Engine — Design Spec

**Date:** 2026-07-04  
**Status:** Approved  
**Branch target:** feat/cartography-layout-engine  
**Version:** v0.16.0  

---

## 1. Problem Statement

GeoViz Engine currently supports basic figure export (saving PNGs and simple page PDF/SVG exports for individual maps). However, it lacks a dedicated interactive **Print Layout Editor** expected in professional GIS and geological software (such as ArcGIS Layout Manager or QGIS Print Layout):
1. **No Interactive Page Canvas:** Users cannot visually arrange paper layout elements (maps, title blocks, legends, scale bars, north arrows) on a WYSIWYG paper sheet.
2. **Missing Exploration Standard Title Blocks:** No built-in support for Chinese Exploration Title Blocks (《勘探管理图件图册编制规范》国标责任表) required for official industry reports.
3. **Rigid Legend Layout:** Legends cannot be customized into multi-column layouts or placed in user-defined positions.

To address these needs, we will implement the **Publishing Cartography & Layout Engine** module in `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/` and main application menu.

---

## 2. Scope

### In Scope
1. **Interactive Cartography Layout Window (`CartographyLayoutWindow`):** Dedicated PySide6 window showing real A4/A3/A2 paper canvas with zoom, pan, and grid snapping.
2. **Draggable & Resizable Layout Items (`LayoutGraphicsItem`):** 8-point resize handles and magnetic edge alignment for all paper elements.
3. **Dual Template Support:**
   - **`GB_EXPLORATION_SPEC`:** Chinese Exploration Standard layout with double border (ticks), 3-row Title Block, legend box, and north arrow.
   - **`ACADEMIC_JOURNAL`:** Academic publication layout (AAPG / AGU / Nature Geoscience single-column 85mm or double-column 170mm).
4. **Interactive Component Items:**
   - `MapGraphicsItem`: Vector map canvas with coordinate frame & tick marks.
   - `TitleBlockGraphicsItem`: Exploration title block with editable fields (map title, number, authors, scale, date).
   - `LegendGraphicsItem`: Multi-column legend box for facies patterns & symbols.
   - `NorthArrowGraphicsItem` & `ScaleBarGraphicsItem`: Vector cartographic decorations.
5. **300 DPI High-Precision Export:** Vector PDF (`QPrinter`) and SVG (`QSvgGenerator`) export.

### Out of Scope
- Multi-page atlas generation from 100+ well pages automatically in a single batch (focusing on single-page/multi-sheet layout design).

---

## 3. Architecture & Class Design

The changes reside in `packages/geoviz_paleo_map/geoviz_paleo_map/cartography/`.

```
packages/geoviz_paleo_map/geoviz_paleo_map/cartography/
├── __init__.py
├── window.py               # CartographyLayoutWindow UI & toolbar
├── scene.py                # PaperGraphicsScene (A4/A3/A2 paper & grid math)
├── items/                  # Interactive paper items
│   ├── base_item.py        # LayoutGraphicsItem (8 handles & drag logic)
│   ├── map_item.py         # MapGraphicsItem
│   ├── title_block_item.py # TitleBlockGraphicsItem
│   ├── legend_item.py      # LegendGraphicsItem
│   └── decor_items.py      # NorthArrowGraphicsItem & ScaleBarGraphicsItem
└── templates.py            # Presets: GB_EXPLORATION_SPEC & ACADEMIC_JOURNAL
```

---

## 4. Detailed Component Design

### 4.1. Paper Canvas (`PaperGraphicsScene`)

- Paper dimensions in millimeters:
  - A4: $297 \times 210\,\text{mm}$
  - A3: $420 \times 297\,\text{mm}$
  - A2: $594 \times 420\,\text{mm}$
- Supports Portrait and Landscape orientations.
- Renders page margin boundary lines and optional 5mm / 10mm magnetic snapping grid.

### 4.2. Chinese Exploration Standard Title Block (`TitleBlockGraphicsItem`)

Standard 3-column table placed at paper bottom right:
- Column 1: Organization Name & Project Title.
- Column 2: Map Title, Map Number, Scale ($1:N$).
- Column 3: Signatures (Drawn by, Checked by, Approved by, Date).

### 4.3. High-Precision Vector Export Engine

1. **PDF Export (`QPrinter`)**:
   ```python
   printer = QPrinter(QPrinter.PrinterMode.HighResolution)
   printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
   printer.setPageSize(QPageSize(QPageSize.PageSizeId.A3))
   printer.setOutputFileName("map_export.pdf")
   painter = QPainter(printer)
   scene.render(painter)
   painter.end()
   ```

2. **SVG Export (`QSvgGenerator`)**:
   ```python
   generator = QSvgGenerator()
   generator.setFileName("map_export.svg")
   generator.setResolution(300)
   painter = QPainter(generator)
   scene.render(painter)
   painter.end()
   ```

---

## 5. Performance & Testing Strategy

### Performance
- Sub-pixel float coordinate math (`QRectF`, `QPointF`) in millimeters to prevent rounding errors.
- Fast vector rendering using cached paths for 60 FPS viewport zooming.

### Testing Strategy
- Unit and integration tests in `tests/test_cartography_layout.py`:
  1. `test_paper_scene_dimensions()`: Verify paper sizes in mm/pixels.
  2. `test_title_block_rendering()`: Verify Chinese Exploration title block layout.
  3. `test_legend_item_column_wrap()`: Test multi-column legend wrapping.
  4. `test_pdf_svg_export()`: Verify PDF and SVG export without errors.
