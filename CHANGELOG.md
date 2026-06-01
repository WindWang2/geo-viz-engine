# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.12.0] - 2026-06-01

### Added
- **双 GLVolumeItem 叠加渲染 (Phase 12a)**：实现了主振幅数据体与属性数据体（如相干、曲率）的双 GLVolumeItem 三维叠加，支持独立 opacity 不透明度调节、GPU colormap 映射和空间坐标对齐。
- **连井剖面几何规划与报告导出 (Phase 14)**：
  - `auto_section_planner`：自研基于地理走向的 PCA (主成分分析) 与最近邻算法进行多井几何自动选井与连线走向排序。
  - **地图框选交互**：支持在 `MapPage` 井位地图上进行 Shift+Drag 鼠标框选，自动获取框内所有有效测井数据并跳转连井剖面进行 PCA 走向规划排布。
  - **高保真矢量报告导出**：为连井剖面设计了出版级的高保真 PDF/SVG 矢量图件核心导出器。
- **Project 工程文件序列化 (Phase 15)**：
  - 设计了基于 Pydantic 规范的 Git 友好、轻量级嵌套 JSON schema `.gvz` 文件格式，存储多井数据、地震数据、拾取层位、视图设置等全景工程状态。
  - **工程文件数据相对化**：保存时自动相对化路径为工程文件同级或子目录路径，打开时自动还原绝对路径，确保跨机器工程包的便携共享。
  - **DataPage 工程管理 UI**：重构 DataPage，在顶端增加“工程项目管理”分组框，集成“新建/打开/保存/另存为”操作并对接标准 QFileDialog 文件管理器，提供元数据自适应显示。
- **测试套件扩充**：新增 9 个单元测试与 UI 集成测试，验证三维双体叠加、DataPage controls、MainWindow state sync 接口以 100% 绿全部通过，全量测试达到 723 passed。

## [0.11.0] - 2026-06-01

### Added
- **通用图表与等值线插值渲染（Phase 17）**：构建了纯自研、轻量级且高品质的 PySide6 二维通用图表及空间散点等值线/色斑图渲染库。
  - `PlotWidget`：高性能 QPainter 二维通用图表，支持 Heckbert 自适应刻度轴标定、折线及散点绘制。
  - **LTTB 数据降采样算法**：支持 $100K+$ 点大数据量下 QPainter 60+ FPS 流畅渲染，保证十万级数据渲染不假死。
  - **空间插值核心**：实现二维规则网格自研 IDW 向量化插值计算，及 SciPy (RBF/Linear) 空间散点网格化插值。
  - **QThread 异步计算**：将耗时的空间插值计算路由至后台 QThread 异步执行，配合进度/完成信号传递，实现流畅的 GUI 响应。
  - **异常数据与外插边界保护**：引入 NaN 数据清洗掩膜 (Masking) 与外插 Convex Hull 边界防护，防止外插发散或越界。
  - **等值线提取核心**：自研 Marching Squares 算法实现等值线（Line）与等值面（Filled Polygons）的几何路径拓扑提取与多边形闭合。
  - **中石油 (CNPC) 地质色标库**：集成了标准化地质色标模板渲染，支持高品质 PDF/SVG 矢量无损导出。
- **古地理图层级锁定与重叠修复（Phase 11.8 & 11.9）**：
  - 实现全局层级锁定（相/亚相/微相），提供缩放平移层级同步锁。
  - 修复比例尺滑动条刻度防水平重叠保护（最少保持 45px 间距），以及图例标题与色块色卡垂直重叠。
  - 扩充微相/亚相色彩系统，支持超咸水潟湖、湖底泥、三角洲前缘等 13 种地层岩相的 SVGs 图例与 resolvers。
- **15 条新增测试**：覆盖自适应刻度、NaN series 边界、LTTB 压缩、IDW/SciPy 插值、Marching Squares contouring 以及 QThread async worker 生命周期的全量自动化 TDD 测试。

## [0.10.0] - 2026-05-30

### Added
- **井震结合可视化集成（Phase 8）**：将 `geoviz-well-tie` 纯 NumPy 库与 `geoviz-seismic` 可视化引擎完整集成，实现合成地震记录与实际地震剖面的交互对比。
  - `WellTiePanel`：持久化面板，含 Ricker/Ormsby 子波选择、峰值频率滑块、f1-f4 Ormsby 参数滑块、合成记录生成、Auto-Tie 互相关标定、CC 系数和时移量读数、T-D 标定表 CSV 导出。
  - `SeismicView` 工具栏新增"井震标定"可切换按钮，首次点击创建 WellTiePanel（懒加载），后续 toggle 仅隐藏/显示（面板持久化不重建）。
  - `ProfileVD` 合成记录叠合 API：`set_synthetic_overlay(h_position, twt, values)` 在地震剖面上绘制 QPainter wiggle trace 合成记录叠合。
  - `BinGridGeometry`：Pydantic 模型，支持井位 XY 坐标 → 地震 inline/crossline 映射（方位角从北顺时针）。
  - `SeismicVolumeMeta.xy_to_il_xl()`：委托 BinGridGeometry 实现坐标转换。
  - `SeismicLoader.read_trace(iline, xline)`：按 inline/crossline 读取单道数据。
  - `auto_tie()` / `auto_tie_with_quality()`：基于 `numpy.correlate` 的互相关自动时移估计。
  - `generate_synthetic_twt()`：单位安全包装（dt_ms → dt_seconds），自动构建 midpoint calibration 解决反射系数 N-1 对齐问题。
  - `resample_to_seismic_grid()`：将任意 TWT 域数据重采样到地震网格。
