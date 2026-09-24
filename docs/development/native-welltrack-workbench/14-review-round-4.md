# 14 — Review Round 4（cross-worktree integration，对 Prompt A 真实 public API 对账）

日期：2026-09-24 · A 状态：**已找到** — worktree `/home/kevin/projects/paleo_project/main/geo-viz-engine-wt-qgis-welltrack`，分支 `feat/qgis-plot-welltrack-kernel`，基线 `ebe9b70f`（领先 origin/main 3 commits，未合并、未推送 origin）。

## 对账方式

逐头精读 A 的 13 个 public headers（well_track_canvas / track_model / curve_data / curve_style / axis_spec / depth_domain / hit_testing / track_layout / well_track_tools / depth_synchronizer…）+ A 的 CMakeLists + demo/example，然后实现 `src/view/qgis_surface.cpp`（B 内唯一 include A 头的文件）。

## 契约对账表（B seam → A 真实 API）

| B seam（render_surface.h） | A 实现 | 备注 |
|---|---|---|
| `widget()` | `WellTrackCanvas : QgsPlotCanvas` | A 适配 QGIS plot canvas shell；pan/zoom 手势为纯 QGIS |
| `setTracks` | 重建 `WellTrackModel`（`adoptTrack(shared_ptr<TrackSpec>)`）+ `canvas->setModel` | 全量同步路径 |
| `updateTrack`（upsert） | 存在则原地改 `TrackSpec` + `model->touch()` + `canvas->refresh()`；不存在则 `adoptTrack` | A 的 model 可变 + generation 计数天然支持 |
| `removeTrack` | `model->removeTrack(quint64)` + refresh | id 映射：B string ↔ A quint64（adapter 计数器分配） |
| `setDepthRange` | `canvas->setDepthDomain(makeDomain(top,bottom))` | A 侧自带 1e-9 no-op 守卫（kDepthNoOpEpsilon）与 clamp |
| `setFullDepthRange` | no-op | A 从 model `depthExtent()` 推导 full extent（canvas.cpp:51） |
| `setSecondaryAxis` | **接受但忽略** | A v1 无第二轴 API（open item #1） |
| `trackAt` | `lastLayout().trackAtX(x)` + 反查 id + `canvas->depthAt(pos)` | |
| `hitCurve(pos,tol)` | `canvas->hitTest(pos,tol)` → `HitResult.curveId`（SeriesId 反查） | A 提供 O(log n) 最近采样命中 |
| `depthAt` / `yPosForDepth` | `canvas->depthAt(pos)` / `depthDomain().yForDepth(depth, contentArea)` | 视窗外 → -1 对齐 |
| `depthPerPixel` / `contentHeight` | `contentArea.height()/domain.span()` | |
| `trackGeometry` | `lastLayout().geometryForTrackId(id)->columnRect` | A 的 TrackLayoutResult 供 overlay 定位 |
| `supportsImageTracks` | false | A v1 无图像带（open item #2） |
| `depthRangeRequested` 信号 | 连 A `canvas->depthRangeChanged(shallow,deep)` | 双侧 no-op 守卫终止回声 |
| `cursorMoved` | 连 A `cursorDepthChanged(depth)`（NaN=离开内容区） | A 另有 `sampleHovered(HitResult)`（B 暂不消费，host 可直连） |
| `fitRequested` / `trackHeaderClicked` | 无 A 信号 | B 侧由 API（`fitDepth()`）承担；header 点击待 A（open item #3） |
| `viewportResized` | adapter 对 canvas `installEventFilter` Resize | |
| 曲线零拷贝 | `CurveSeriesView`（borrowed 内存） | **关键生命周期**：adapter 每 track 保留 `CurveBufferPtr`（`retained_`），保证借用数组存活于所有引用它的 model snapshot——A 的文档化合同 |
| 样式 | `CurveStyle{lineColor,lineWidthF,penStyle}` + `TrackAxisSpec{min,max,Log10,logFloor=1e-10}` | log floor 双侧一致（1e-10 parity） |
| 区间带 | `DepthIntervalBand{top,bottom,QBrush,label}` | pattern 材质化在 adapter（QSvgRenderer→20px tile→QBrush，pattern_engine.py parity；Qt6::Svg 仅 adapter 门控内链接） |
| markers | `DepthMarkerLine{depth,color,DashLine,1.5,label}` 附加到**每个** curve track | 复合全画布 overlay 视觉（Python MarkerTrack parity） |
| 深度轴 | `TrackRole::DepthRuler`（A 原生渲染标签，宽 72 默认） | seam 的 ticks 不转发（供无原生 ruler 的 kernel）；B 仍计算（domain 逻辑保留） |

## 有意的能力降级（记录，不算缺陷）

1. **嵌套相三列**：A v1 band 无 sub-column → 降级为最深一级（Python 非嵌套模式已有该语义）。
2. **header 曲线摘要**（swatch + min~max unit）：A header 只画 title/axis scale → headerEntries 仅 title 生效（open item #4）。
3. **图像轨**：`supportsImageTracks()==false` → controller 跳过 image 列（能力门控设计）。

## CMake 集成（对 A 真实消费模式的适配）

- A **没有 install/export config**（其 README 消费方式 = `add_subdirectory`）→ B 增加 `GEOVIZ_QGIS_WELLTRACK_DIR` cache 路径 → `add_subdirectory` A 包；同时保留未来 `find_package(GeoVizQgisWellTrack CONFIG)` 路径。
- A 的 `cmake/GeoVizQgisSdk.cmake` 从环境读 `PALEO_QGIS_SOURCE_DIR/PALEO_QGIS_SDK_DIR/PALEO_QGIS_BUILD_DIR/PWB_QGIS_DEPS_PREFIX`（与 paleo-workbench 同名合同）→ B 构建时导出同组变量。
- adapter 开启时：B 链 `Qt6::Svg`（PRIVATE）+ 公开 `GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL` 编译定义（example 据此引导 `QgsApplication`：prefix + init/initQgis/exitQgis，A demo 同款）。
- 测试（静态链接传递 QGIS）ctest 注入 `QT_QGIS_PREFIX_DIR` + `LD_LIBRARY_PATH=${GEOVIZ_QGIS_RUNTIME}`（A 测试同款 env）。

## 集成验证计划（docs 15 执行）

1. 以 A worktree 的包为 `GEOVIZ_QGIS_WELLTRACK_DIR`，SDK 环境变量注入后 configure B。
2. `cmake --build -j4`（峰值 ≤6；GCC16 ICE 时重试循环）。
3. ctest 三组测试。
4. `host_integration_example --smoke`（真实 QGIS 渲染路径 representative well smoke）。
5. host-link smoke：example 即是（链接 GeoViz::WellTrackNative + GeoViz::QgisWellTrack）。

## Open items（反馈给 A 线，非 B 阻塞）

1. 第二深度轴（TWT）原语。
2. 图像带（岩心照片）。
3. track header 点击信号 + header 曲线摘要（swatch/range 文本）。
4. band 子列（嵌套相）。
