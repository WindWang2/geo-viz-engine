# 09 — Performance Plan

B 不实现渲染性能层（LOD/缓存/降采样属 A）。B 的性能责任在数据流与更新粒度。

## 低拷贝路径

| 环节 | 机制 | 反例（禁止） |
|---|---|---|
| host→snapshot | `shared_ptr<const WellDataSnapshot>` 一次构建，多视图共享 | Python CurveTrack 构造期重建 CurveData（内存×2） |
| snapshot→surface | `SurfaceCurveLayer` 持 `CurveBufferPtr`，A 直接读数组 | 逐点 QVariant/QJsonObject |
| 检查 | MockSurface 测试断言传入指针 `get()` 与快照相同（零拷贝直传） | |

目标：1e5+ 样本曲线，B 侧 O(1) 指针传递 + O(log n) 查询（`valueAt` bisect、interval 二分）。

## 更新粒度（六类 → seam 调用）

| 变更类型 | seam 调用 | 成本 |
|---|---|---|
| style-only（颜色/线型/可见） | `updateTrack(单列)` | O(该列) |
| view-state-only（当前深度窗） | `setDepthRange` | O(1) |
| one-curve data（revision diff 命中单曲线） | `updateTrack(所在列)` | O(该列) |
| one-track structural（增删曲线/宽度） | `updateTrack` | O(该列) |
| depth transform（checkshot 注入/更换） | `setSecondaryAxis` | O(轴) |
| whole-document（换井/全量重载） | `setTracks` | O(全) |

判定实现：controller 维护 `lastRevision_` 与 `perCurveRevision_` 映射，`replaceSnapshot` 时 diff；结构与顺序变更（增删 track/排序）才升级为 `setTracks`。

## 索引

- 曲线：`CurveBuffer` 约定深度升序（adapter 保证；构造时排序一次），`valueAt` std::upper_bound。
- 区间命中：每 IntervalColumn 构建时按 top 排序的副本 + 命中二分（重叠区间取最长匹配）；深度排序副本在 snapshot 构建时一次完成。
- tops：按 depth 排序 vector，命中=容差窗口二分。
- 全部为只读结构，无锁（GUI 线程合同）。

## 失效与刷新

- B 不做像素缓存（A 职责）；B 的 crosshair/splitter overlay 每帧直绘（无缓存，代价恒定小）。
- `setDepthRange` no-op 守卫（<1e-9）阻断同步组级联重绘（N2/N7 语义）。
- 深度同步组：多 controller 信号经 Qt direct connection 传播，无 16ms QTimer 合流（Qt 信号本身就批处理至事件循环；若实测需要，留 controller 内单发 QTimer 钩子，默认关）。

## 大数据验收（测试）

- 1e5 样本 × 8 曲线 snapshot：`loadSource`+`inspectAt` < 50ms（offscreen，无断言阈值 CI 化，仅回归参考记录）。
- 200 track、5e3 interval 的 `inspectAt` 全命中 < 5ms。
- 重复 switch well ×20 无 RSS 增长（粗粒度：进程 RSS 前后差 < 阈值，防 snapshot 泄漏）。
- 零拷贝断言（上表"检查"行）。

## 明确不优化

- 降采样/LOD 算法、QPainterPath 缓存、DPR 缩放、位图 cache（全部 A 域）。
- 多线程渲染（GUI 线程合同不变）。