- **61 条新增测试**（4 个测试文件）：pipeline 完整流程、空间参考、auto-tie 互相关、WellTiePanel 面板 + SeismicView 集成。总计 589 条测试全部通过。

## [0.9.0] - 2026-05-30

### Added
- **STFT 谱分解与 RGB 属性融合（Phase 7）**：基于 `scipy.signal.stft` 的时频分析，支持三频段 RGB 合成显示。
  - `attributes.py` 新增 `spectral_decompose()`：STFT 带通滤波器组，输出三频段振幅。
  - `fuse_rgb()`：将三个属性体融合为 RGB 三通道数组。
  - `ProfileVD.render_rgba()`：RGBA 直通渲染，跳过色标映射，直接显示 RGB 融合结果。
  - 属性交叉图：QPainter 散点对话框，支持任意两种属性（如频率 vs 包络）的交叉分析。
- **地震属性分析扩展（Phase 6 续）**：
  - `extract_along_horizon()`：沿层位提取属性值。
  - 新增瞬时频率、RMS 振幅、甜点属性、相对声阻抗 4 种属性。
  - `ColormapManager` 新增 viridis 和 phase_wheel 色标。

## [0.8.0] - 2026-05-29

### Added
- **连井对比拾取工作流（`geoviz-cross-well` 包）**：新增独立 `geoviz-cross-well` 包，在现有 QPainter 连井渲染器上叠加专业地层对比工作流。包可独立 pip install 使用。
  - `FormationTopsModel`：层位顶面数据库，支持 CSV 加载/保存，自动地质调色板配色，虚线标注 + 标签。
  - `HorizonPicksModel` + `PicksUndoManager`：手动地层拾取与完整的两栈撤销/重做（Ctrl+Z / Ctrl+Y）。支持拾取放置、跨井连接、深度调整、删除等操作。
  - `CorrelationLayer`：贝塞尔曲线相关连线渲染。手动拾取为实线，DTW 建议为虚线"幽灵拾取"。
  - `DTWEngine`：基于 Sakoe-Chiba 带约束的动态时间规整（DTW）自动层位对比，输出归一化代价与置信度。
  - `SeismicTie`：checkshot CSV 加载与深度-时间（T-D）插值，支持双轴显示。
  - `CrossWellCanvas`：组合 `CrossWellWidget` + `PickingOverlay` + 事件过滤器（拾取/导航模式路由）。
- **CrossWellPage 工具栏重构**：分组工具栏（数据/视图/对比/导出），新增层位导入、域切换（MD/TWT）、状态栏（深度、井数、拾取模式）、富空状态引导页。
- **26 条新增测试**：覆盖层位模型 CSV 往返、拾取模型撤销/重做/JSON 序列化、DTW 引擎（相同/偏移/短/空曲线）、地震校深插值。

## [0.7.0] - 2026-05-29

### Added
- **古地理图多边形编辑模式**：支持对古地理图多边形进行交互式编辑，包括顶点拖拽、多边形拖拽、顶点插入/删除、多边形创建/删除等操作。编辑模式通过工具栏"编辑模式"按钮或快捷键 E 切换。
- **共享顶点拓扑保持**：引入拓扑模型（TopologyModel），相邻多边形共享顶点引用。移动一个顶点时，所有相邻多边形同步更新，确保拓扑关系一致。
- **撤销/重做支持**：基于命令模式（Command Pattern）实现完整的撤销/重做功能，支持 Ctrl+Z / Ctrl+Shift+Z 快捷键。包含 MoveVertexCmd、InsertVertexCmd、DeleteVertexCmd、CreatePolygonCmd、DeletePolygonCmd、EditAttributesCmd 等命令类型。
- **编辑模式上下文菜单**：右键菜单支持删除顶点、删除多边形、编辑属性（相名称、显示名称、边界类型）等操作。
- **GeoJSON 保存与导出**：支持将编辑后的拓扑模型保存为 GeoJSON 文件，以及导出为 PNG / PDF / SVG 格式。支持按层级拆分保存到原始文件。
- **编辑覆盖层**：在编辑模式下显示顶点手柄（蓝色圆点）、边高亮（橙色）、共享顶点指示（绿色），提供直观的编辑反馈。
- **FaciesHierarchy.get_children 方法**：新增获取指定特征直接子节点的方法。

