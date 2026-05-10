# Changelog

All notable changes to this project will be documented in this file.

## [0.5.0] - 2026-05-11

### Added
- **地震可视化独立包 `geoviz-seismic`**：将 3D 体渲染、2D 剖面显示、SEGY 加载等从主应用提取到独立 PySide6 包。
  - 新增 `loader.py`：`SeismicLoader` 基于 segyio 的按需切片读取，支持 inline/crossline/timeslice 与降采样。
  - 新增 `renderer_3d.py`：`Renderer3D` 基于 PyVista Qt 的 3D 体渲染，含交互式 inline/crossline/time 切片平面。
  - 新增 `profile_vd.py` / `profile_wiggle.py`：VD 热图与 Wiggle 波形剖面渲染，VisPy GPU 加速回退。
  - 新增 `profile_widget.py`：`ProfileWidget` 统一 VD/Wiggle 切换与色标选择。
  - 新增 `seismic_view.py`：`SeismicView` 组合 3D 渲染 + 2D 剖面 + 工具栏的完整地震可视化组件。
  - 新增 `cache.py`：`SeismicCache` LRU 切片缓存（默认 50 条）。
  - 新增 `colormap.py`：`ColormapManager` seismic/gray/jet/hsv 色标生成与数据映射。
  - 新增 `horizon.py`：`HorizonParser` 层位文件解析，支持 nearest/RBF 插值填充。
  - 新增 `models.py`：`SeismicVolumeMeta`、`SliceInfo`、`HorizonData` 数据模型。
- **合成地震数据生成**：`SeismicView._generate_synthetic()` 生成含倾斜反射层、断层和噪声的合成数据用于演示。
- **100 条测试覆盖**：包含数据模型、缓存、色标、层位、加载器、剖面渲染、3D 渲染、视图集成等完整测试。

### Changed
- `SeismicPage` 从独立渲染器改为 `SeismicView` 薄封装（~40 行）。
- 删除旧的 `src/renderers/seismic_renderer.py`，功能已完全迁移到 `geoviz-seismic` 包。
- `src/data/models.py` 移除 `SeismicVolumeMeta`（已迁移到包内）。
- `src/app.py` 新增 subprocess 安全探测，防止无 OpenGL 环境下 pyvistaqt 导致 C-level 崩溃。
- 版本号升级到 0.5.0。

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
