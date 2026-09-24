# geoviz-well-track-native

独立 Native C++ 井道可视化包（`GeoViz::WellTrackNative`，namespace `geoviz::well_track`）。
把 `geoviz_well_log`（Python/PySide6）的真实产品能力整理为领域模型 + 产品组件，渲染基座消费
Prompt A 的 `GeoViz::QgisWellTrack`（QGIS/QgsPlot），本包**不包含**第二套通用
canvas/axis/zoom/pan/render 框架。

- 设计与审查文档：`docs/development/native-welltrack-workbench/`（00–16）
- 行为对照 oracle：`03-behavior-oracle.md`（Python 行为 → Native 责任 → kernel 原语 → 测试）

## 分层

```
domain（Qt-free）  ids / depth / curve / style / intervals / markers / defaults / pattern catalog
config（QtCore）   WellTrackViewConfig（可序列化视图配置，JSON）
data  （QtCore）   WellDataSnapshot（不可变快照）/ IWellTrackDataSource / IDepthTransformService
view  （QtWidgets）WellTrackController / WellTrackWidget / 工厂 / 检巡/选择 / 渲染 seam
                    └── IWellTrackSurface ── QgisSurface(条件编译) ── GeoViz::QgisWellTrack ── QGIS
```

## 构建与消费

```bash
# 独立配置（无 Prompt A 时：domain/config/data/view 全部可构建测试）
cmake -S packages/geoviz-well-track-native -B build/wt-native \
      -DCMAKE_BUILD_TYPE=Release -DGEOVIZ_WELL_TRACK_BUILD_TESTS=ON
cmake --build build/wt-native -j4
ctest --test-dir build/wt-native --output-on-failure

# 与 Prompt A 集成（sibling worktree / install prefix）
cmake -S packages/geoviz-well-track-native -B build/wt-native-qgis \
      -DGeoVizQgisWellTrack_DIR=/path/to/A/install/lib/cmake/GeoVizQgisWellTrack
cmake --build build/wt-native-qgis -j4
```

host 侧：

```cmake
find_package(GeoVizWellTrackNative CONFIG REQUIRED)
target_link_libraries(paleo-workbench PRIVATE GeoViz::WellTrackNative GeoViz::QgisWellTrack)
```

```cpp
auto source  = std::make_shared<WorkbenchWellSource>(record);   // 实现 IWellTrackDataSource
auto* view   = geoviz::well_track::WellTrackViewFactory{}.create(source, parent);
layout->addWidget(view);
view->controller()->setDepthTransform(checkshotService);        // 可选 TWT 标注轴
```

完整 API 见 `include/geoviz/well_track/well_track.h` 与 docs 06。

## 与 Prompt A 的关系

- B 冻结消费契约：`include/geoviz/well_track/view/render_surface.h`（`IWellTrackSurface`）。
- 唯一生产实现 `src/view/qgis_surface.cpp` 仅在 `GeoViz::QgisWellTrack` 可用时编译
  （`-DGeoVIZ_WELL_TRACK_WITH_QGIS_KERNEL=ON` + `GeoVizQgisWellTrack_DIR`）。
- 无 A 时包仍可构建/测试（MockSurface 契约测试）；widget 呈现"无渲染内核"错误态。
  **刻意不提供任何像素级 fallback 渲染器**（任务 §4/§19）。

## 资产

`assets/patterns/`（19 岩性 + 17 相 SVG）自 `geoviz_well_log` 原样复制（数据资产复用，
命名规则 parity：pattern key 连字符→下划线；`facies/` 子目录优先）。解析目录顺序：
`$GEOVIZ_WELL_TRACK_PATTERN_DIR` → install prefix `share/geoviz/well-track/patterns`。

## 测试

`tests/`：domain（数值 oracle 对齐 Python 测试断言）、config（roundtrip/校验）、
view（MockSurface 驱动的 controller/widget 行为 + 更新粒度 + 生命周期 + 大数据）。
GUI 冒烟：`examples/host_integration_example --smoke`（有 A 时走真实渲染路径）。

## 边界

- 包不拥有工程文件/数据目录/数据库/版本管理；host 决定视图配置存放位置。
- 深度域：MD（TVDSS 由 host 预算填 MD，仅域标签）；TWT 经 `IDepthTransformService` 注入
  做第二轴标注；不做内部深度/单位换算。
- Python `geoviz_well_log` 保持原样，作为 behavior oracle / fixture 来源。
