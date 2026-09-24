# 00 — Basine（基线快照）

> 日期：2026-09-24 · 分支：`feat/native-welltrack-workbench` · base SHA：`0f89b9ed`（origin/main，Merge PR #153）
> worktree：`/home/kevin/projects/paleo-merged-main/geo-viz-engine-wt-welltrack-workbench`

## 仓库形态（事实）

- **Python/PySide6 monorepo**（uv workspace，`packages/` 下 9 个 hatchling 子包），无根 CMake，无任何 `.cmake`；唯一 native 代码是 `native/map_edit_core/`（pybind11 + setuptools，消费方仓库构建，不在 workspace 成员中）。
- Python 严格 3.12；Qt 绑定只用 PySide6；CI：fast gate = `pytest -m "not slow"`，slow job best-effort。
- 与井相关包：`geoviz_well_log`（34 源文件 + 16 测试，~9.3k 行）、`geoviz_cross_well`（20 文件）、`geoviz_well_tie`（14 文件，纯 numpy 无 Qt）、`geoviz_plots`（35 文件，通用 XY 绘图，**与 well_log 零耦合**）、`geoviz_common`（6 文件，map/paleo-map 专用，与 well_log 无关）。
- app 侧：`src/pages/well_log/page.py`（宿主编排）、`src/data/loaders.py`（Excel/LAS/XML → WellLogData）、`src/data/models.py`（AppWellLogData 扩展）。

## 渲染现状（事实）

- 主流水线：`WellLogData(pydantic) → build_qpainter_tracks() → WellLogCanvas.set_tracks() → QWidget-per-track QPainter`；同一 QPainter 路径服务屏幕显示与 SVG/PDF/PNG 矢量导出。
- 遗留 ECharts/WebEngine 路径（`chart_engine.py` + `web_dist/` 1.1MB）与声明式 `config.py` schema 不被 QPainter 管线消费。
- 自研基础设施（well_log 包内）：`LayoutCoordinator`（深度广播）、`ZoomPanHandler`、`CrosshairOverlay`、`DepthRuler`、min-max 降采样、QPainterPath/QPixmap 双缓存。与 `geoviz_plots`/`geoviz_common` 无代码共享。

## 深度域（事实，决定 Native 包边界）

- **渲染域只有 MD**。`datum_elevation` 字段存在但包内零消费；TVDSS 由宿主 loader 算好后填进 MD 列（`src/data/loaders.py`）。
- TWT 仅是 overlay 上的**第二坐标轴标注**（`PickingOverlay._paint_twt_axis`），由 `CheckshotTable`（分段线性插值，可回退 np.interp）提供 depth↔twt 转换；track 渲染不做时间域重采样。
- 无 TVD 变换、无 sample 域。

## 视图配置持久化（事实）

- **当前完全没有**：track 顺序/宽度/可见性/曲线分配/样式均为内存态，每次加载井由 `build_qpainter_tracks` 按固定默认规则（`_MERGE_GROUPS`、固定宽度）重建；`.gvz` 工程文件只存 active_page + seismic 字段。
- Native 包将**新增**可序列化 view/track configuration（本任务 §13 要求），这是能力增量而非 parity。

## Prompt A（GeoViz::QgisWellTrack）状态

- 基线时点：origin 无 A 分支、无 open PR；本机无 `packages/geoviz-qgis-welltrack/`、无 A worktree。
- 结论：B 按"冻结 public contract"模式对接 —— 在 B 内定义**极薄 adapter seam**（`IWellTrackSurface`），唯一生产实现 `QgisSurface` 编译期以 `find_package(GeoVizQgisWellTrack)` 门控；A 可用后从 sibling worktree/install prefix 解析其 target 做集成验证。不复制 A 实现、不写 fallback 绘图引擎。
- 期间每次进入新 review 轮时 re-fetch 检查 A 分支是否出现（见各 review 文档的"A 状态"节）。

## 基线已知问题（来自审查，Native 设计须规避）

1. `CrosshairOverlay/WellLogView/ConnectionOverlay/CrossWellWidget/section_canvas/WellItem` 六处手写同一 depth↔Y 公式 —— #114 系列 bug 来源。
2. `downsample._provider`、`las_preview._las_parser_provider` 进程级全局单例、无线程保护、异常静默吞。
3. 两个 `PatternEngine` 单例不共享缓存；pattern 在 SVG 导出中是位图。
4. `CrossWellWidget.eventFilter` 需 `hasattr` 防 C++ 对象先析构 —— 析构顺序脆弱。
5. `WellLogPage._cleanup_load_thread` 超时后置 None，迟到 `finished` 可篡改当前井（app 级，host 参考须写对）。
6. 页面层访问 `track._curves` 私有属性、label 字符串作 track key（merge 后可碰撞）。
7. interval_id 用 `"_"` 拼接字符串编码 —— 新 domain 用结构化 id，禁止复制。

## 并行边界

- B 只拥有 `packages/geoviz-well-track-native/**` 与 `docs/development/native-welltrack-workbench/**`；不改 A 目录。
- **不改根 CMakeLists**（当前不存在）：B 包自带完整 CMake，可独立 `cmake -S packages/geoviz-well-track-native -B ...` 配置；根级聚合 CMake 留给未来统一决策，PR 中给 merge guidance。与 A 零文件 overlap。
