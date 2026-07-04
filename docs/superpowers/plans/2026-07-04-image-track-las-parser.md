# Implementation Plan: Single-Well Image Track & LAS File Parser (Phase 32 / v0.20.0)

## Overview
Implement **LAS 2.0/3.0 File Parser (`las_parser.py`)** and **Single-Well Image Track (`ImageTrack`)** in `geoviz-well-log` and `WellLogPage`. Features include parsing `.las` curves with NULL value cleaning, depth-scaled core photo segment mapping, continuous FMI borehole image rendering, double-click image preview modal, and 300 DPI vector PDF/SVG report exporting.

---

## Tasks & Sub-Phases

### Task 1: LAS 2.0/3.0 File Parser Module
- **Files**: `packages/geoviz_well_log/geoviz_well_log/las_parser.py`
- **Work**:
  - Implement `parse_las_file(filepath_or_content)` to parse `~V`, `~W`, `~C`, `~A` sections.
  - Clean sentinel NULL values (`-999.25`, `-9999.0` -> `np.nan`).
- **Tests**: `tests/test_las_parser.py`

### Task 2: ImageTrack & Photo Segment Renderer
- **Files**: `packages/geoviz_well_log/geoviz_well_log/tracks/image_track.py`
- **Work**:
  - Implement `ImageTrack` inheriting from `TrackBase`.
  - Support `CorePhotoSegment` (depth-proportional `QPixmap` painting) and `BoreholeImageSegment` (2D pseudocolor FMI matrix).
- **Tests**: `tests/test_image_track.py`

### Task 3: Image Preview Magnifier Modal
- **Files**: `packages/geoviz_well_log/geoviz_well_log/image_preview_dialog.py`
- **Work**:
  - Implement `ImagePreviewDialog` for double-click photo inspection with zoom and pan controls.
- **Tests**: `tests/test_image_preview_dialog.py`

### Task 4: WellLogPage Integration & 300 DPI Vector PDF Export
- **Files**: `src/pages/well_log/page.py`, `packages/geoviz_well_log/geoviz_well_log/tracks/__init__.py`
- **Work**:
  - Expose `ImageTrack` in `tracks/__init__.py`.
  - Add "📁 导入 LAS 文件" and "📸 新增图像轨道" toolbar actions and sidebar inspector panel in `WellLogPage`.
  - Verify 300 DPI vector PDF/SVG export with embedded photo tracks.
- **Tests**: `tests/test_well_log_las_integration.py`

---

## Verification Criteria

1. All unit & integration tests in `tests/test_las_parser.py`, `tests/test_image_track.py`, `tests/test_image_preview_dialog.py`, and `tests/test_well_log_las_integration.py` pass.
2. Full test suite executes cleanly with 0 failures.