### Changed
- **ZoomPanHandler 编辑模式禁用**：编辑模式下自动禁用平移缩放操作，避免编辑冲突。
- **FaciesPolygonsLayer 选择高亮**：编辑模式下选中的多边形显示高亮发光效果，未选中的多边形自动变暗。
- **TopologyBuilder 代码重构**：提取 `_build_rings` 辅助方法，统一 `from_features` 和 `from_hierarchy` 的环构建逻辑。

### Fixed
- **DeleteVertexCmd 共享顶点修复**：修复删除共享顶点时错误清除所有关联特征引用的问题，现在仅移除当前特征的引用。
- **DeletePolygonCmd.undo 修复**：修复撤销删除多边形时创建孤立顶点的问题，正确引用已存在的顶点 ID。
- **InsertVertexCmd / DeleteVertexCmd 边索引一致性**：修复边索引在插入/删除顶点时的不一致问题。
- **EditAttributesCmd 撤销修复**：基于快照实现属性编辑的撤销，确保完整恢复原始属性。
- **to_geojson 修复**：修复带孔洞的环使用 MultiPolygon 而非 Polygon 类型的问题。

## [0.6.4] - 2026-05-28

### Added
- **多级锁定与精确边界渲染**：在锁定面板中支持将古地理图对象精确锁定至“相”、“亚相”或“微相”级别。即使在相缩放界面下，被锁定的亚相或微相边界依然能够自动且精确地渲染（分别以 1.5px 和 1.0px 的粗细绘制），而其他未锁定的古地理区块依然保持干净清爽的相级边界。
- **标注高对比度 Badge**：为锁定状态的对象标注增加了高对比度、带圆角边框的 Badge 胶囊背景，搭配 🔒 前缀，使其在深浅色底图上都能清晰可辨，并与未锁定对象产生强烈的视觉区隔。
- **边界防越级与精准过滤**：优化了全图边界绘制的主被动过滤逻辑，当且仅当边界级别不深于视图级别或所涉子树被明确锁定至足够深度时才行绘制，完全消除了全局边界杂乱的 Bug。

### Changed
- **内部边界淡化机制优化**：在放大的微观尺度下，被锁定的父级相/亚相的内部边界将自动以半透明（透明度约 17%，粗细 0.7px）淡化处理，从而过滤不必要的细节噪声。

## [0.6.3] - 2026-05-28

### Added
- **新增独立包 `geoviz-map`**：基于 QPainter + Web Mercator 投影的地理可视化引擎，6 个 layer 组合渲染（背景/经纬网/世界陆地/中国省界/参考标签/井点），支持视口剔除、cursor-anchored 滚轮缩放、拖拽平移、井点 hover/click hit-test。可独立 pip install 后嵌入任意 PySide6 项目。
- **新增独立包 `geoviz-paleo-map`**：基于 QPainter + Plate Carrée 投影的古地理图引擎，8 个 layer（4 数据层 + 4 chrome）。复用 `geoviz-well-log.PatternEngine` 并新增 `get_composite_brush` / `get_color_fuzzy` 两个公共方法。

### Changed
- **PaleoMap 渲染重写**：古地理图从 QWebEngineView + ECharts 迁移到原生 QPainter。1:1 视觉/交互对齐（背景、polygon 复合花纹、边界样式、井位、标题、指北针、比例尺、图例、tooltip）。tempfile-based GeoJSON 中转移除，`load_features(features, period_name, wells)` 直接消费 dict。
- **MapPage 渲染重写**：井位分布图从 QWebEngineView + MapLibre GL 迁移到原生 QPainter（通过 `geoviz_map` 包），1:1 视觉/交互对齐。消除了 Windows 上 WebEngine + OpenGL 上下文冲突的潜在隐患。
- **仓库结构整理**：将根目录散落的临时调试脚本、旧 ECharts Web 实验工程、`package.json`/`node_modules` 等遗留产物迁入 `archive/` 归档目录（`scripts/`、`web-echarts/`、`web-deps/`、`misc/`），全部通过 `git mv` 保留历史。
- **截图统一**：根目录散落的参考图与 QA 截图收纳至 `docs/screenshots/{references,qa}/`。
- **杂项归位**：`sample_paleo.geojson` → `samples/`，`build_with_conda.bat` → `scripts/`。

### Removed
- 删除 `src/pages/paleo_map/renderer.py`（411 行含 295 行内联 HTML/JS）和 `_write_period_geojsons` / `_period_geojson_files` / `_cleanup_tmp` 中转代码。
- `_PaleoMapPage(QWebEnginePage)` 子类 + tempfile 中转一并消失。主应用零 WebEngine import。
- 删除 `src/pages/map/renderer.py`（394 行 MapLibre 嵌入实现）。
- 删除 `src/pages/map/assets/maplibre-gl.{js,css}`（~640 KB 内联资产）。
- `well://` 自定义 URL scheme 与 `QWebEnginePage` 子类一并消失。
- 从 git 索引彻底移除 `node_modules/`（1909 文件），并在 `.gitignore` 中加入 `node_modules/`、`.coverage`、根目录散落图片防护。

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
