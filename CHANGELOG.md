# Changelog

All notable changes to this project will be documented in this file.

## [0.4.0] - 2026-05-10

### Added
- **测井可视化引擎独立化**：将 track 构建、排序、合并/拆分、导出逻辑从 `WellLogPage` 提取到 `geoviz-well-log` 包中。
  - 新增 `payload_builder.py`：`build_tracks_from_data()` 等数据变换函数，从 `WellLogData` 构建 ECharts JSON payload。
  - 新增 `track_manager.py`：`TrackManager` 类，管理轨道排序、可见性、曲线合并/拆分。
  - 新增 `export.py`：`export_dialog()` / `export_svg()` / `export_pdf()` / `export_png()`，SVG/PDF 矢量导出与显示完全一致。
  - 新增 `pattern_map.py`：`PATTERN_MAP` 从 `src/utils/constants.py` 移入包内。
- **测井页面选井器**：`WellLogPage` 工具栏新增下拉框，可直接选择井位加载测井图，无需切换到地图页。
- **包完整 API 文档**：`packages/geoviz_well_log/README.md` 重写，包含 API 参考、JSON payload 格式、3 个完整示例。

### Changed
- `WellLogPage` 从 ~900 行精简到 ~350 行，仅保留 UI 编排和 AI 预测业务逻辑。
- `src/utils/constants.py` 改为从 `geoviz_well_log.pattern_map` re-export `PATTERN_MAP`，保持向后兼容。
- ECharts SVG renderer 保证导出与显示完全一致（矢量输出）。

## [0.3.0] - 2026-05-09

### Added
- **Paleogeography Map Visualization**: A new targeted, high-aesthetics map rendering module for ancient geography.
- Zero-friction GeoJSON loading via drag-and-drop or file picker.
- Instant high-resolution static PNG export capability.
- Support for rendering arbitrary geological facies using existing SVG rock patterns seamlessly via ECharts.
- Async loading of massive GeoJSON files using PySide6 localfile interception to prevent UI freezing.

### Changed
- Centralized facies to SVG pattern mapping in `src/utils/constants.py` to remove DRY violations across modules.
