# Technical Design Spec: Single-Well Image Track & LAS File Parser (Phase 32 / v0.20.0)

## 1. Executive Summary

Phase 32 introduces **Industry-Standard LAS 2.0/3.0 File Parsing (`las_parser.py`)** and a dedicated **Single-Well Image Track (`ImageTrack`)** to `geoviz-well-log` and `WellLogPage`. It enables loading `.las` curve datasets with automatic NULL value cleaning, depth-scaled high-resolution core photo segment mapping, continuous FMI borehole image pseudocolor rendering, click-to-zoom image inspection, and 300 DPI vector PDF/SVG report exporting.

---

## 2. System Architecture & Component Breakdown

```
+-----------------------------------------------------------------------------+
|                       WellLogPage (src/pages/well_log/page.py)               |
|                                                                             |
|  - Toolbar Actions: "📁 导入 LAS 文件", "📸 新增图像轨道"                     |
|  - Image Track Inspector Panel (Core photo list & FMI settings)              |
+------------------------------------+----------------------------------------+
                                     |
                                     v
+------------------------------------+----------------------------------------+
|            geoviz_well_log (Package: Well Log Engine & Tracks)               |
|                                                                             |
|  1. LASParser (packages/geoviz_well_log/geoviz_well_log/las_parser.py)     |
|     - Parses ~V, ~W, ~C, ~A sections in LAS 2.0/3.0 format                  |
|     - Cleans sentinel NULL values (-999.25, -9999.0 -> np.nan)              |
|                                                                             |
|  2. ImageTrack (packages/geoviz_well_log/geoviz_well_log/tracks/image_track.py)|
|     - Inherits from TrackBase                                               |
|     - CorePhotoSegment rendering with QPixmap depth-proportional scaling     |
|     - BoreholeImageSegment rendering for 2D FMI matrix pseudocolor          |
|     - Double-click QDialog preview magnifier                                |
+-----------------------------------------------------------------------------+
```

---

## 3. LAS 2.0/3.0 Parser Specification

- **Module**: `packages/geoviz_well_log/geoviz_well_log/las_parser.py`
- **Supported Section Tokens**:
  - `~VERSION` / `~V`: Version string and wrapping flags.
  - `~WELL` / `~W`: Well name (`WELL`), start depth (`STRT`), stop depth (`STOP`), step (`STEP`), null sentinel (`NULL`).
  - `~CURVE` / `~C`: Curve mnemonic, unit, and description pairs.
  - `~ASCII` / `~A`: Matrix numerical data block.
- **Sentinel NULL Sanitization**: Replaces missing values matching `NULL` sentinel with `np.nan`.
- **Output Data Structure**:
  ```python
  @dataclass
  class LASParseResult:
      well_name: str
      depth_name: str
      depth: np.ndarray
      curves: dict[str, np.ndarray]
      units: dict[str, str]
      descriptions: dict[str, str]
  ```

---

## 4. ImageTrack Specification

- **Module**: `packages/geoviz_well_log/geoviz_well_log/tracks/image_track.py`
- **Data Models**:
  - `CorePhotoSegment(depth_top: float, depth_bottom: float, image_path: str, title: str)`
  - `BoreholeImageSegment(depth_top: float, depth_bottom: float, data_matrix: np.ndarray, colormap_name: str)`
- **Rendering**:
  - Calculates pixel target `target_rect = QRectF(track_x, y_top, track_width, y_bottom - y_top)`.
  - Paints scaled pixmap using `QPainter.drawPixmap(target_rect, pixmap)`.
- **Interactive Inspection**:
  - Double-clicking photo segment opens `ImagePreviewDialog` for zoom and pan.

---

## 5. Verification Plan

1. **Unit Tests**:
   - `tests/test_las_parser.py`: Verify parsing of sample LAS 2.0 content with NULL replacements.
   - `tests/test_image_track.py`: Verify `ImageTrack` creation, `CorePhotoSegment` depth mapping, and paint execution.
2. **Integration Tests**:
   - `tests/test_well_log_las_integration.py`: Test end-to-end LAS import in `WellLogPage` and 300 DPI report export.
