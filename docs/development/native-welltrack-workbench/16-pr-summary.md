# 16 — PR Summary

- 分支：`feat/native-welltrack-workbench`（base `origin/main` @ `0f89b9ed`，7 commits，已 push）
- **PR #154**：`feat(well-log): add native QGIS-backed well-track visualization package`
  https://github.com/WindWang2/geo-viz-engine/pull/154
- 状态：open，不等待线上 CI，不自动 merge。

## 提交序列

| SHA | 内容 |
|---|---|
| `d23079c8` | 包骨架（domain/config/data/view + seam + tests + example + 资产 + docs 00-10） |
| `e0c209cc` | Round-1 架构审查修复（4×P0、2×P1、6×P2） |
| `f638c055` | Round-2 交互审查修复（P0 splitter 吞输入、P1 隐藏轨复活） |
| `8bf6221f` | Round-3 对抗审查修复（2×P1、5×P2、10×P3） |
| `0b3b7b4b` | Round-4：qgis_surface.cpp 真实对接 A public API + CMake 集成 |
| `6ba6dcb0` | 受控构建收尾（真实编译暴露的修复 + A 侧 shim 块 + docs/15 证据） |
| （本次） | docs/16 |

## DoD 核验（任务 §22 的 21 项）

1. ✅ `packages/geoviz-well-track-native/` 独立存在（21 头/源 + 3 测试可执行 + example + 36 SVG 资产 + README）。
2. ✅ standalone C++ package：自带 CMake，可独立 `-S packages/geoviz-well-track-native` 配置构建；install/export（A install config 落地后启用完整导出）。
3. ✅ 领域模型与 QWidget/renderer 分离（domain 零 Qt；controller/widget 只经 seam）。
4. ✅ 实际绘制消费 `GeoViz::QgisWellTrack`（qgis_surface.cpp；smoke 经 WellTrackCanvas/QgsPlotCanvas）。
5. ✅ 无第二 generic PlotCanvas/Axis/ZoomPan 引擎（Round 3 专项 grep 确认；MockSurface 是记录式 test double）。
6. ✅ 多轨/多曲线井道显示（默认文档 9 类轨道；merge groups；smoke 6 轨 3 曲线）。
7. ✅ 岩性/沉积相（嵌套降级最深级）/体系域/层位语义（pattern catalog + 模式映射 + tops overlay）。
8. ✅ shared depth + inspection + track management（同步组防回环；inspectAt 结构化读出；增删/排序/显隐/宽度/merge/split）。
9. ✅ host data adapter 清晰（IWellTrackDataSource/IDepthTransformService；无 workbench 私有类型）。
10. ✅ Python `geoviz_well_log` 保持原样，形成 feature/oracle 对照（docs 01/03）。
11. ✅ 大数组零拷贝（shared_ptr<const CurveBuffer> 直传 seam；测试断言指针同一）。
12. ✅ 生命周期 review 无 P0/P1（Round 2 路径 8 + Round 3 专项）。
13. ✅ 4 轮 review（docs 11–14）。
14. ✅ 开发期间无反复全仓 build（仅最终两线 targeted build；未 build QGIS；未跑全仓 pytest）。
15. ✅ targeted build/test 成功，并行度 -j2/-j4（≤6）。
16. ✅ representative well smoke 通过（真实内核 ×2 exit=0）。
17. ✅ 与 Prompt A API 集成验证完成（对 A 快照；A 分支自身未编译的部分以 shim 记录，PR 注明 merge guidance）。
18. ✅ commit/push 完成（`git ls-remote` 可见 6ba6dcb0）。
19. ✅ PR #154 已创建。
20. ✅ 不等待线上 CI。
21. ✅ 不自动 merge。

## 移交说明

- **A 侧**：修 docs/14 S1–S7（含 `nsecElapsed` 拼写与 const 滑移）后，B 的 CMake shim 块与 keep-alive 可整体删除；open items（TWT 第二轴/图像带/header 摘要/子列）见 docs/14。
- **host 侧**（paleo-workbench）：`find_package` + 链接两 target，实现 `IWellTrackDataSource`（docs 06/07 有完整适配表与示例）。
- 快照构建目录：`/tmp/wt-build-base`（无 A）、`/tmp/wt-build-qgis`（含 A 快照）。
