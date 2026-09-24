# 04 — QGIS Kernel Contract（对 Prompt A 的冻结消费契约）

> A 状态（2026-09-24）：origin 无 A 分支/PR，本机无 `packages/geoviz-qgis-welltrack/`。本文档是 **B 侧冻结契约**：B 只依赖此处列出的能力面；A 合并后若有出入，只需修 `src/view/qgis_surface.cpp` 一个适配文件。

## 分层原则（任务 §4 的落地）

```
host (paleo-workbench)
  → GeoViz::WellTrackNative  (domain/config/data/view)
      → IWellTrackSurface     ← B 拥有的窄接缝（本包 public header）
          └── QgisSurface     ← 唯一生产实现（src/view/qgis_surface.cpp，编译期门控）
                → GeoViz::QgisWellTrack (Prompt A) → QGIS/QgsPlot
```

- B 代码（controller/widget/inspection/selection/serialization）只面向 `IWellTrackSurface`。
- `QgisSurface` include A 的 public headers，把 seam 调用翻译为 A API；**B 不 include QGIS 头**（QGIS 类型不泄漏出 A）。
- 测试用 `MockSurface`（只记录调用，不渲染像素）——是 contract test double，不是 fallback 绘图引擎。

## B 需要 A 提供的能力（冻结清单）

| # | 能力 | seam 形式 | A 域内职责 |
|---|---|---|---|
| K1 | track viewport（多列布局容器 + 每列内容绘制） | `setTracks/updateTrack/removeTrack` | 列几何、列头底、文本/标签绘制 |
| K2 | shared depth viewport | `setDepthRange` + `depthAt(y)` | 深度↔像素映射的唯一权威 |
| K3 | curve rendering | `SurfaceCurveLayer`（buffer 指针 + 样式 + X range/log） | LOD/降采样/视口裁剪/QPainterPath |
| K4 | generic interval/band | `SurfaceIntervalRow`（矩形/三角 + 颜色/pattern 资产路径） | 区间矩形/形状填充、pattern 材质化 |
| K5 | marker | `SurfaceMarkerRow`（dashed 线 + 颜色 + label） | 全画布层位线绘制 |
| K6 | plot tools（wheel zoom / drag pan / dblclick） | surface 自持输入，向上发 `depthRangeRequested/fitRequested` | 光标锚定换算（A 持有 viewport 几何） |
| K7 | hit testing | `trackAt(pos)`、`hitCurve(pos, tol)` | 像素容差命中 |
| K8 | LOD/render substrate | （K3 内隐含） | 缓存/失效策略 |
| K9 | 文本标签绘制（track header / interval label / 深度刻度文本） | `SurfaceTrackHeader`、`SurfaceIntervalRow.label`、`SurfaceTick` | 自适应字号/换行/竖排（label policy） |

**B 保留的产品职责**（不得下放也不得上移）：轨道顺序/宽度/显隐配置、深度域规则（钳制/最小 span/no-op 守卫）、inspection 组装、selection、视图序列化、pattern 名→资产 key 解析、robust range、nice interval 计算、merge/split 语义。

## 交互事件的归属（防"第二 zoom/pan 框架"）

- A（surface）持有原始输入事件（wheel/mouse），把**视口意图**以信号上报：`depthRangeRequested(top,bottom)`、`fitRequested()`、`cursorDepthChanged(depth, trackId)`、`trackHeaderClicked(trackId)`、`splitterDragged(trackId, newWidthPx)`（若 A 提供列边界拖拽；否则 B 在 overlay 层处理，见 08）。
- B（controller）应用产品规则后**回写** `setDepthRange`。数学锚定（zoom around cursor）由 A 完成（它持有 y→depth）；业务钳制（全范围、span≥1.0、1e-9 no-op）由 B 完成。与 Python 的 ZoomPanHandler/canvas 分工同构。

## CMake 解析（任务 §19）

```cmake
# packages/geoviz-well-track-native/CMakeLists.txt
find_package(GeoVizQgisWellTrack QUIET CONFIG)
option(GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL "Build QgisSurface adapter" ${GeoVizQgisWellTrack_FOUND})
if(GEOVIZ_WELL_TRACK_WITH_QGIS_KERNEL)
  target_sources(geoviz_well_track_native PRIVATE src/view/qgis_surface.cpp)
  target_link_libraries(geoviz_well_track_native PUBLIC GeoViz::QgisWellTrack)
endif()
```

- A 未就绪时：库仍构建（domain/config/data/view/mock 兼容层），`QgisSurface` 不编译，CMake STATUS 明示；widget 需 host 注入 surface factory。
- A 就绪后（sibling worktree/install prefix）：`cmake -DGeoVizQgisWellTrack_DIR=/path/to/A/install/lib/cmake/GeoVizQgisWellTrack`，完整集成构建（§19/DoD 17）。
- **禁止**：为脱离 A 编译而在 B 内实现任何像素级 fallback surface。

## 集成验证路径（当 A 可用时）

1. 从 A worktree 构建 A → install prefix。
2. B 以该 prefix 配置，构建 `geoviz_well_track_native`（含 qgis_surface.cpp）。
3. 跑 `examples/host_integration_example`（representative well smoke）。
4. host-link smoke：一个最小 main 链接 `GeoViz::WellTrackNative` + `GeoViz::QgisWellTrack` 只验证符号/初始化/销毁。
