# 15 — Final Build Evidence（受控 targeted build）

日期：2026-09-24。开发全程仅本轮做完整编译（前序仅 Round 4 期间一次基线 + 一次集成的增量尝试），并行度 -j2/-j4（≤6 上限遵守），未重编 QGIS SDK（只读复用 vendored 安装树），未做全仓构建。

## 1. 基线构建（无 A：domain/config/data/view + MockSurface 测试）

```
cmake -S packages/geoviz-well-track-native -B /tmp/wt-build-base -DCMAKE_BUILD_TYPE=Release
cmake --build /tmp/wt-build-base -j2/-j4        → [100%] Built target host_integration_example（0 error）
ctest --test-dir /tmp/wt-build-base             → 100% tests passed (3/3)
  wt_domain_tests  Passed 0.02s   （TestDepth/CurveBuffer/RobustRange/XRange/Intervals/PatternCatalog/Defaults）
  wt_config_tests  Passed 0.02s   （ViewConfig roundtrip + DocumentBuilder parity）
  wt_view_tests    Passed 0.14s   （深度规则/轨道管理/snapshot diff/巡检/吸附/同步组/生命周期/大数据）
host_integration_example --smoke（错误态路径）   → exit=0
  smoke: tracks=6 depth=1250.00 curves=3 intervals=4 markers=1
  smoke: config tracks=6 roundtrip=ok
```

过程中修复的编译错误（本轮首次真实编译暴露）：`well_track_factory.h` 缺前置声明；`resolveXRange` 定义落错命名空间；`document_builder.cpp` 缺 robust_range include；example 缺 `<QJsonArray>`；`mock_surface.h`（Q_OBJECT）未列 target sources 导致 vtable 未定义。

## 2. Prompt A 集成构建（真实 QGIS 内核）

A 目标：`/home/kevin/projects/paleo_project/main/geo-viz-engine-wt-qgis-welltrack`（分支 `feat/qgis-plot-welltrack-kernel`）在验证期间被并行修改 → **对当时状态做只读快照 `/tmp/qwt-snapshot`**，对快照构建（A 侧预存问题与 shim 清单见 docs/14 构建后记，共 S1–S8）。

```
export PALEO_QGIS_SOURCE_DIR=.../main/third_party/qgis
export PALEO_QGIS_SDK_DIR=.../main/native/qgis_render_bridge/build/qgis-vendor/output
export PALEO_QGIS_BUILD_DIR=.../qgis-vendor
export PWB_QGIS_DEPS_PREFIX=.../main/build/qgis-deps-prefix
cmake -S packages/geoviz-well-track-native -B /tmp/wt-build-qgis \
      -DGEOVIZ_QGIS_WELLTRACK_DIR=/tmp/qwt-snapshot
  → geoviz-well-track-native: QgisSurface adapter ENABLED (Prompt A kernel)
cmake --build /tmp/wt-build-qgis -j2（含 A 的 core+gui + QGIS 头编译）
  → [100%] Built target wt_view_tests / host_integration_example（0 error）
ctest（QT_QGIS_PREFIX_DIR + LD_LIBRARY_PATH 注入）
  → 100% tests passed (3/3)，0.55s
```

## 3. Representative well smoke（真实内核路径，两次运行）

```
QT_QPA_PLATFORM=offscreen GEOVIZ_WELL_TRACK_PATTERN_DIR=<pkg>/assets/patterns \
  /tmp/wt-build-qgis/examples/host_integration_example --smoke
  smoke: tracks=6 depth=1250.00 curves=3 intervals=4 markers=1
  smoke: config tracks=6 roundtrip=ok
  exit=0   （复跑第二次同样 exit=0）
```

内核真实参与证据：
- `nm -C host_integration_example | grep -c QgisSurfaceFactory` = 18（factory 已链接，静态库 keep-alive 生效）；
- `ldd` 显示 `libqgis_core.so.4.2.0` / `libqgis_gui.so.4.2.0` 从 vendored SDK 解析加载；
- 路径为 factory.create → SurfaceRegistry → QgisSurface → WellTrackCanvas(QgsPlotCanvas)，`QgsApplication` 前置引导（prefix/init/initQgis/exitQgis）。
- 脚本化操作全通过：zoomAt(1500, 0.2)、inspectAt(1250)（3 曲线插值 + 4 interval 命中 + 1 层位命中）、hide lithology、moveTrack(facies→0)、viewConfig JSON roundtrip、close。

## 4. Host-link smoke

`host_integration_example` 本身即同时链接 `GeoViz::WellTrackNative` 与 `GeoViz::QgisWellTrack`（+QGIS SDK）的最小 host：create → 操作 → destroy 全链 exit=0。

## 5. 结论

- 基线（无 A）与集成（有 A）两条构建线全绿，测试 3/3 ×2，冒烟 2/2。
- 编译并行度最大 -j4、常态 -j2；ICE 重试环未触发（本轮无编译器崩溃）。
- A 集成经快照完成（A 分支自身仍未可编译——S4/S5 需 A 修复；见 docs/14）。
