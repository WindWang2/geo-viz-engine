# Changelog

All notable changes to this project will be documented in this file.

## [0.6.2] - 2026-05-12

### Security
- **Insecure Deserialization Fix**: Migrated well log caching from `pickle` to **Pydantic JSON** (`model_validate_json`). This eliminates the Arbitrary Code Execution (RCE) risk from malicious cache files.
- **Network Security**: Updated AI model inference endpoint to **HTTPS** to protect proprietary geological data during transmission.
- **WebView Hardening**: Implemented `_PaleoMapPage` to restrict navigation in `QWebEngineView`, blocking potential local file exfiltration or remote XSS redirects.
- **Data Privacy**: Removed real well coordinates from git tracking. Added `data/well_coordinates.example.json` as a non-sensitive template.

### Performance
- **Caching Efficiency**: Verified **251x speedup** in well log loading using the new JSON caching layer (1.1ms vs 268ms for raw parse).
- **Seismic Slicing**: Confirmed sub-ms slicing performance (0.023ms on CPU) for 3D volume navigation.

### Added
- **Developer Documentation**: Added detailed `README.md` files to core UI pages (`src/pages/seismic`, `src/pages/well_log`) explaining the integration with modular packages.
- **Dependency Management**: Explicitly added `PyOpenGL` to resolve rendering issues in PyQtGraph-based modules.

### Fixed
- **Test Suite**: Resolved a regression in `ProfileWiggle` tests caused by the migration away from VisPy.
- **Version Consistency**: Synchronized root `pyproject.toml` version with the changelog.

## [0.6.1] - 2026-05-11

### Added
- **地震三维模块重构**：将底层从 Vispy/PyVista 迁移至 **PyQtGraph (QOpenGLWidget)**。
  - 彻底解决了 Linux Wayland 及 Nvidia 环境下的 OpenGL Context 限制与着色器版本冲突。
  - 新增 GPU 计算层：原生集成 **CuPy** (CUDA 13.2) 加速引擎，实现地震体数据在 GPU 显存的常驻与 sub-ms 级别瞬时切片。

## [0.6.0] - 2026-05-11

### Added
- **古地理图大幅增强**：面向出版级质量的完整改进。
  - ECharts 本地打包，支持离线使用。
  - 新增 `PaleoDataLoader`：支持 CSV/Excel 数据自动转换为 GeoJSON。
  - 多时期管理：加载多个时期数据，通过下拉框快速切换。
  - 对比模式：双面板并排对比不同时期。
  - SVG/PDF/PNG 三格式导出。
  - 16+8 个地质 SVG 充填图案（新增滨岸、生物礁、蒸发岩、冰川、火山岩、变质岩、冲积扇、潟湖）。
  - 柔和色系底色 + SVG 图案叠加。
  - 相界线样式（实线/虚线/断层）。
  - 内嵌粗体标签，自动对比度。
  - 图例含图案色块 + 界线类型 + 井位符号。
  - 指北针、比例尺、标题等图面装饰。
  - 井位叠加显示。

## [0.5.1] - 2026-05-11

### Changed
- **性能优化**：异步 QThread 加载 SEGY 和合成数据（不再阻塞 UI）；QPixmap 缓存减少重复渲染；ColormapManager LUT 缓存避免重建色标；ProfileVD 归一化数据缓存加速色标切换；VisPy 批量渲染合并所有 wiggle 道为单次 draw call。
- **代码质量**：horizon.py 修复 `_read_points` 错误列读取（`nums[-1]` → `nums[2]`）；移除 `src/app.py` 中 10 秒超时的 subprocess 探测；为所有公共类和方法添加 docstring；Literal 类型替代字符串枚举；SeismicLoader 支持 context manager。
- **线程安全**：修复 segyio 文件句柄跨线程传递问题（worker 关闭句柄，主线程重新打开）；防止异步 worker 重复触发。
- 删除冗余方法 `is_loaded()`（与 `is_ready()` 相同）。
- 添加 `ColormapManager.clear_cache()` 用于测试和内存受限场景。

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
- **合成地震数据生成**：生成含倾斜反射层、断层和噪声的合成数据用于演示。
- **100 条测试覆盖**：包含数据模型、缓存、色标、层位、加载器、剖面渲染、3D 渲染、视图集成等完整测试。

### Changed
- `SeismicPage` 从独立渲染器改为 `SeismicView` 薄封装（~40 行）。
- 删除旧的 `src/renderers/seismic_renderer.py`，功能已完全迁移到 `geoviz-seismic` 包。
- `src/data/models.py` 移除 `SeismicVolumeMeta`（已迁移到包内）。

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
